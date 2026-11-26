import operator
from datetime import datetime, timedelta
from functools import reduce

from celery import current_app, shared_task
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from django.db import InterfaceError, OperationalError, transaction
from django.db.models import Q
from django.utils import timezone

from care.emr.api.viewsets.device import disassociate_device_from_encounter
from care.emr.api.viewsets.location import close_related_location_from_encounter
from care.emr.models.encounter import Encounter
from care.emr.resources.encounter.constants import StatusChoices
from encounter_auto_complete.settings import get_class_time_limits

logger = get_task_logger(__name__)

ELIGIBLE_STATUSES = (
    StatusChoices.in_progress.value,
    StatusChoices.on_hold.value,
    StatusChoices.discharged.value,
)


def _complete_encounter(encounters, encounter_id, thresholds, cutoff):
    with transaction.atomic():
        # Recheck eligibility under the lock so overlapping runs are safe.
        encounter = encounters.select_for_update().filter(pk=encounter_id).first()
        if encounter is None:
            return False

        start = encounter.period.get("start")
        if start is not None:
            try:
                start = datetime.fromisoformat(start)
            except (TypeError, ValueError):
                logger.warning(
                    "Skipping encounter %s with an invalid period start",
                    encounter.external_id,
                )
                return False
            if timezone.is_naive(start):
                start = timezone.make_aware(start, current_app.timezone)
            if start >= thresholds[encounter.encounter_class]:
                return False

        completed_at = timezone.now().isoformat()
        encounter.status = StatusChoices.completed.value
        encounter.status_history.setdefault("history", []).append(
            {
                "status": encounter.status,
                "moved_at": completed_at,
                "source": "encounter_auto_complete",
                "scheduled_for": cutoff.isoformat(),
            }
        )
        if not encounter.period.get("end"):
            encounter.period["end"] = completed_at
        # Automated completion must not be attributed to the previous editor.
        encounter.updated_by = None
        disassociate_device_from_encounter(encounter)
        close_related_location_from_encounter(encounter)
        encounter.save(
            update_fields=[
                "status",
                "status_history",
                "period",
                "updated_by",
                "modified_date",
            ]
        )
    return True


@shared_task(bind=True, max_retries=3)
def complete_encounters(self, cutoff=None):
    """Complete open encounters older than their class time limit at midnight."""
    time_limits = get_class_time_limits()
    if not time_limits:
        return 0

    if cutoff is None:
        cutoff = timezone.localtime(timezone.now(), current_app.timezone).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    else:
        cutoff = datetime.fromisoformat(cutoff)
        if timezone.is_naive(cutoff):
            raise ValueError("The encounter completion cutoff must include a timezone")

    # Eligible once created and started before midnight minus the class time limit.
    thresholds = {
        encounter_class: cutoff - timedelta(hours=hours)
        for encounter_class, hours in time_limits.items()
    }
    encounters = Encounter.objects.filter(
        reduce(
            operator.or_,
            (
                Q(encounter_class=encounter_class, created_date__lt=threshold)
                for encounter_class, threshold in thresholds.items()
            ),
        ),
        status__in=ELIGIBLE_STATUSES,
    )
    completed = 0
    try:
        for encounter_id in encounters.values_list("id", flat=True).iterator(
            chunk_size=500
        ):
            try:
                if _complete_encounter(encounters, encounter_id, thresholds, cutoff):
                    completed += 1
            except (InterfaceError, OperationalError):
                raise
            except Exception:
                # A bad encounter must not block the rest of this run or later runs.
                logger.exception("Failed to auto complete encounter %s", encounter_id)
    except (InterfaceError, OperationalError) as exc:
        # Preserve the original cutoff even if a retry crosses another midnight.
        raise self.retry(
            exc=exc, kwargs={"cutoff": cutoff.isoformat()}, countdown=60
        ) from exc

    logger.info(
        "Completed %s encounters for midnight %s", completed, cutoff.isoformat()
    )
    return completed


@current_app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        crontab(hour=0, minute=0),
        complete_encounters.s(),
        name="auto_complete_encounters_at_midnight",
    )

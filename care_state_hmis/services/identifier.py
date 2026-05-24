"""Hospital Identifier (Encounter.external_identifier) generation service."""

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from care_state_hmis.models import EncounterIdentifierSequence

ALLOWED_TOKENS = {"FAC_CODE", "YYYY", "MM", "DD", "SEQ", "CLASS", "CLASS_TEXT"}

# Hardcoded mapping of ``Encounter.encounter_class`` codes (see
# ``care.emr.resources.encounter.constants.ClassChoices``) to the short
# human-friendly tokens rendered by ``{CLASS_TEXT}``. Unknown codes fall back
# to the upper-cased raw code.
ENCOUNTER_CLASS_TEXT_MAP = {
    "imp": "IP",      # inpatient
    "amb": "OP",      # ambulatory / outpatient
    "obsenc": "OBS",  # observation
    "emer": "ER",     # emergency
    "vr": "VR",       # virtual
    "hh": "HH",       # home health
}


def _class_text(encounter_class: str | None) -> str:
    if not encounter_class:
        return ""
    return ENCOUNTER_CLASS_TEXT_MAP.get(encounter_class, encounter_class.upper())


def _bucket_for(reset_period: str) -> str:
    now = timezone.localtime()
    if reset_period == "yearly":
        return now.strftime("%Y")
    if reset_period == "monthly":
        return now.strftime("%Y-%m")
    if reset_period == "daily":
        return now.strftime("%Y-%m-%d")
    return ""


def _allocate_sequence(facility_id, bucket: str) -> int:
    """Atomically allocate the next sequence number for (facility, bucket).

    Uses ``SELECT ... FOR UPDATE`` so concurrent workers cannot hand out the
    same value.
    """
    with transaction.atomic():
        row, _ = (
            EncounterIdentifierSequence.objects.select_for_update().get_or_create(
                facility_id=facility_id, bucket=bucket
            )
        )
        EncounterIdentifierSequence.objects.filter(pk=row.pk).update(
            last_value=F("last_value") + 1
        )
        row.refresh_from_db(fields=["last_value"])
        return row.last_value


def generate_identifier(encounter, config) -> str:
    """Render the Hospital Identifier for a freshly-created encounter."""
    bucket = _bucket_for(config.reset_period)
    seq = _allocate_sequence(encounter.facility_id, bucket)
    now = timezone.localtime()
    ctx = {
        "FAC_CODE": config.facility_code or str(encounter.facility_id)[:6],
        "YYYY": now.strftime("%Y"),
        "MM": now.strftime("%m"),
        "DD": now.strftime("%d"),
        "SEQ": seq,
        "CLASS": (encounter.encounter_class or "").upper(),
        "CLASS_TEXT": _class_text(encounter.encounter_class),
    }
    return config.pattern.format(**ctx)

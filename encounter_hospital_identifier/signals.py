"""Auto-assignment and immutability of the Hospital Identifier
(stored as ``Encounter.external_identifier``).

Format: ``{YY}{MM}{id:08d}`` derived from the encounter's ``created_date`` and
auto-increment primary key.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from care.emr.models.encounter import Encounter

HOSPITAL_IDENTIFIER_LABEL = "Hospital Identifier"


def _format_identifier(encounter) -> str:
    created = encounter.created_date or timezone.now()
    # Read YY
    year = timezone.localtime(created).strftime("%y")
    month = timezone.localtime(created).strftime("%m")
    return f"{year}{month}{encounter.id:08d}"


@receiver(
    pre_save,
    sender=Encounter,
    dispatch_uid="hmis_hospital_identifier_immutable",
)
def guard_hospital_identifier(sender, instance, **kwargs):
    """Reject any change to ``external_identifier`` after it has been set.

    Bypassed by ``QuerySet.update`` (which does not fire pre_save) — the
    assignment receiver uses that path intentionally.
    """
    if instance._state.adding:  # noqa: SLF001
        return
    try:
        old = Encounter.objects.only("external_identifier").get(pk=instance.pk)
    except Encounter.DoesNotExist:
        return
    if old.external_identifier and old.external_identifier != instance.external_identifier:
        raise ValidationError({"external_identifier": (f"{HOSPITAL_IDENTIFIER_LABEL} cannot be changed once assigned.")})


@receiver(
    post_save,
    sender=Encounter,
    dispatch_uid="hmis_hospital_identifier_assign",
)
def assign_hospital_identifier(sender, instance, created, **kwargs):
    """On create, stamp ``external_identifier`` with ``{YY}{MM}{id:08d}``.

    No-op if an identifier was already supplied with the create payload.
    """
    if not created or instance.external_identifier:
        return

    encounter_pk = instance.pk

    def _do():
        identifier = _format_identifier(instance)
        Encounter.objects.filter(pk=encounter_pk, external_identifier__isnull=True).update(external_identifier=identifier)

    transaction.on_commit(_do)

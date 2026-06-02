"""Signals for auto-assignment and immutability of the Hospital Identifier
(stored as ``Encounter.external_identifier``).
"""

import logging

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from care.emr.models.encounter import Encounter
from encounter_identifiers.models import FacilityEncounterIdentifierConfig
from encounter_identifiers.services.identifier import (
    IdentifierStampSkipped,
    allocate_identifier,
)

logger = logging.getLogger(__name__)

HOSPITAL_IDENTIFIER_LABEL = "Hospital Identifier"
MAX_ASSIGNMENT_ATTEMPTS = 3


@receiver(
    pre_save,
    sender=Encounter,
    dispatch_uid="hmis_hospital_identifier_immutable",
)
def guard_hospital_identifier(sender, instance, **kwargs):
    """Reject any change to ``external_identifier`` after it has been set.

    Bypassed only by ``Encounter.objects.filter(...).update(...)``, which does
    not fire pre_save — the assignment signal uses that path intentionally.
    """
    if instance._state.adding:  # noqa: SLF001
        return
    try:
        old = Encounter.objects.only("external_identifier").get(pk=instance.pk)
    except Encounter.DoesNotExist:
        return
    if (
        old.external_identifier
        and old.external_identifier != instance.external_identifier
    ):
        raise ValidationError(
            {
                "external_identifier": (
                    f"{HOSPITAL_IDENTIFIER_LABEL} cannot be changed once assigned."
                )
            }
        )


@receiver(
    post_save,
    sender=Encounter,
    dispatch_uid="hmis_encounter_hospital_identifier_assign",
)
def assign_hospital_identifier(sender, instance, created, **kwargs):
    """On create, allocate and stamp a Hospital Identifier from the facility's
    configured pattern. No-op if the facility has no config, or if the encounter
    was created with an identifier already supplied.
    """
    if not created or instance.external_identifier:
        return
    try:
        config = instance.facility.hmis_encounter_identifier_config
    except FacilityEncounterIdentifierConfig.DoesNotExist:
        return
    if not config.is_enabled_for_encounter_class(instance.encounter_class):
        return

    encounter_pk = instance.pk

    def _do():
        for attempt in range(MAX_ASSIGNMENT_ATTEMPTS):
            try:
                allocate_identifier(instance, config)
                return
            except IdentifierStampSkipped:
                return
            except IntegrityError:
                if attempt == MAX_ASSIGNMENT_ATTEMPTS - 1:
                    logger.exception(
                        "Failed to allocate %s for encounter %s after %d attempts",
                        HOSPITAL_IDENTIFIER_LABEL,
                        encounter_pk,
                        MAX_ASSIGNMENT_ATTEMPTS,
                    )
                    raise

    transaction.on_commit(_do)

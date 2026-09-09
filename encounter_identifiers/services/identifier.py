"""Hospital Identifier (Encounter.external_identifier) generation service."""

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from encounter_identifiers.models import (
    EncounterIdentifierAllocation,
    EncounterIdentifierSequence,
)

ALLOWED_TOKENS = {"FAC_CODE", "YYYY", "YY", "MM", "DD", "SEQ", "CLASS", "CLASS_TEXT"}

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


class IdentifierStampSkippedError(Exception):
    """Raised when the encounter can no longer receive a plugin allocation."""


def _bucket_for(reset_period: str, now=None) -> str:
    now = now or timezone.localtime()
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


def _render_identifier(encounter, config, seq: int, now) -> str:
    ctx = {
        "FAC_CODE": config.facility_code or str(encounter.facility_id)[:6],
        "YYYY": now.strftime("%Y"),
        "YY": now.strftime("%y"),
        "MM": now.strftime("%m"),
        "DD": now.strftime("%d"),
        "SEQ": seq,
        "CLASS": (encounter.encounter_class or "").upper(),
        "CLASS_TEXT": _class_text(encounter.encounter_class),
    }
    return config.pattern.format(**ctx)


def generate_identifier(encounter, config) -> str:
    """Reserve, stamp, and return the Hospital Identifier for an encounter."""
    allocation = allocate_identifier(encounter, config)
    if allocation:
        return allocation.identifier
    return encounter.external_identifier or ""


def allocate_identifier(encounter, config) -> EncounterIdentifierAllocation | None:
    """Reserve and stamp a plugin-generated identifier for an encounter.

    ``EncounterIdentifierAllocation`` is the durable uniqueness boundary. The
    core encounter field is updated only after a reservation row is created.
    """
    existing_allocation = EncounterIdentifierAllocation.objects.filter(
        encounter=encounter
    ).first()
    if existing_allocation:
        updated = encounter.__class__.objects.filter(pk=encounter.pk).filter(
            Q(external_identifier__isnull=True) | Q(external_identifier="")
        ).update(external_identifier=existing_allocation.identifier)
        if updated:
            encounter.external_identifier = existing_allocation.identifier
        return existing_allocation

    now = timezone.localtime()
    bucket = _bucket_for(config.reset_period, now)
    seq = _allocate_sequence(encounter.facility_id, bucket)
    identifier = _render_identifier(encounter, config, seq, now)

    with transaction.atomic():
        existing_allocation = EncounterIdentifierAllocation.objects.filter(
            encounter=encounter
        ).first()
        if existing_allocation:
            updated = encounter.__class__.objects.filter(pk=encounter.pk).filter(
                Q(external_identifier__isnull=True) | Q(external_identifier="")
            ).update(external_identifier=existing_allocation.identifier)
            if updated:
                encounter.external_identifier = existing_allocation.identifier
            return existing_allocation

        allocation = EncounterIdentifierAllocation.objects.create(
            encounter=encounter,
            facility_id=encounter.facility_id,
            identifier=identifier,
            bucket=bucket,
            sequence=seq,
            pattern=config.pattern,
            reset_period=config.reset_period,
        )
        updated = (
            encounter.__class__.objects.filter(pk=encounter.pk)
            .filter(Q(external_identifier__isnull=True) | Q(external_identifier=""))
            .update(external_identifier=identifier)
        )
        if not updated:
            raise IdentifierStampSkippedError
        encounter.external_identifier = identifier
        return allocation

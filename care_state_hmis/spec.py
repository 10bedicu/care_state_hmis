from enum import StrEnum
from string import Formatter

from pydantic import UUID4, Field, field_validator

from care.emr.resources.base import EMRResource
from care.emr.resources.encounter.constants import ClassChoices
from care_state_hmis.models import FacilityEncounterIdentifierConfig
from care_state_hmis.services.identifier import ALLOWED_TOKENS


class ResetPeriodChoices(StrEnum):
    none = "none"
    yearly = "yearly"
    monthly = "monthly"
    daily = "daily"


class FacilityEncounterIdentifierConfigWriteSpec(EMRResource):
    __model__ = FacilityEncounterIdentifierConfig
    __exclude__ = ["facility"]

    pattern: str
    facility_code: str = ""
    enabled_encounter_classes: list[ClassChoices] = Field(default_factory=list)
    reset_period: ResetPeriodChoices = ResetPeriodChoices.yearly

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, value):
        formatter = Formatter()
        try:
            parsed = list(formatter.parse(value))
        except ValueError as exc:
            raise ValueError("Invalid pattern format string.") from exc

        has_seq = False
        for _, field_name, _, _ in parsed:
            if field_name is None:
                continue
            if field_name not in ALLOWED_TOKENS:
                allowed_tokens = ", ".join(sorted(ALLOWED_TOKENS))
                message = (
                    f"Invalid token '{field_name}'. Allowed tokens: {allowed_tokens}."
                )
                raise ValueError(message)
            if field_name == "SEQ":
                has_seq = True

        if not has_seq:
            raise ValueError(
                "Pattern must include {SEQ} to guarantee unique identifiers."
            )

        return value

    @field_validator("enabled_encounter_classes")
    @classmethod
    def validate_enabled_encounter_classes(cls, value):
        return list(dict.fromkeys(value))

    def perform_extra_deserialization(self, is_update, obj):
        if not is_update:
            obj.facility = self._context["facility"]


class FacilityEncounterIdentifierConfigReadSpec(EMRResource):
    __model__ = FacilityEncounterIdentifierConfig
    __exclude__ = []

    id: UUID4 | None = None
    facility: UUID4 | None = None
    pattern: str
    facility_code: str
    enabled_encounter_classes: list[ClassChoices] = Field(default_factory=list)
    reset_period: ResetPeriodChoices

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["facility"] = str(obj.facility.external_id)

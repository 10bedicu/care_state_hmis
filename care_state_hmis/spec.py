from string import Formatter

from pydantic import UUID4, field_validator
from enum import Enum


from care.emr.resources.base import EMRResource

from care_state_hmis.models import FacilityEncounterIdentifierConfig
from care_state_hmis.services.identifier import ALLOWED_TOKENS

class ResetPeriodChoices(str, Enum):
    none = "none"
    yearly = "yearly"
    monthly = "monthly"
    daily = "daily"

class FacilityEncounterIdentifierConfigWriteSpec(EMRResource):
    __model__ = FacilityEncounterIdentifierConfig
    __exclude__ = ["facility"]

    pattern: str
    facility_code: str = ""
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
                raise ValueError(
                    f"Invalid token '{field_name}'. Allowed tokens: {allowed_tokens}."
                )
            if field_name == "SEQ":
                has_seq = True

        if not has_seq:
            raise ValueError(
                "Pattern must include {SEQ} to guarantee unique identifiers."
            )

        return value

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
    reset_period: ResetPeriodChoices

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["facility"] = str(obj.facility.external_id)

from django.db import models

from care.emr.models.base import EMRBaseModel


class FacilityEncounterIdentifierConfig(EMRBaseModel):
    """Per-facility configuration for auto-generating ``Encounter.external_identifier``.

    The external_identifier is presented to users as **"Hospital Identifier"**.
    """

    RESET_PERIOD_CHOICES = [
        ("none", "none"),
        ("yearly", "yearly"),
        ("monthly", "monthly"),
        ("daily", "daily"),
    ]

    facility = models.OneToOneField(
        "facility.Facility",
        on_delete=models.CASCADE,
        related_name="hmis_encounter_identifier_config",
    )
    pattern = models.CharField(
        max_length=128,
        help_text=(
            "Format string. Allowed tokens: {FAC_CODE}, {YYYY}, {MM}, {DD}, "
            "{SEQ}, {CLASS}, {CLASS_TEXT}. "
            "Example: {CLASS_TEXT}-{FAC_CODE}-{YYYY}-{SEQ:06d}"
        ),
    )
    facility_code = models.CharField(max_length=16, blank=True)
    enabled_encounter_classes = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Encounter class codes for which identifiers are generated. "
            "Empty list enables all encounter classes."
        ),
    )
    reset_period = models.CharField(
        max_length=16,
        choices=RESET_PERIOD_CHOICES,
        default="yearly",
    )

    class Meta:
        app_label = "care_state_hmis"

    def is_enabled_for_encounter_class(self, encounter_class):
        if not self.enabled_encounter_classes:
            return True
        return encounter_class in self.enabled_encounter_classes

    def __str__(self):
        return f"HospitalIdentifierConfig({self.facility_id})"

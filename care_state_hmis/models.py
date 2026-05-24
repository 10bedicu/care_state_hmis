from django.db import models


class FacilityEncounterIdentifierConfig(models.Model):
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
    reset_period = models.CharField(
        max_length=16,
        choices=RESET_PERIOD_CHOICES,
        default="yearly",
    )

    def __str__(self):
        return f"HospitalIdentifierConfig({self.facility_id})"


class EncounterIdentifierSequence(models.Model):
    """Race-safe per-(facility, bucket) monotonic counter."""

    facility = models.ForeignKey("facility.Facility", on_delete=models.CASCADE)
    bucket = models.CharField(max_length=16, default="")
    last_value = models.BigIntegerField(default=0)

    class Meta:
        unique_together = [("facility", "bucket")]

    def __str__(self):
        return f"EncounterIdentifierSequence({self.facility_id}, {self.bucket!r}, {self.last_value})"

from django.db import models


class EncounterIdentifierSequence(models.Model):
    """Race-safe per-(facility, bucket) monotonic counter."""

    facility = models.ForeignKey("facility.Facility", on_delete=models.CASCADE)
    bucket = models.CharField(max_length=16, default="")
    last_value = models.BigIntegerField(default=0)

    class Meta:
        app_label = "care_state_hmis"
        unique_together = [("facility", "bucket")]

    def __str__(self):
        return f"EncounterIdentifierSequence({self.facility_id}, {self.bucket!r}, {self.last_value})"

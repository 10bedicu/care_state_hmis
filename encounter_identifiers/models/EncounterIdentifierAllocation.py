from django.db import models


class EncounterIdentifierAllocation(models.Model):
    """Plugin-owned reservation for identifiers assigned to encounters."""

    encounter = models.OneToOneField(
        "emr.Encounter",
        on_delete=models.CASCADE,
        related_name="hmis_identifier_allocation",
    )
    facility = models.ForeignKey("facility.Facility", on_delete=models.CASCADE)
    identifier = models.CharField(max_length=100)
    bucket = models.CharField(max_length=16, default="")
    sequence = models.BigIntegerField()
    pattern = models.CharField(max_length=128)
    reset_period = models.CharField(max_length=16)
    allocated_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["facility", "bucket", "sequence"],
                name="unique_hmis_encounter_identifier_seq",
            ),
        ]

    def __str__(self):
        return f"EncounterIdentifierAllocation({self.encounter_id}, {self.identifier!r})"

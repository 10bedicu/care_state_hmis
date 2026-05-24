from django.contrib import admin

from care_state_hmis.models import (
    EncounterIdentifierSequence,
    FacilityEncounterIdentifierConfig,
)


@admin.register(FacilityEncounterIdentifierConfig)
class FacilityEncounterIdentifierConfigAdmin(admin.ModelAdmin):
    list_display = ("facility", "pattern", "facility_code", "reset_period")
    search_fields = ("facility__name", "facility_code")
    autocomplete_fields = ("facility",)


@admin.register(EncounterIdentifierSequence)
class EncounterIdentifierSequenceAdmin(admin.ModelAdmin):
    list_display = ("facility", "bucket", "last_value")
    search_fields = ("facility__name",)
    readonly_fields = ("facility", "bucket", "last_value")

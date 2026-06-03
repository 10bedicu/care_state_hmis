from care.emr.extensions.base import PlugExtension, ExtensionResource
from care.emr.models.location import FacilityLocation
from care.emr.registries.extensions.registry import ExtensionRegistry


class EncounterKindLocationAssignmentExtension(PlugExtension):
    extension_name = "encounter_kind_location_assignment"
    extension_version = "1.0.0"
    resource_type = ExtensionResource.encounter
    write_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Location",
        "type": "object",
        "properties": {
            "location": {"type": "string", "title": "Assign to a Location"},
        },
        "additionalProperties": "false",
    }
    retrieve_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Patient Demographics",
        "type": "object",
        "x-ui": {"control": "grid"},
        "properties": {
            "location": {"type": "string", "title": "Assign to a Location"},
        },
        "additionalProperties": "false",
    }

    def validate(self, data, resource=None):
        super().validate(data, resource)

        if location_external_id := data.get("location"):
            if not FacilityLocation.objects.filter(external_id=location_external_id, mode="kind").exists():
                raise ValueError("Kind location does not exist")


ExtensionRegistry.register(EncounterKindLocationAssignmentExtension())

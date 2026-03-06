from care.emr.extensions.base import PlugExtension, ExtensionResource
from care.emr.registries.extensions.registry import ExtensionRegistry


class PatientDemographicsExtension(PlugExtension):
    extension_name = "patient_demographics"
    extension_version = "1.0.0"
    resource_type = ExtensionResource.patient
    write_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Patient Demographics",
        "type": "object",
        "x-ui": {"control": "grid"},
        "properties": {
            "related_person": {"type": "string", "title": "Related Person"},
            "caste": {
                "type": "string",
                "title": "Caste",
                "enum": ["OBC", "General", "SC", "ST", "Other"],
            },
            "religion": {
                "type": "string",
                "title": "Religion",
                "enum": ["Hindu", "Muslim", "Christian", "Sikh", "Jain", "Other"],
            },
        },
        "additionalProperties": "false",
    }


ExtensionRegistry.register(PatientDemographicsExtension())

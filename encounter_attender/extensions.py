from care.emr.extensions.base import PlugExtension, ExtensionResource
from care.emr.registries.extensions.registry import ExtensionRegistry

class EncounterAttenderExtension(PlugExtension):
    extension_name = "encounter_attender"
    extension_version = "1.0.0"
    resource_type = ExtensionResource.encounter
    write_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Encounter Attender",
        "type": "object",
        "properties": {
            "attender": {
                "type": "object",
                "title": "Attender Details",
                "x-ui": {"control": "grid"},
                "properties": {
                    "attender_relation": {
                        "type": "string",
                        "title": "Attender Relation",
                        "enum": ["S/O","D/O","F/O","M/O","W/O","H/O","Guardian/O"],
                    },
                    "attender_name": {"type": "string", "title": "Attender Name"},
                    "attender_phone": {
                        "type": "string",
                        "title": "Attender Phone Number",
                    },
                    "attender_address": {"type": "string", "title": "Attender Address"},
                },
            }
        },
        "additionalProperties": "false",
    }
    retrieve_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Encounter Attender",
        "type": "object",
        "properties": {
            "attender": {
                "type": "object",
                "title": "Attender Details",
                "x-ui": {"control": "grid"},
                "properties": {
                    "attender_relation": {
                        "type": "string",
                        "title": "Attender Relation",
                        "enum": ["S/O","D/O","F/O","M/O","W/O","H/O","Guardian/O"],
                    },
                    "attender_name": {"type": "string", "title": "Attender Name"},
                    "attender_phone": {"type": "string", "title": "Attender Phone Number"},
                    "attender_address": {"type": "string", "title": "Attender Address"},
                },
            }
        },
        "additionalProperties": "false",
    }

ExtensionRegistry.register(EncounterAttenderExtension())
from care.emr.extensions.base import PlugExtension, ExtensionResource
from care.emr.registries.extensions.registry import ExtensionRegistry

from patient_demographics.settings import plugin_settings

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
    retrieve_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Patient Demographics",
        "type": "object",
        "x-ui": {"control": "grid"},
        "properties": {
            "related_person": {"type": "string", "title": "Related Person"},
            "caste": {
                "x-ui": {"render_blacklist": ["treatment_summary", "appointment_print"]},
                "type": "string",
                "title": "Caste",
                "enum": ["OBC", "General", "SC", "ST", "Other"],
            },
            "religion": {
                "x-ui": {"render_blacklist": ["treatment_summary", "appointment_print"]},
                "type": "string",
                "title": "Religion",
                "enum": ["Hindu", "Muslim", "Christian", "Sikh", "Jain", "Other"],
            },
        },
        "additionalProperties": "false",
    }


ExtensionRegistry.register(PatientDemographicsExtension())

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
                    "attender_relation": {"type": "string", "title": "Attender Relation", "enum": ["S/O","D/O","F/O","M/O","W/O","H/O","Guardian/O"]},
                    "attender_name": {"type": "string", "title": "Attender Name"},
                    "attender_phone": {"type": "string", "title": "Attender Phone Number"},
                    "attender_address": {"type": "string", "title": "Attender Address"},
                },
            },
        },
        "additionalProperties": "false"
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
                    "attender_relation": {"type": "string", "title": "Attender Relation", "enum": ["S/O","D/O","F/O","M/O","W/O","H/O","Guardian/O"]},
                    "attender_name": {"type": "string", "title": "Attender Name"},
                    "attender_phone": {"type": "string", "title": "Attender Phone Number"},
                    "attender_address": {"type": "string", "title": "Attender Address"},
                },
            },
        },
        "additionalProperties": "false"
    }

if plugin_settings.HMIS_EXTENSIONS_ENABLE_ATTENDER:
    ExtensionRegistry.register(EncounterAttenderExtension())

class EncounterLocationExtension(PlugExtension):
    extension_name = "encounter_kind_location_assignment"
    extension_version = "1.0.0"
    resource_type = ExtensionResource.encounter
    write_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Location Assignment",
        "type": "object",
        "x-ui": {"control": "grid", "render_blacklist": ["ip_admission_form"]},
        "properties": {
            "location": {
                "type": "string",
                "title": "Ward/Wing Admitted To",
            },
        },
        "additionalProperties": "false"
    }
    retrieve_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Location Assignment",
        "type": "object",
        "x-ui": {"control": "grid", "render_blacklist": ["ip_admission_form"]},
        "properties": {
            "location": {
                "type": "string",
                "title": "Ward/Wing Admitted To",
            },
        },
        "additionalProperties": "false"
    }

if plugin_settings.HMIS_EXTENSIONS_ENABLE_LOCATION_KIND:
    ExtensionRegistry.register(EncounterLocationExtension())

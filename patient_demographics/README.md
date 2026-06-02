# Patient Demographics Plugin

Adds extra demographic fields to the CARE patient resource through the plug extension registry.

## What It Does

- Registers a `PlugExtension` for the patient resource.
- Adds `related_person`, `caste`, and `religion` fields to the stored extension payload.
- Defines both write and retrieve schemas for the demographic extension.
- Prevents `caste` and `religion` from rendering in `treatment_summary` and `appointment_print` contexts.

## Configuration Notes

This plugin does not define plugin-specific settings in this repository.

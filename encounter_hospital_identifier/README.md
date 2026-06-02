# Encounter Hospital Identifier Plugin

Assigns a hospital-facing identifier to encounters and keeps that identifier immutable after creation.

## What It Does

- Generates `Encounter.external_identifier` after encounter creation.
- Uses the format `YYMM########`, based on the encounter creation date and database id.
- Prevents later changes to `external_identifier` once a value has been assigned.

## Configuration Notes

This plugin does not define plugin-specific settings in this repository.

# Encounter Access Authorization Plugin

Adds custom encounter authorization logic for restart operations in CARE.

## What It Does

- Registers a custom authorization handler with the encounter authorization controller.
- Allows superusers to restart completed encounters.
- Allows the user who last updated an encounter to restart it when the encounter is completed and they still have encounter write permission.
- Falls back to CARE's existing encounter access checks for permission evaluation inside the encounter.

## Configuration Notes

This plugin does not define plugin-specific settings in this repository.

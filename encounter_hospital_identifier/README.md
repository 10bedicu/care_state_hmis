# Encounter Hospital Identifier Plugin

Gives each new encounter a Hospital Identifier and prevents that identifier from being changed later.

This plugin always uses the same identifier format. Use `encounter_identifiers` instead when each facility needs its own format or sequence reset rules. Do not enable both plugins at the same time.

## How It Works

After an encounter is created, the plugin sets `Encounter.external_identifier` to `{YY}{MM}{id:08d}`. It uses the encounter's local creation date and pads the database ID to eight digits. For example, an encounter created in March 2026 with ID 42 becomes `260300000042`.

The identifier is saved after the encounter has been created. If an encounter already has an identifier, the plugin leaves it unchanged.

Once an identifier has been assigned, the plugin rejects later changes to it.

## Configuration

This plugin has no settings. The format is fixed.

## Signals

| Signal | Sender | Handler | Purpose |
| --- | --- | --- | --- |
| `pre_save` | `Encounter` | `guard_hospital_identifier` | Stops an assigned identifier from being changed. |
| `post_save` | `Encounter` | `assign_hospital_identifier` | Adds the identifier to a new encounter. |

## Routes

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe. |

## Notes

- The identifier is unique because it includes the database ID, but that also reveals roughly how many encounters exist.
- The plugin checks the saved record every time an encounter is updated.
- Bulk updates using `QuerySet.update` skip this protection.

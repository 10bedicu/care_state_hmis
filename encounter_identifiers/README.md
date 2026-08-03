# Encounter Identifiers Plugin

Creates Hospital Identifiers for encounters using a format that each facility can choose.

Use this instead of `encounter_hospital_identifier` when facilities need different formats or sequence reset rules. Do not enable both plugins at the same time.

## How It Works

A facility starts using this plugin by creating a `FacilityEncounterIdentifierConfig`. Facilities without a configuration are left unchanged, so you can enable it one facility at a time.

After an encounter is created, the plugin checks the facility configuration and the encounter class. When the encounter qualifies, it takes the next number in the sequence, builds an identifier from the configured pattern, records it, and saves it to `Encounter.external_identifier`.

The sequence is protected so two people creating encounters at the same time cannot receive the same number. If there is a collision, the plugin tries again up to three times before reporting an error.

Once an identifier has been assigned, the plugin rejects later changes to it.

### Pattern tokens

| Token | Value |
| --- | --- |
| `{FAC_CODE}` | The configured `facility_code`, or the first six characters of the facility ID when it is blank |
| `{YYYY}` `{YY}` `{MM}` `{DD}` | The date the identifier is assigned, in local time |
| `{SEQ}` | The next sequence number; supports formats such as `{SEQ:06d}` |
| `{CLASS}` | The encounter class code in uppercase |
| `{CLASS_TEXT}` | Short encounter class name: `IP`, `OP`, `OBS`, `ER`, `VR`, or `HH` |

Every pattern must include `{SEQ}`. For example, `{CLASS_TEXT}-{FAC_CODE}-{YYYY}-{SEQ:06d}` produces `OP-KLM01-2026-000042`.

### Reset periods

`reset_period` controls when the numbering starts again: `yearly` (the default), `monthly`, `daily`, or `none` to keep one continuous sequence. Include the matching date in the pattern so a reset does not create an identifier that was used before.

## Configuration

This plugin has no global settings. Configure it separately for each facility using the routes below.

| Field | Default | Description |
| --- | --- | --- |
| `pattern` | required | Identifier format. It must contain `{SEQ}`. |
| `facility_code` | `""` | Short code used for `{FAC_CODE}`. |
| `enabled_encounter_classes` | `[]` | Encounter classes that receive identifiers. Leave empty to include every class. |
| `reset_period` | `yearly` | When the numbering restarts: `none`, `yearly`, `monthly`, or `daily`. |

## Models

| Model | Purpose |
| --- | --- |
| `FacilityEncounterIdentifierConfig` | A facility's identifier format, code, encounter classes, and reset period. |
| `EncounterIdentifierSequence` | The latest number used by a facility for a period. |
| `EncounterIdentifierAllocation` | A record of every identifier assigned. |

## Signals

| Signal | Sender | Handler | Purpose |
| --- | --- | --- | --- |
| `pre_save` | `Encounter` | `guard_hospital_identifier` | Stops an assigned identifier from being changed. |
| `post_save` | `Encounter` | `assign_hospital_identifier` | Creates and adds the identifier to a new encounter. |

## Routes

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/facility/<facility_external_id>/identifier-config/` | View a facility's configuration. |
| `POST` | `/facility/<facility_external_id>/identifier-config/` | Create a facility configuration. |
| `PUT` | `/facility/<facility_external_id>/identifier-config/` | Update a facility configuration. |

All three routes require permission to update the facility. Unlike the other plugins, this one does not provide a `/health` route.

## Notes

- An encounter that already has an identifier is left unchanged.
- Changing a facility's pattern does not change identifiers that have already been assigned.
- Bulk updates using `QuerySet.update` skip this protection.

For more detail about the data model and how identifiers are assigned, see [docs/auto_assign_encounter_identifier.md](docs/auto_assign_encounter_identifier.md).

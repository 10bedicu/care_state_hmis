# Patient Demographics Plugin

Adds extra patient and encounter fields needed for State HMIS reporting.

## How It Works

When CARE starts, this plugin makes extra fields available on patient and encounter records. The values are stored with the existing record, so the plugin does not create its own database tables or migrations.

There are three field groups. The patient fields are always available. The two encounter field groups must be enabled in the plugin settings.

| Extension | Resource | Fields | Registered |
| --- | --- | --- | --- |
| `patient_demographics` | Patient | `related_person`, `caste`, `religion` | Always |
| `encounter_attender` | Encounter | `attender.attender_relation`, `attender_name`, `attender_phone`, `attender_address` | When `HMIS_EXTENSIONS_ENABLE_ATTENDER` is on |
| `encounter_kind_location_assignment` | Encounter | `location` | When `HMIS_EXTENSIONS_ENABLE_LOCATION_KIND` is on |

`caste` and `religion` accept only approved values. They are collected but not shown in the treatment summary or appointment printout. `location` is not shown on the inpatient admission form.

## Configuration

| Setting | Default | Description |
| --- | --- | --- |
| `HMIS_EXTENSIONS_ENABLE_ATTENDER` | `False` | Adds encounter fields for a bystander or attender. |
| `HMIS_EXTENSIONS_ENABLE_LOCATION_KIND` | `False` | Adds an encounter field for the ward or wing where the patient was admitted. |

Restart CARE after changing either setting.

## Signals

This plugin does not listen for signals. It registers its fields when CARE starts.

## Routes

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe. |

## Notes

- Turning off an extension hides it for future use. Values already saved on records remain there.
- Only the fields listed above are accepted; unknown fields are rejected.

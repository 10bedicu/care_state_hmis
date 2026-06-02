# Auto-assign `Encounter.external_identifier` per facility

## Goal

On encounter creation, populate the core field `Encounter.external_identifier`
(labelled **"Hospital Identifier"** in the UI) from a per-facility pattern,
for example `ENC-{FAC_CODE}-{YYYY}-{SEQ:06d}`. This is implemented inside the
`care_state_hmis` plugin without core CARE model changes.

## Current implementation

The latest implementation adds per-facility configuration models, a validation
spec, and an API endpoint for configuring the identifier pattern.

### Data model

`FacilityEncounterIdentifierConfig` lives in
`encounter_identifiers/models/FacilityEncounterIdentifierConfig.py` and stores one
configuration per facility:

```python
class FacilityEncounterIdentifierConfig(EMRBaseModel):
    facility = models.OneToOneField(
        "facility.Facility",
        on_delete=models.CASCADE,
        related_name="hmis_encounter_identifier_config",
    )
    pattern = models.CharField(max_length=128)
    facility_code = models.CharField(max_length=16, blank=True)
    enabled_encounter_classes = models.JSONField(default=list, blank=True)
    reset_period = models.CharField(
        max_length=16,
        choices=[("none", "none"), ("yearly", "yearly"), ("monthly", "monthly"), ("daily", "daily")],
        default="yearly",
    )
```

`EncounterIdentifierSequence` lives in
`encounter_identifiers/models/EncounterIdentifierSequence.py` and stores the
race-safe counter for each `(facility, bucket)` pair:

```python
class EncounterIdentifierSequence(models.Model):
    facility = models.ForeignKey("facility.Facility", on_delete=models.CASCADE)
    bucket = models.CharField(max_length=16, default="")
    last_value = models.BigIntegerField(default=0)

    class Meta:
        unique_together = [("facility", "bucket")]
```

Both models are exported from `care_state_hmis/models/__init__.py`.

### Configuration API

`encounter_identifiers/urls.py` exposes one facility-scoped configuration endpoint:

```text
GET  /api/care_state_hmis/facility/<facility_external_id>/identifier-config/
POST /api/care_state_hmis/facility/<facility_external_id>/identifier-config/
PUT  /api/care_state_hmis/facility/<facility_external_id>/identifier-config/
```

The endpoint is backed by
`encounter_identifiers/viewsets/facility_identifier_config.py` and requires
`can_update_facility_obj` permission for the target facility. `GET` returns an
empty object when a facility has no configuration. `POST` creates the first
configuration for a facility, and `PUT` updates the existing one.

Write payload:

```json
{
  "pattern": "{CLASS_TEXT}-{FAC_CODE}-{YYYY}-{SEQ:06d}",
  "facility_code": "GH",
  "enabled_encounter_classes": ["imp", "emer"],
  "reset_period": "yearly"
}
```

Read payload:

```json
{
  "id": "<config_external_id>",
  "facility": "<facility_external_id>",
  "pattern": "{CLASS_TEXT}-{FAC_CODE}-{YYYY}-{SEQ:06d}",
  "facility_code": "GH",
  "enabled_encounter_classes": ["imp", "emer"],
  "reset_period": "yearly"
}
```

Only one `FacilityEncounterIdentifierConfig` can exist for a facility. A second
`POST` returns a validation error: `Configuration already exists for this facility.`

`enabled_encounter_classes` is an optional allowlist. When the list is empty,
identifiers are generated for every encounter class. When the list contains one
or more values, identifiers are generated only for encounters whose
`encounter_class` is in the list. For example, `["imp"]` enables only inpatient
encounters and `["imp", "emer"]` enables inpatient and emergency encounters.

### Pattern validation

`encounter_identifiers/spec.py` validates writes with
`FacilityEncounterIdentifierConfigWriteSpec`.

Allowed tokens:

- `{FAC_CODE}` - configured `facility_code`; if blank, generation falls back to
  the first six characters of the encounter's facility id.
- `{YYYY}`, `{MM}`, `{DD}` - current local assignment date parts.
- `{SEQ}` - per-facility, per-bucket monotonic sequence value.
- `{CLASS}` - upper-cased encounter class code.
- `{CLASS_TEXT}` - short encounter class label. Known mappings are `imp -> IP`,
  `amb -> OP`, `obsenc -> OBS`, `emer -> ER`, `vr -> VR`, and `hh -> HH`.

The pattern must include `{SEQ}`. Format specs are supported, so `{SEQ:06d}`
renders a zero-padded six-digit sequence.

Valid `reset_period` values:

- `none` - one sequence per facility.
- `yearly` - one sequence per facility and year. This is the default.
- `monthly` - one sequence per facility and month.
- `daily` - one sequence per facility and day.

Valid `enabled_encounter_classes` values are the CARE encounter class codes:

- `imp` - inpatient.
- `amb` - ambulatory / outpatient.
- `obsenc` - observation.
- `emer` - emergency.
- `vr` - virtual.
- `hh` - home health.

## Identifier service

`encounter_identifiers/services/identifier.py` renders the final identifier.

- `ALLOWED_TOKENS = {"FAC_CODE", "YYYY", "MM", "DD", "SEQ", "CLASS", "CLASS_TEXT"}`
- `_bucket_for(reset_period)` maps the reset period to `""`, `YYYY`, `YYYY-MM`,
  or `YYYY-MM-DD`.
- `_allocate_sequence(facility_id, bucket)` uses `select_for_update()` and an
  atomic transaction so concurrent workers cannot receive the same value.
- `generate_identifier(encounter, config)` formats the configured pattern using
  the generated context.

## Signals

`encounter_identifiers/signals/encounter.py` wires the behavior to `Encounter` saves.

### Immutability guard (`pre_save`)

Once `external_identifier` has a value, later changes are rejected with:

```text
Hospital Identifier cannot be changed once assigned.
```

The user-facing error message intentionally says "Hospital Identifier", not
`external_identifier`.

### Auto-assignment (`post_save` on create)

On a newly created encounter, the receiver:

1. Skips if `external_identifier` was supplied in the create payload.
2. Skips if the facility has no `FacilityEncounterIdentifierConfig`.
3. Skips if `enabled_encounter_classes` is non-empty and the encounter class is
   not in the configured list.
4. Schedules assignment with `transaction.on_commit()`.
5. Re-fetches the encounter after commit and skips if it was deleted or already
   received an identifier.
6. Generates the identifier and writes it with `QuerySet.update()`.
7. Retries up to three times on `IntegrityError`.

Because assignment runs after commit, the generated Hospital Identifier may not
be present in the original encounter create response. It appears on subsequent
reads.

### `encounter_class` changes

No re-issue happens after creation. If a pattern contains `{CLASS}` or
`{CLASS_TEXT}`, the identifier reflects the encounter class at assignment time.
Later `encounter_class` changes do not rewrite it.

### Missing facility configuration

If a facility has no configuration, the receiver short-circuits silently:

```python
try:
    config = instance.facility.hmis_encounter_identifier_config
except FacilityEncounterIdentifierConfig.DoesNotExist:
    return
```

Concretely:

- `Encounter.external_identifier` keeps whatever was supplied, usually `None`.
- No sequence row is created or touched.
- No `transaction.on_commit` callback is scheduled.
- The immutability guard still applies if a value is later set manually.

Configuring a facility after encounters already exist does not back-fill those
encounters. Assignment only happens at create time.

## File layout

```text
app/care_state_hmis/encounter_identifiers/
├── models/
│   ├── __init__.py
│   ├── EncounterIdentifierSequence.py
│   └── FacilityEncounterIdentifierConfig.py
├── services/
│   └── identifier.py
├── signals/
│   ├── __init__.py
│   └── encounter.py
├── spec.py
├── urls.py
└── viewsets/
    ├── __init__.py
    └── facility_identifier_config.py
```

`care_state_hmis/apps.py` imports `encounter_identifiers.signals`, so signal
registration is handled by the plugin app config.

## Migration note

The current code introduces two new models. A database migration is required
before the feature can be used in an environment.

## Test checklist

- No `FacilityEncounterIdentifierConfig` -> `external_identifier` stays `None`.
- `GET /identifier-config/` without config -> `{}`.
- `POST /identifier-config/` creates the facility config when authorized.
- Duplicate `POST /identifier-config/` -> validation error.
- `PUT /identifier-config/` updates pattern, facility code, enabled encounter
  classes, and reset period.
- Empty `enabled_encounter_classes` -> identifiers generated for all encounter
  classes.
- `enabled_encounter_classes=["imp"]` -> only inpatient encounters receive
  generated identifiers.
- `enabled_encounter_classes=["imp", "emer"]` -> inpatient and emergency
  encounters receive generated identifiers; other classes are skipped.
- Invalid token in `pattern` -> validation error listing allowed tokens.
- Pattern without `{SEQ}` -> validation error.
- Payload supplies `external_identifier` on encounter create -> not overwritten,
  and subsequent edits are rejected.
- Concurrent encounter creates in one facility -> distinct sequence values.
- Two facilities with the same pattern -> independent sequences.
- Encounter create rolled back -> no identifier is stamped on a row.
- Edit on existing encounter changing `external_identifier` -> validation error.
- `encounter_class` changed after creation -> `external_identifier` unchanged.

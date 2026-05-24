# Plan: Auto-assign `Encounter.external_identifier` per Facility (plugin care_state_hmis)

## Goal

On encounter creation, populate the core field `Encounter.external_identifier` (labelled
**"Hospital Identifier"** in the UI) from a per-facility pattern
(e.g. `ENC-{FAC_CODE}-{YYYY}-{SEQ:06d}`). 100% inside the plugin — no core changes.

### Policy decisions (locked)

- **Identifier is immutable** once assigned. Manual edits and `encounter_class`
  changes do **not** rewrite it. Class is captured at create time only.
- **All user-facing error messages refer to the field as "Hospital Identifier"**, never
  `external_identifier`.

---

## 1. Data model (plugin)

**`care_state_hmis/models.py`**

```python
class FacilityEncounterIdentifierConfig(models.Model):
    facility = models.OneToOneField(
        "facility.Facility",
        on_delete=models.CASCADE,
        related_name="hmis_encounter_identifier_config",
    )
    pattern = models.CharField(max_length=128)              # "ENC-{FAC_CODE}-{YYYY}-{SEQ:06d}"
    facility_code = models.CharField(max_length=16, blank=True)
    reset_period = models.CharField(
        max_length=16,
        choices=[("none","none"),("yearly","yearly"),("monthly","monthly"),("daily","daily")],
        default="yearly",
    )

class EncounterIdentifierSequence(models.Model):
    facility = models.ForeignKey("facility.Facility", on_delete=models.CASCADE)
    bucket = models.CharField(max_length=16, default="")    # "", "2026", "2026-05", "2026-05-20"
    last_value = models.BigIntegerField(default=0)

    class Meta:
        unique_together = [("facility", "bucket")]
```

Register `FacilityEncounterIdentifierConfig` in `admin.py` for ops configuration.

---

## 2. Migration (plugin)

`care_state_hmis/migrations/0001_initial.py`:

- Create the two models above.
- Add a partial unique index on the core `emr_encounter` table via `RunSQL`:

```sql
CREATE UNIQUE INDEX hmis_unique_encounter_hospital_identifier_per_facility
ON emr_encounter (facility_id, external_identifier)
WHERE external_identifier IS NOT NULL;
```

Reverse SQL drops the index.

---

## 3. Identifier service

**`care_state_hmis/services/identifier.py`**

```python
ALLOWED_TOKENS = {"FAC_CODE", "YYYY", "MM", "DD", "SEQ", "CLASS"}

def _bucket_for(reset_period: str) -> str: ...
def _allocate_sequence(facility_id, bucket) -> int: ...   # select_for_update
def generate_identifier(encounter, config) -> str: ...
```

- `select_for_update()` + bucketed counter = race-safe under concurrent workers, and
  supports dynamic resets (which a Postgres `SEQUENCE` can't do cleanly).
- `.format(**ctx)` is safe because only whitelisted keys are present.
- `{CLASS}` is resolved **at creation time** and never re-evaluated.

---

## 4. Signals

**`care_state_hmis/signals/encounter.py`**

### 4a. Immutability guard (`pre_save`)

Blocks any later mutation of `external_identifier` once set. Error message uses the
user-facing label "Hospital Identifier".

### 4b. Auto-assignment (`post_save` on create)

- `post_save` + `created` — runs once, after the row exists.
- Skip if already set — payload-supplied identifiers are respected (and then frozen).
- `.filter(pk=...).update(...)` — bypasses re-entering signals; also bypasses the
  immutability guard because no `pre_save` fires on `QuerySet.update`.
- `transaction.on_commit` — sequence numbers are not burned if the encounter create
  rolls back. Tradeoff: identifier appears on subsequent reads, not the create response.
- `dispatch_uid` — guards against duplicate registration on plugin reload.
- Retries up to 3× on `IntegrityError` from the partial unique index.

### How `encounter_class` changes are handled

No re-issue. The identifier baked at create time stands. If `pattern` contains
`{CLASS}`, the value reflects the **original** class — intentional, matches typical
MRN/visit-number semantics.

### When the facility has no `FacilityEncounterIdentifierConfig`

The `post_save` receiver short-circuits silently:

```python
try:
    config = instance.facility.hmis_encounter_identifier_config
except FacilityEncounterIdentifierConfig.DoesNotExist:
    return
```

Concretely:

- `Encounter.external_identifier` keeps whatever was supplied (typically `None`).
- No sequence row is created or touched.
- No `transaction.on_commit` callback is scheduled.
- Nothing is logged — this is a normal no-op, not an error.
- The immutability guard still applies: if the value is later set manually (admin / API),
  it is frozen from that point on.

**Configuring a facility _after_ encounters already exist does not back-fill** existing
rows — assignment only happens at create time. A back-fill management command is
out of scope; add one if/when the need arises.

Wire up in `signals/__init__.py`:

```python
from . import billing      # noqa
from . import encounter    # noqa
```

---

## 5. File layout

```
app/care_state_hmis/care_state_hmis/
├── admin.py                          # + FacilityEncounterIdentifierConfig admin
├── models.py                         # + the two models (new file)
├── migrations/
│   └── 0001_initial.py               # models + partial unique index on emr_encounter
├── services/
│   ├── __init__.py
│   └── identifier.py                 # generate_identifier, _allocate_sequence, _bucket_for
└── signals/
    ├── __init__.py                   # + from . import encounter
    └── encounter.py                  # pre_save guard + post_save assigner
```

`apps.py` already imports `care_state_hmis.signals`, so no change there.

---

## 6. Test checklist

- No `FacilityEncounterIdentifierConfig` → `external_identifier` stays `None`.
- Payload supplies `external_identifier` → not overwritten, and subsequent edits are rejected.
- 50 concurrent encounter creates in one facility → 50 distinct contiguous sequence numbers.
- `reset_period="yearly"` → bucket rolls at Jan 1 (freeze with `time_machine`).
- Two facilities, same pattern → independent sequences.
- Encounter create rolled back → sequence value not consumed (verifies `on_commit`).
- Edit on existing encounter changing `external_identifier` → `ValidationError`:
  "Hospital Identifier cannot be changed once assigned."
- `encounter_class` changed after creation → `external_identifier` unchanged.
- Pattern containing `{CLASS}` reflects class at creation time even after a later class change.

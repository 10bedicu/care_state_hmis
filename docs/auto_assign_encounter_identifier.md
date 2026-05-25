# Plan: Auto-assign `Encounter.external_identifier` (minimal)

## Goal

On encounter creation, stamp `Encounter.external_identifier` (labelled
**"Hospital Identifier"** in the UI) with:

```
{YY}{MM}{id:08d}
```

e.g. encounter with int pk `42` created in May 2026 → `"260500000042"`.

100% inside the plugin — no core changes, no per-facility config, no sequence
table.

---

## Why this is enough

- `Encounter.id` is the auto-increment integer pk on `BaseModel`
  ([care/utils/models/base.py](care/utils/models/base.py#L15-L16)) — already
  unique, already monotonic, already race-safe (Postgres hands it out).
- Year + month prefix keeps identifiers human-readable and groups them visually
  by creation month.
- 8-digit zero-pad gives 10⁸ encounters before overflow; identifier still
  formats sanely past that (digits just grow).

---

## Policy decisions

- **Applies to every encounter on every facility.** No opt-in config.
- **Skip if `external_identifier` is already set** on create (respects payload-supplied values).
- **Immutable** once assigned — `pre_save` guard rejects later mutations with
  the user-facing label "Hospital Identifier".
- **No back-fill** for pre-existing encounters. Assignment only happens at create.

---

## Implementation

### `care_state_hmis/signals/encounter.py`

```python
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from care.emr.models.encounter import Encounter

HOSPITAL_IDENTIFIER_LABEL = "Hospital Identifier"


def _format_identifier(encounter) -> str:
    created = encounter.created_date or timezone.now()
    local = timezone.localtime(created)
    return f"{local.strftime('%y')}{local.strftime('%m')}{encounter.id:08d}"


@receiver(
    pre_save,
    sender=Encounter,
    dispatch_uid="hmis_hospital_identifier_immutable",
)
def guard_hospital_identifier(sender, instance, **kwargs):
    """Reject mutation of external_identifier once set.

    Bypassed by ``QuerySet.update`` (which does not fire pre_save) — the
    assignment receiver uses that path intentionally.
    """
    if instance._state.adding:  # noqa: SLF001
        return
    try:
        old = Encounter.objects.only("external_identifier").get(pk=instance.pk)
    except Encounter.DoesNotExist:
        return
    if old.external_identifier and old.external_identifier != instance.external_identifier:
        raise ValidationError(
            {
                "external_identifier": (
                    f"{HOSPITAL_IDENTIFIER_LABEL} cannot be changed once assigned."
                )
            }
        )


@receiver(
    post_save,
    sender=Encounter,
    dispatch_uid="hmis_hospital_identifier_assign",
)
def assign_hospital_identifier(sender, instance, created, **kwargs):
    if not created or instance.external_identifier:
        return

    encounter_pk = instance.pk

    def _do():
        identifier = _format_identifier(instance)
        Encounter.objects.filter(
            pk=encounter_pk, external_identifier__isnull=True
        ).update(external_identifier=identifier)

    transaction.on_commit(_do)
```

### `care_state_hmis/signals/__init__.py`

```python
from . import billing      # noqa
from . import encounter    # noqa
```

---

## Key choices

- **`{YY}{MM}` derived from `created_date`**, not `now()`, so re-running the
  format always yields the same string for a given encounter.
- **`post_save` + `transaction.on_commit`** — value is stamped after the
  encounter row truly commits; rolled-back creates leave nothing behind.
  Tradeoff: identifier is **not** in the `POST /encounter` response body; it
  appears on subsequent reads.
- **`.filter(pk=..., external_identifier__isnull=True).update(...)`** —
  bypasses re-entering the signal _and_ the immutability guard, and is a no-op
  if another path beat us to it.
- **`dispatch_uid`** — guards against duplicate registration on plugin reload.

---

## What is **not** included (vs. the earlier full design)

- No `FacilityEncounterIdentifierConfig` model.
- No `EncounterIdentifierSequence` counter table.
- No `select_for_update` / bucketed sequence allocation.
- No `{FAC_CODE}`, `{CLASS}`, `{CLASS_TEXT}`, `{SEQ}` tokens.
- No partial unique index on `emr_encounter(facility_id, external_identifier)`
  — `id` is already globally unique, so `{YY}{MM}{id:08d}` is globally unique by
  construction.
- No admin entries, no migrations, no new models.

If/when richer formats are needed, fall back to the full design.

---

## File layout

```
app/care_state_hmis/care_state_hmis/
└── signals/
    ├── __init__.py                   # + from . import encounter
    └── encounter.py                  # pre_save guard + post_save assigner
```

`apps.py` already imports `care_state_hmis.signals`, so no app-config change.

---

## Test checklist

- New encounter created → after commit, `external_identifier == f"{YY}{MM}{id:08d}"`.
- Encounter created with a payload-supplied `external_identifier` → not overwritten.
- Later edit changing `external_identifier` → `ValidationError`:
  "Hospital Identifier cannot be changed once assigned."
- Encounter create rolled back → no row written, nothing to clean up.
- Two encounters with consecutive ids in the same month → identifiers differ in
  the last digits only.
- Encounter created on the 1st vs 31st of the same month → same `YYMM` prefix.

# Care State HMIS Plugins

CARE backend plugin repository for State HMIS workflows.

This repository packages backend plugins that can be installed together from a single source repository:

| Plugin | Purpose |
| --- | --- |
| `invoice_auto_balance` | Automatically balances issued invoices when completed payment reconciliations cover the invoice amount. |
| `patient_demographics` | Adds patient demographic extension fields such as related person, caste, and religion. |
| `encounter_hospital_identifier` | Assigns a hospital-facing encounter identifier and prevents it from being changed later. |
| `encounter_access_authorization` | Adds custom encounter authorization rules for restarting completed encounters. |
| `appointment_invoice_payment` | Creates and settles appointment-linked invoices when charge items are attached to bookings. |
| `encounter_auto_complete` | Completes configured encounter classes across all facilities at midnight. |

## Included Plugins

### `invoice_auto_balance`

Balances an issued invoice after a successful payment reconciliation. When the net paid amount covers the invoice total, the plugin marks billed charge items as paid, updates the invoice status to balanced, and triggers account rebalancing.

### `patient_demographics`

Registers a patient extension schema with CARE so additional demographic fields can be stored and rendered with the patient resource. The current schema adds `related_person`, `caste`, and `religion`.

### `encounter_hospital_identifier`

Assigns `Encounter.external_identifier` automatically using the encounter creation date and database id in the format `YYMM########`. Once assigned, the plugin blocks later edits to that identifier.

### `encounter_access_authorization`

Overrides encounter authorization handling to support custom restart rules. Superusers can restart a completed encounter, and the user who last updated the encounter can do the same when they still hold encounter write permission.

### `appointment_invoice_payment`

Automates billing for appointment bookings after a charge item is attached. The plugin can apply revisit pricing, issue an invoice, and create a corresponding payment reconciliation for the booking.

## Local Development

### Midnight encounter completion

Enable `encounter_auto_complete` as a CARE plug, using this repository as its
`package_name`. It has no API, models, or migrations. Configure one rule per
encounter class in the plug's `configs`:

```python
configs={
    "ENCOUNTER_AUTO_COMPLETE_RULES": [
        {"encounter_class": "amb"},
        {"encounter_class": "vr"},
        {"encounter_class": "obsenc", "time_limit_hours": 24},
    ],
}
```

or as JSON in an environment variable on the Celery workers:

```env
ENCOUNTER_AUTO_COMPLETE_RULES=[{"encounter_class": "amb"}, {"encounter_class": "vr"}, {"encounter_class": "obsenc", "time_limit_hours": 24}]
```

Allowed classes are `imp`, `amb`, `obsenc`, `emer`, `vr`, and `hh`.
`time_limit_hours` is optional and defaults to 0. No rules disables completion.
Invalid JSON, unknown classes or keys, negative or non-integer hours, and two rules
for one class fail startup validation. Restart workers after changing the rules.

The plug must be installed and enabled in both Beat and worker processes. It uses
the existing Celery Beat scheduler and registers one daily task at midnight in the
Celery timezone (`Asia/Kolkata` in CARE). No scheduler replacement is needed.

Each run applies across **all facilities**, including older open encounters. Only
`in_progress`, `on_hold`, and `discharged` encounters in the selected classes are
eligible. Creation time and any recorded period start must precede the midnight
cutoff minus the class's time limit. The limit is only checked at midnight, so with
a 24 hour limit an encounter is completed at the first midnight at least 24 hours
after it started (24 to 48 hours later). Missing starts are allowed; malformed starts
are skipped and logged.
Naive start timestamps are interpreted in the Celery timezone. Planned, terminal,
deleted, and post-cutoff encounters are excluded.

Completion appends status history with an automatic source and scheduled cutoff,
sets `updated_by` to null, fills a missing period end with the execution time, and
uses CARE's existing device and location cleanup. Each encounter is processed in
its own transaction with a row lock. Overlapping/repeated runs skip encounters
already completed. Transient database failures retry up to three times, keeping
the original cutoff; encounters committed before a failure are not changed again.
Any other failure rolls back that encounter, is logged, and the run continues with
the rest. There is no automatic catch-up for a missed Beat dispatch.

To run the focused tests from a CARE checkout with the plug installed and enabled:

```bash
python manage.py test encounter_auto_complete --settings=config.settings.test
```

### Installing plugs locally

To work on these plugs locally alongside CARE, use a local path-based plug configuration and install the repository in editable mode.

1. Clone this repository into the same development environment that hosts your CARE checkout.

   ```bash
   git clone git@github.com:10bedicu/care_state_hmis.git
   ```

2. Add the plugin entries to your CARE `plug_config.py` and point each one to the absolute path of your local clone.

   ```python
   from plugs.manager import PlugManager
   from plugs.plug import Plug

   plugs = [
       Plug(
           name="invoice_auto_balance",
           package_name="/absolute/path/to/care_state_hmis",
           version="",
           configs={},
       ),
       Plug(
           name="patient_demographics",
           package_name="/absolute/path/to/care_state_hmis",
           version="",
           configs={},
       ),
       Plug(
           name="encounter_hospital_identifier",
           package_name="/absolute/path/to/care_state_hmis",
           version="",
           configs={},
       ),
       Plug(
           name="encounter_access_authorization",
           package_name="/absolute/path/to/care_state_hmis",
           version="",
           configs={},
       ),
       Plug(
           name="appointment_invoice_payment",
           package_name="/absolute/path/to/care_state_hmis",
           version="",
           configs={},
       ),
   ]

   manager = PlugManager(plugs)
   ```

3. If your CARE checkout installs plugs through `plugs/manager.py`, temporarily switch the install command to editable mode by adding `-e` to the pip invocation, following the same approach used in other plug repositories.

   ```python
   subprocess.check_call([
       sys.executable,
       "-m",
       "pip",
       "install",
       "-e",
       *packages,
   ])
   ```

   > [!IMPORTANT]
   > Keep this change local to your development environment and do not include it in a pull request.

4. Install the configured plugs from your CARE repository.

   ```bash
   python install_plugins.py
   ```

5. Install this repository's development dependencies in the same Python environment and use the built-in validation commands while iterating.

   ```bash
   pip install -r requirements_dev.txt
   pip install -e .
   make lint
   make test
   tox
   ```

6. Restart or rebuild your CARE deployment using the normal workflow from the host CARE repository so local plug changes are picked up.

## Production Setup

To install these plugs from a Git repository instead of a local path, add them to your CARE `plug_config.py` using the repository URL.

```python
from plugs.manager import PlugManager
from plugs.plug import Plug

plugs = [
    Plug(
        name="invoice_auto_balance",
        package_name="git+https://github.com/10bedicu/care_state_hmis.git",
        version="@main",
        configs={},
    ),
    Plug(
        name="patient_demographics",
        package_name="git+https://github.com/10bedicu/care_state_hmis.git",
        version="@main",
        configs={},
    ),
    Plug(
        name="encounter_hospital_identifier",
        package_name="git+https://github.com/10bedicu/care_state_hmis.git",
        version="@main",
        configs={},
    ),
    Plug(
        name="encounter_access_authorization",
        package_name="git+https://github.com/10bedicu/care_state_hmis.git",
        version="@main",
        configs={},
    ),
    Plug(
        name="appointment_invoice_payment",
        package_name="git+https://github.com/10bedicu/care_state_hmis.git",
        version="@main",
        configs={},
    ),
]

manager = PlugManager(plugs)
```

For production deployments, pin `version` to a release tag or commit instead of `@main`.

For more detail on CARE plug installation, see the pluggable app configuration guide: <https://care-be-docs.ohc.network/pluggable-apps/configuration.html>.

## License

This project is licensed under the terms of the [MIT license](LICENSE).

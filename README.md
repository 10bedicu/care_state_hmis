# Care State HMIS Plugins

CARE backend plugin repository for State HMIS workflows.

This repository packages five backend plugins that can be installed together from a single source repository:

| Plugin | Purpose |
| --- | --- |
| `invoice_auto_balance` | Automatically balances issued invoices when completed payment reconciliations cover the invoice amount. |
| `patient_demographics` | Adds patient demographic extension fields such as related person, caste, and religion. |
| `encounter_hospital_identifier` | Assigns a hospital-facing encounter identifier and prevents it from being changed later. |
| `encounter_access_authorization` | Adds custom encounter authorization rules for restarting completed encounters. |
| `appointment_invoice_payment` | Creates and settles appointment-linked invoices when charge items are attached to bookings. |

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

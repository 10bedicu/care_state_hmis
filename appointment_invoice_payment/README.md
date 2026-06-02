# Appointment Invoice Payment Plugin

Automates invoice creation and payment reconciliation for appointment bookings once a charge item is attached.

## What It Does

- Listens to `TokenBooking` saves and processes bookings after a charge item is linked.
- Detects revisit scenarios and can replace the default appointment charge item with the revisit charge item definition configured on the schedule.
- Creates an invoice for a billable appointment charge item, syncs invoice items, and issues the invoice.
- Creates a matching `PaymentReconciliation` so the appointment invoice can be settled automatically.

## Configuration Notes

- `HMIS_INVOICE_ALLOW_REVISIT_ACROSS_DEPARTMENTS` defaults to `True`.
- When enabled, revisit lookup can reuse prior paid bookings across healthcare services in the same facility instead of limiting the check to the current schedule resource.

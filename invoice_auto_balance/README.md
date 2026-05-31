# Invoice Auto Balance Plugin

Balances issued invoices automatically after successful payment reconciliation.

## What It Does

- Listens to `PaymentReconciliation` saves for active, complete reconciliations.
- Aggregates payments and credit notes against the target invoice.
- Marks billed charge items as paid and moves the invoice to `balanced` when the invoice total is fully covered.
- Triggers account rebalancing after reconciliation processing completes.

## Configuration Notes

This plugin does not define plugin-specific settings in this repository.

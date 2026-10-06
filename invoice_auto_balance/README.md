# Invoice Auto Balance Plugin

Marks an issued invoice as balanced when its payments cover the full amount, so staff do not have to close it by hand.

## How It Works

The plugin checks each saved `PaymentReconciliation`. It ignores reconciliations that are not both `active` and `complete`.

For an issued invoice, it adds all completed payments and subtracts credit notes. If the remaining amount covers `invoice.total_gross`, the plugin marks the invoice's billed charge items as paid, records when they were paid, and changes the invoice status to `balanced`.

It also queues account rebalancing for every qualifying reconciliation, whether or not the invoice becomes balanced.

## Configuration

This plugin has no settings.

## Signals

| Signal | Sender | Handler | Purpose |
| --- | --- | --- | --- |
| `post_save` | `PaymentReconciliation` | `handle_payment_reconciliation_rebalance` | Balances a covered invoice and queues account rebalancing. |

## Routes

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe. |

## Notes

- Only invoices with the `issued` status can be balanced. Draft and already balanced invoices are skipped.
- An overpayment still counts as fully paid.
- A reconciliation without an invoice still queues account rebalancing.

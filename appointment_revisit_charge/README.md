# Appointment Revisit Charge Plugin

Applies a revisit charge when a patient returns within the follow-up period set on the schedule.

This plugin only chooses the charge item for the booking. CARE handles invoicing and payment processing.

## How It Works

The plugin checks a booking when a charge item is added. It ignores bookings without a charge item and updates that do not change the charge item.

For each booking, it finds the patient's most recent paid appointment that started on or before the new appointment. It ignores cancelled appointments and previous appointments that already used a revisit charge, so revisit discounts cannot be chained together.

If that appointment was paid within `Schedule.revisit_allowed_days`, the plugin replaces the usual charge item with the schedule's `revisit_charge_item_definition`. If the schedule has no revisit charge item definition, the booking has no charge item and the revisit is free.

The plugin leaves bookings outside the follow-up period unchanged. It also leaves a booking unchanged when its charge item has already been paid on an invoice.

## Configuration

| Setting | Default | Description |
| --- | --- | --- |
| `HMIS_ALLOW_REVISIT_ACROSS_DEPARTMENTS` | `True` | Lets an appointment in one department count as a revisit after a visit to another department in the same facility. When off, only appointments on the same schedule resource count. |

The follow-up period and revisit charge are set on each schedule in CARE through `Schedule.revisit_allowed_days` and `Schedule.revisit_charge_item_definition`.

## Signals

| Signal | Sender | Handler | Purpose |
| --- | --- | --- | --- |
| `post_save` | `TokenBooking` | `handle_appointment_revisit_charge` | Replaces the usual charge with the revisit charge when the booking qualifies. |

## Routes

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe. |

## Notes

- A schedule with a follow-up period but no revisit charge makes qualifying revisits free instead of using the normal price.
- The follow-up period includes its first and last day. It is measured in whole days from the earlier payment to the new appointment's start.

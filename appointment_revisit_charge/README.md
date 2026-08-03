# Appointment Revisit Charge Plugin

Applies the revisit charge item to an appointment booking once a charge item is attached.

## What It Does

- Listens to `TokenBooking` saves and processes bookings after a charge item is linked.
- Detects revisit scenarios and can replace the default appointment charge item with the revisit charge item definition configured on the schedule.

## Configuration Notes

- `HMIS_ALLOW_REVISIT_ACROSS_DEPARTMENTS` defaults to `True`.
- When enabled, revisit lookup can reuse prior paid bookings across healthcare services in the same facility instead of limiting the check to the current schedule resource.

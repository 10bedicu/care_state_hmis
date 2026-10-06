# Encounter Access Authorization Plugin

Lets the person who last updated a completed encounter reopen it, without giving that ability to everyone.

## How It Works

When CARE starts, the plugin registers its own encounter permission handler before CARE's default handler.

It changes only the rule for restarting an encounter. A restart is allowed for a superuser, or when all of the following are true:

- the user is the one recorded in `encounter.updated_by`
- the encounter is in a completed state
- the user still has `can_write_encounter` permission on that encounter

All other encounter permission checks continue to use CARE's normal rules.

## Configuration

This plugin has no settings.

## Signals

This plugin does not listen for signals. It registers its permission handler when CARE starts.

## Routes

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe. |

## Notes

- Because the rule uses `updated_by`, a later edit by someone else gives that person the ability to restart the encounter.
- This replaces CARE's normal restart rule; it does not add another option to it.

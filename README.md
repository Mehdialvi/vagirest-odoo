# VAGIREST Odoo ERP

Custom ERP development for VAGIREST / Daneshpad Alavi.

## Stack

- Odoo 17 Community
- PostgreSQL 15
- Docker

## Custom Addons

See:

`docs/ACTIVE_MODULES.md`

## Developer / AI Agent Instructions

Read these files before making changes:

1. `AGENTS.md`
2. `PROJECT_STATE.md`
3. Relevant documentation under `docs/`

## Production Safety

Production is currently running with a legacy Docker addon-volume
configuration.

Do not recreate production containers until the deployment configuration
has been normalized and tested.


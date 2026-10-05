# VAGIREST ERP — Current Project State

## Environment

Production ERP:
- Odoo 17 Community
- PostgreSQL 15
- Docker deployment
- Database: VAGIREST

Production containers:
- `odoo-project-web-1`
- `odoo-project-db-1`

A separate native-dashboard test environment currently exists.

## Source Control

This repository was created from the live production custom addon source.

Before creation of this repository, the VAGIREST custom addons were not
under a unified Git repository.

## Important Deployment Issue

The currently running production container's `/mnt/extra-addons`
mount does not appear to correspond cleanly to the named addon volume
declared in the current docker-compose.yml.

For that reason production containers must not yet be recreated from
docker-compose.yml.

Normalizing production deployment is a future controlled task.

## Current Functional Areas

The custom addon suite includes functionality for:

- CRM
- Customer receipts
- Inventory / QMS
- Invoice reports
- Jalali calendar
- Management dashboard
- Product naming
- Production records / QC / rework
- Unique customer phone validation

See:

`docs/ACTIVE_MODULES.md`

for the exact modules and installed versions captured from production.

## CRM Direction

VAGIREST CRM uses Odoo contacts as the persistent customer entity.

Sales interactions and purchase cycles may repeat over the life of a
customer, while customer history must remain linked to the same contact.

CRM development should therefore preserve separation between:

- Customer / Contact (`res.partner`)
- Sales opportunity (`crm.lead`)
- Activities
- Quotations / orders
- Repeat purchase cycles

## Immediate Technical Priorities

1. Establish Git as the source of truth for custom code.
2. Preserve a clean production baseline.
3. Audit custom module dependencies and architecture.
4. Establish safe staging/development workflow.
5. Normalize Docker/addon volume deployment.
6. Move future code changes through Git + review + testing.
7. Stop using production as the primary development workspace.


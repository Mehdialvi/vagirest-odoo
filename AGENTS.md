# VAGIREST Odoo Development Rules

## Platform

- Odoo: 17 Community
- PostgreSQL: 15
- Production database: VAGIREST
- Production runs with Docker
- Custom addons are currently loaded from `/mnt/extra-addons`

## Critical Production Safety Rules

1. Never modify the production database without explicit approval.
2. Never run SQL UPDATE, DELETE, TRUNCATE, DROP, or ALTER against production without explicit approval.
3. Prefer Odoo ORM and module migrations over direct SQL.
4. Never run `docker compose down` on production without explicit approval.
5. Never recreate the production Odoo web container without verifying its addon volume first.
6. Never delete or replace a Docker volume without explicit approval.
7. Always create and verify a backup before production deployment.
8. Never store passwords, API keys, tokens, certificates, or secrets in Git.
9. Show the diff before a production deployment.
10. Test module upgrades outside production first whenever possible.

## Important Current Runtime Warning

The currently running production Odoo container mounts `/mnt/extra-addons`
from an existing Docker volume whose live source must be preserved.

Do NOT assume that recreating the container from the current compose file
will reconnect to the same addon volume.

Until the deployment architecture is normalized:

- no `docker compose down`
- no `docker compose up --force-recreate`
- no container recreation
- no addon volume deletion

without first auditing the live mounts.

## Repository Layout

Custom modules:

`custom_addons/`

Documentation:

`docs/`

Operational scripts:

`scripts/`

## Development Workflow

For every feature or fix:

1. Read AGENTS.md.
2. Read PROJECT_STATE.md.
3. Read the relevant documentation under `docs/`.
4. Inspect the existing implementation before changing code.
5. Keep the change narrowly scoped.
6. Use a Git branch or worktree for significant changes.
7. Run syntax/static checks.
8. Run relevant Odoo tests when available.
9. Review the diff.
10. Update documentation when business behavior changes.
11. Commit the tested change.
12. Deploy to staging/test environment.
13. Validate behavior.
14. Backup production.
15. Deploy the approved commit to production.

## Odoo Rules

- Preserve compatibility with Odoo 17 Community.
- Do not patch Odoo core.
- Implement custom behavior in custom addons.
- Use model inheritance rather than modifying core models.
- Keep access rights and record rules explicit.
- Avoid unnecessary sudo().
- Avoid raw SQL unless there is a strong documented reason.
- Ensure upgrades are idempotent when possible.

## Data Integrity

Existing VAGIREST production records must be treated as authoritative data.

Any migration that:
- changes identifiers,
- merges contacts,
- deletes records,
- changes stock quantities,
- modifies accounting data,
- changes lots,
- changes manufacturing history,
- or modifies QC history

requires a dedicated migration plan and explicit approval.


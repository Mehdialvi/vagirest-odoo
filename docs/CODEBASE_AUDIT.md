# VAGIREST Odoo 17 codebase audit

Audit date: 2026-10-05 (Asia/Tehran). Scope: architecture, security, maintainability, data integrity, testing, installation, upgrades, deployment, and rollback.

## Scope and evidence

- Repository root: /workspace/vagirest-odoo.
- Branch: work. HEAD: dc5d927c1a10cdadeef835d34cfc15f78f60a147.
- Read AGENTS.md, PROJECT_STATE.md, README.md, docs/ACTIVE_MODULES.md, the CRM README, and the production checksum inventory.
- Inspected the complete tracked inventory: 174 files before this report; nine addons; 61 non-backup Python files, 37 non-backup XML files, ACL CSVs, JavaScript, CSS, initializers, manifests, and three binary assets. There are 24 new custom models. Binary assets were inventoried and hashed, not executed.
- Identified and inspected 59 tracked legacy/backup/disabled files, including initializer and manifest differences. These are distinguished from loaded code.
- Python AST parsing and XML well-formedness checks passed for the inspected .py/.xml files. All manifest data paths exist. These are static checks, not Odoo behavioral tests.
- The initial working tree was clean. This audit creates only docs/CODEBASE_AUDIT.md. No source, manifests, database records, deployment configuration, or baseline checksums were changed. No commit, push, service startup, upgrade, or production connection was performed.
- Local comparison of docs/PRODUCTION_BASELINE_SHA256.txt: 194 entries; 168 existing files match their recorded SHA-256; 26 historical backup paths are absent; zero hash mismatches. This verifies the available checkout against the recorded list, not the current production filesystem.
- Earlier onboarding verified installation of seven addons in vagirest_dev, an HTTP 200 login form, and an ORM smoke check for contact creation, normalized phone uniqueness, and formatting-only updates. Retained logs corroborate that evidence. Dashboard installation failed; Customer Receipts was left uninstalled. Both development containers are currently stopped, so no live database validation was repeated during this audit.
- Production container mounts, user memberships, private data, database constraints, backups, load, and network controls were not inspected. Static defects below are confirmed source observations; exploitability, existing corrupt data, and performance magnitude require isolated staging tests.

Severity definitions: Critical means a path threatens stock/QC authority or production recovery; High means a serious security, integrity, installation, or operational defect; Medium means material reliability, correctness, or maintenance risk; Low means limited-impact housekeeping or metadata issues. Severity describes potential impact, not evidence that production has already been damaged.

## Module and dependency architecture

An arrow below means “depends on.” The custom dependency graph has no declared cycle.

~~~mermaid
graph TD
  Receipts[vagirest_customer_receipts] --> Dashboard[vagirest_native_dashboard]
  Receipts --> Jalali[vagirest_jalali_calendar]
  Dashboard --> Jalali
  Jalali --> QMS[vagirest_inventory_qms]
  Jalali --> Production[vagirest_production_record]
  QMS --> Production
  CRM[vagirest_crm]
  Invoice[vagirest_invoice_report]
  Naming[vagirest_product_naming]
  Phone[vagirest_unique_phone]
~~~

| Addon / manifest version | Standard dependencies | Custom dependencies | Responsibility and inheritance | Earlier isolated install |
|---|---|---|---|---|
| vagirest_crm / 17.0.1.2.0 | crm, sale_management, contacts, stock, mail, utm | None | Extends res.partner and crm.lead; owns vagirest.product.interest | Installed |
| vagirest_customer_receipts / 17.0.1.1.0 | sale, account, mail | Jalali, Native Dashboard | Owns receipt, balance, and balance-line models; extends res.partner; reads bank statements/orders | Not installed: dashboard hook blocks dependency |
| vagirest_inventory_qms / 17.0.3.4.0 | base, stock, mail | Production Record | F01 requests, F02 supplier receipts/QC, F04 deliveries; extends product.template | Installed; stock workflows not functionally verified |
| vagirest_invoice_report / 17.0.1.2.0 | account, web, sale | None | QWeb sale/invoice PDFs; extends account.move and sale.order for date conversion | Installed; PDF output untested |
| vagirest_jalali_calendar / 17.0.1.5.0 | sale | Production Record, Inventory QMS | Extends production, QC, F01/F02/F04, stock.picking, stock.move.line, stock.lot, sale.order | Installed only after explicit product_expiry install |
| vagirest_native_dashboard / 17.0.1.0.2 | spreadsheet_dashboard_sale | Jalali | Extends spreadsheet.dashboard, sale.order, SQL-backed sale.report; generates dashboards in post_init_hook | Failed: company 3 / user 19 prerequisite |
| vagirest_product_naming / 17.0.1.0.0 | product, stock, mrp, sale | None | Extends product.product display_name | Installed |
| vagirest_production_record / 17.0.3.17.0 | base, stock, mail, contacts, crm, sale, spreadsheet_dashboard, hr, hr_attendance, hr_expense | None | Production, QC, rework, correction requests/history; overrides stock CRUD and hr.expense | Installed; production/QC/rework transfers untested |
| vagirest_unique_phone / 17.0.1.0.0 | base, contacts | None | Extends res.partner create/write and stored normalization | Installed; limited smoke check passed |

Cross-module coupling:

- Calendar conversion is packaged together with warehouse/manufacturing adapters. Receipts imports Jalali utilities directly, so finance and dashboards transitively install production, QC, warehouse, HR, and attendance modules.
- Receipts imports the personal-dashboard group in ACLs, record rules, and views, and attaches menus to the standard spreadsheet-dashboard root. The dashboard dependency is real, not just an unused manifest entry.
- Native Dashboard reads the stored sale.order.date_order_jalali field introduced by Jalali through its sale.report SQL extension.
- Production Record changes global menus belonging to Contacts, HR, Attendance, Expenses, dashboards, and Apps. It also changes base stock and expense CRUD behavior for users carrying its inventory-viewer group.
- Multiple loaded classes extend the same production/QC/rework models. Runtime method chains include correction_workflow, rework auto-creation, correction requests, rework security, and company/sequence fixes. Read the entire inheritance chain before changing an action.
- CRM, phone validation, and Receipts all extend res.partner; Invoice, Jalali, and Native Dashboard all extend sale.order. No copied Odoo core is present, but composition and upgrade testing are required.

## Security and elevated-access inventory

| Area | Existing controls | Gaps / composition concerns |
|---|---|---|
| Production / QC | Operator and QC roles; ERP implies both; operator stock-viewer access; QC record/line uniqueness; action group checks | No global company rules; no submitted-production write lock; no QC-line immutability |
| Rework | Read-only/create restrictions through ACLs; server write guards; unlink prohibited; direct cancellation disabled | Caller-controlled bypass flags; company-less correction requests; no global company rules |
| F01/F04 | Ownership group rules; warehouse role can see all; state write guards | No company intersection; F01 unlink unrestricted by state; F04 line create unguarded; client context bypass |
| F02 | F02 role gets read/write/create; QC action group checks; completed deletion guard | No record rules or company field; no record/line write guard; QC role alone lacks F02 ACL |
| Receipts / balances | Global company rules; personal assignment/creator rules; manager rules; field groups; match validation | Finance group owned by dashboard; assignment rule crosses company/currency; aggregates use sudo |
| CRM catalog | All internal users read; sales managers manage product interests; unique code | Scope is global; inherited contact/lead rules determine confidentiality |
| Native dashboard | Global owner/company rules plus dashboard group_ids | Creator-based filtering, hardcoded targets, group provisioning only for one user, parent-menu conflict |
| Stock / expenses | Production addon denies stock.picking/move/move.line and hr.expense CRUD to viewer users unless ERP/superuser | Does not similarly guard stock.quant or stock.lot; group combinations need explicit tests |

Static sudo() call sites: Production Record 95, Inventory QMS 27, Customer Receipts 1; all other addons 0. These counts include overridden method implementations in loaded files, not necessarily 123 distinct executed operations. Receipts also has compute_sudo=True fields; related fields can compute with elevation under Odoo defaults. Dashboard post_init_hook executes in an installation context even without explicit sudo().

No direct cursor execute/executemany calls, raw SQL DML, explicit database commit/rollback calls, or direct stock.quant quantity writes were found in current addon code. Native Dashboard models/sale_report.py constructs fixed SQL SELECT/GROUP BY fragments through Odoo's reporting API. This is SQL-backed reporting, not user-interpolated DML; no injection path was identified. There are no custom HTTP controllers in this repository. Absence of those patterns is not a general security certification.

## Findings

### F01 — Critical: production addon-volume recovery is not established

- Module: repository/deployment; all addons.
- File/function: AGENTS.md “Important Current Runtime Warning”; PROJECT_STATE.md “Important Deployment Issue”; README.md “Production Safety.”
- Problem: documents explicitly state the live production /mnt/extra-addons mount does not cleanly match the current compose declaration. No tracked compose, deployment script, or tested rollback procedure exists here.
- Why it matters: recreating the web container may attach an empty or wrong addon volume, prevent Odoo registry loading, or serve a different source baseline. A source-only rollback may also be incompatible with an upgraded database.
- Recommended fix: in a separately authorized production inspection, inventory exact mount sources and ownership without mutation; verify recovery of database, filestore, addon filesystem, image, and configuration together; rehearse on staging before normalizing deployment.
- Data migration: not inherently required; normalization must preserve volumes and database state. Restoration or upgrade rollback needs a dedicated recovery plan.

### F02 — Critical: submitted production records and lines remain writable

- Module: vagirest_production_record.
- File/function: models/production_record.py, VagirestProductionRecord.create/action_submit_to_qc and VagirestProductionRecordLine.create/write; loaded extensions in correction_workflow.py and correction_request.py.
- Problem: there is no write override on the production parent to enforce submitted/cancelled immutability. Line write only checks a changed product's suitability, not parent state. Line create has no parent-state guard. ACLs give operators parent/line write/create access. readonly view/model fields do not enforce generic RPC immutability.
- Why it matters: a permitted ORM caller can change quantities, batch/date, metadata, or workflow fields after stock posting without a reversal. Stored QC related fields and generated_lot can then differ from completed stock moves and actual stock.lot names.
- Recommended fix: enforce state and field-level rules in create/write/unlink on parent and children, reject user-supplied system/audit fields, and route changes through authorized private transition helpers. Add negative RPC/ORM tests.
- Data migration: possibly; inspect historical documents against pickings/lots/QC snapshots before repairing discrepancies. Do not rewrite historical lots automatically.

### F03 — Critical: F02 receipt and inspection lines lack server-side state/role protection

- Module: vagirest_inventory_qms.
- File/function: models/raw_material_receipt.py, VagirestRawMaterialReceipt and VagirestRawMaterialReceiptLine; views/raw_material_receipt_views.xml; security/ir.model.access.csv.
- Problem: the parent has no write guard and the line class has no create/write/unlink guards. F02 users can write inspection_result, quantities, products, lots, and parent system fields through ORM regardless of receipt state. Only action_finalize_qc checks the QC role; editing the decision inputs does not.
- Why it matters: the receipt and QC history can be changed after real movements. A receiver can prepare/alter QC outcomes without inspector authority, defeating separation of duties.
- Recommended fix: enforce receiver versus inspector permissions and parent-state immutability on every CRUD path; sanitize creation defaults and audit fields; permit corrections only through approved reversal actions.
- Data migration: possibly; reconcile F02 histories, quantities, lots, and linked pickings before enforcing new invariants.

### F04 — High: workflow context flags are supplied by clients

- Module: vagirest_production_record; vagirest_inventory_qms.
- File/function: models/qc_record.py:513 write (allow_qc_correction); models/rework_security.py write methods (allow_rework_workflow_write / allow_rework_qc_workflow_write); models/rework_correction_request.py write methods (allow_rework_request_system_write / allow_rework_qc_request_system_write); QMS models/material_request.py parent/line guards (allow_f01_workflow_write / allow_f04_workflow_write).
- Problem: setting those context keys skips business guards. RPC callers control context, so the keys are not trusted proof that a controlled action authorized the write.
- Why it matters: authenticated users with underlying write ACLs can bypass state locks or alter review/audit fields. Record rules still apply to non-sudo writes; this finding is a business-authorization bypass, not an assertion that every user becomes a superuser.
- Recommended fix: remove context-only authorization. Validate caller access, role, company, state, target identity, and allowed fields in private transition helpers; use narrowly scoped elevation after validation.
- Data migration: usually no schema migration; existing audit values may require a reviewed integrity investigation.

### F05 — Critical: QC decisions can be changed through their child model

- Module: vagirest_production_record.
- File/function: models/qc_record.py, VagirestQCRecord.write and VagirestQCRecordLine; security/ir.model.access.csv.
- Problem: parent write blocks most changes in done state, but QC lines have no parent-state create/write/unlink enforcement. QC users have line write access. A draft QC parent also accepts system fields such as state and picking references without a field whitelist.
- Why it matters: decision totals may be edited after approval while completed approved/rework/rejected transfers remain unchanged. Altering a child directly does not invoke the parent's write guard.
- Recommended fix: add child state/parent-link checks and parent system-field protection; require validated submission and controlled correction transitions; test direct child RPC writes.
- Data migration: possibly; compare posted decision quantities with the original transfer lines before correcting any history.

### F06 — High: operational models lack company isolation

- Module: vagirest_production_record; vagirest_inventory_qms.
- File/function: both security/security.xml files; production_record.py, qc_record.py, correction_workflow.py, correction request models, raw_material_receipt.py.
- Problem: production/QC/F02 and legacy/correction models lack a company field; rework and F01/F04 have company fields but no global company record rule. Group rules giving warehouse/QC/ERP “all” access contain no company intersection. Operational relational fields generally lack check_company enforcement.
- Why it matters: users can see custom documents outside their permitted companies. Elevated stock actions can select a company from ambient context or hardcoded locations rather than an authorized document scope. with_company() is not a record-access control.
- Recommended fix: define required document company and stored related child company fields; backfill using verified original pickings/lots; add global allowed-company rules and relational consistency checks; validate allowed companies before sudo().
- Data migration: yes for new required company fields and legacy data; ambiguous or conflicting source companies need manual review.

### F07 — High: reversal helpers use ambient company instead of transaction company

- Module: vagirest_production_record.
- File/function: models/correction_workflow.py:_available_quantity and _reverse_done_picking; rework_correction_request.py:action_approve calls this helper.
- Problem: the shared reversal helper filters quants and creates reverse pickings/moves under record.env.company. Rework documents can have their own company_id, and their forward transfer uses that company.
- Why it matters: switching the active company before correction can cause false insufficient-stock errors or company mismatch failures; elevation makes ambient scope unsafe even when Odoo's stock consistency checks block some combinations.
- Recommended fix: derive company from the original picking, compare it with document company, verify caller access, and keep all availability and reversal operations in that company.
- Data migration: code-only normally; audit any existing reversals with mismatched document/picking companies.

### F08 — High: warehouse and operation IDs are hardcoded throughout stock workflows

- Module: vagirest_production_record; vagirest_inventory_qms.
- File/function: production_record.py:_get_production_picking_type (type 50, input location 40); qc_record.py:action_submit_decision (types 51/52/53; locations 40/41/76/77); rework_record.py picking-type/transfer helpers (warehouse 3; locations 76/40); raw_material_receipt.py:_locations and action_mark_received (locations 40/74/75/77; incoming type 11).
- Problem: integer identities encode production warehouse topology. Some paths check company/usage/location; others only check existence, and the active rework picking-type search lacks an explicit company domain.
- Why it matters: a fresh database installs but cannot exercise production/QC/F02/rework. IDs can be absent or mean different things after restoration, migration, or additional companies.
- Recommended fix: add explicit per-company operation/location configuration with stable XML IDs for demo fixtures, validate topology and ownership, and preserve existing configured operational records.
- Data migration: configuration mapping required for production; do not renumber or recreate stock locations, warehouses, or picking types.

### F09 — High: dashboard company ID 3 is an installation prerequisite

- Module: vagirest_native_dashboard.
- File/function: setup_dashboards.py:228 post_init_hook.
- Problem: company = env['res.company'].browse(3).exists(); the hook raises if that record is absent and builds every generated dashboard for that company.
- Why it matters: fresh installation failed in the isolated database with “Expected company 3 and salesperson 19 with company access.” A database where ID 3 names a different company would generate dashboards for that company without checking business identity.
- Recommended fix: configure the intended company explicitly; allow installing the addon without generating dashboards; use a separately authorized, idempotent provisioning action per company.
- Data migration: existing generated dashboards and their stored domains need a reviewed mapping/reconfiguration; preserve their record and XML IDs.

### F10 — High: dashboard user ID 19 and creator identity are hardcoded

- Module: vagirest_native_dashboard.
- File/function: setup_dashboards.py:230 post_init_hook and build_snapshot.domain; models/sale_report.py:_select_additional_fields.
- Problem: the hook browses user 19, grants that user the personal-dashboard group, and generates dashboards with a fixed personal label. The personal domain filters sale.order.create_uid / sale.report.vagirest_creator_id, not the assigned salesperson user_id.
- Why it matters: fresh install is blocked; another database may grant access to an unintended user. Creator-based reports can diverge from salesperson responsibility after reassignment or imports.
- Recommended fix: select and validate owners explicitly by company; define whether the business metric means creator or salesperson; keep both identities if needed; never grant a numeric-ID user access by assumption.
- Data migration: group membership and dashboard-domain mapping may be required; review ownership rather than mass reassignment.

### F11 — High: Customer Receipts is coupled to dashboard provisioning

- Module: vagirest_customer_receipts.
- File/function: __manifest__.py; security/ir.model.access.csv, rules.xml, finance_privacy.xml; views/receipts.xml and customer_balance.xml.
- Problem: finance ACLs/rules/views reference vagirest_native_dashboard.group_personal_dashboard; menus use the spreadsheet root. Thus the dependency is functional and its hardcoded hook prevents receipt installation.
- Why it matters: core receipt/balance tracking cannot be installed independently, and UI/dashboard refactors can affect financial access.
- Recommended fix: move shared finance/follow-up roles to a small foundation/finance addon and place receipt menus under an appropriate finance root. Retain an optional dashboard integration addon.
- Data migration: yes for safe XML-ID/group ownership transition and membership preservation. Simply deleting the dependency would leave unresolved external IDs.

### F12 — High: Jalali omits its product_expiry dependency

- Module: vagirest_jalali_calendar.
- File/function: __manifest__.py; models/inventory_dates.py:_compute_move_line_jalali_dates / _compute_lot_jalali_dates; views/inventory_views.xml.
- Problem: expiration_date, use_date, removal_date, and alert_date are used without declaring product_expiry. The fresh registry failed on stock.move.line.expiration_date.
- Why it matters: install/upgrade reliability depends on unrelated pre-existing modules. Odoo fails before a usable registry is established.
- Recommended fix: declare product_expiry or move expiration adapters/views into a separate addon depending on it; add fresh-install and upgrade regression tests.
- Data migration: generally no custom record migration; review the effect of installing product_expiry and retained expiration settings on staging.

### F13 — High: F01/F04 reference a missing compute method

- Module: vagirest_inventory_qms.
- File/function: models/material_request.py:106 and :485 warehouse_responsible_id; views/material_request_views.xml:116 and :303.
- Problem: both models set compute="_compute_warehouse_responsible_id", but no loaded addon defines that method.
- Why it matters: reading the field to open either form will attempt an undefined method. Successful registry initialization or a login page does not verify these forms.
- Recommended fix: define the intended responsibility source and implement a batched compute, or replace the field with an explicit valid related field; add form-read tests.
- Data migration: normally no, since these computed fields are not stored; configuration may be needed to define responsibility.

### F14 — High: F04 stock checks do not aggregate repeated demand or normalize UoM

- Module: vagirest_inventory_qms.
- File/function: models/material_request.py:1174 action_finalize_delivery; :932 _reverse_done_picking; :719 _available_quantity.
- Problem: availability is compared per line, not total product/lot/location demand. Quant quantities use product base UoM while delivery quantities use editable line uom_id. Multiple lines can independently pass against the same availability.
- Why it matters: two lines requesting six units each can both pass with ten units available. Unit mismatches and unchecked aggregate demand risk over-delivery or negative stock.
- Recommended fix: aggregate requirements by company/product/lot/source in base UoM, use Odoo UoM conversions/rounding, revalidate all invariants at finalization, and test duplicate lines and alternate UoMs.
- Data migration: potentially; reconcile historical F04 delivered quantities/pickings if discrepancies are found.

### F15 — High: F04 readiness is not a complete finalization invariant

- Module: vagirest_inventory_qms.
- File/function: models/material_request.py:617 action_mark_ready; :1174 action_finalize_delivery; VagirestWarehouseDeliveryLine CRUD.
- Problem: action_mark_ready lacks an explicit initial-state check; line create has no parent-state guard; draft line write allows product/UoM/request_line_id changes despite readonly UI fields. Finalization does not repeat readiness checks for over-request quantities, serial-unit limits, lot/product consistency, or source/destination usage and company.
- Why it matters: data can change or be injected between ready and finalization. UI domains do not enforce relational consistency, and request_line_id can point at an unrelated request line.
- Recommended fix: guard line create/write/unlink and both old/new parents, bind each line to its F01 request/product/UoM, validate state transitions and all stock constraints again before posting.
- Data migration: possibly; validate existing F01/F04 associations and completed lines before adding constraints.

### F16 — High: posted F01 evidence can be deleted

- Module: vagirest_inventory_qms.
- File/function: security/ir.model.access.csv (base.group_user full CRUD on F01); models/material_request.py, VagirestMaterialRequest has no unlink override.
- Problem: owners and warehouse users with matching rules can delete a submitted/received F01. An existing linked F04 may block deletion through its ondelete='restrict', but earlier submitted states have no such protection.
- Why it matters: the request/audit history can disappear before delivery exists. Parent deletion cascades to lines and does not rely on the child's UI lock.
- Recommended fix: restrict unlink to unsubmitted drafts with no downstream evidence; retain cancellation records; test cascade and role behavior.
- Data migration: no routine schema change; historical deletion cannot be reconstructed without backup/audit evidence.

### F17 — High: stock posting and approvals lack demonstrated concurrency safety

- Module: Production Record, Inventory QMS, Unique Phone.
- File/function: production/QC/rework submit actions; F01 action_create_f04; F02/F04 posting/reversal actions; all correction-request action_submit_request methods; res_partner.py create/write.
- Problem: code checks state, existing picking, duplicate request, or current availability and then writes without a document lock, atomic claim, or equivalent database uniqueness for most operations. Production/QC duplicate-request searches also run with requester visibility, so another user's request may be hidden.
- Why it matters: simultaneous calls can race into duplicate transfers, approvals, requests, or contacts. Odoo's stock/constraint internals prevent some failures but do not establish business-operation idempotency.
- Recommended fix: serialize transitions at the document boundary using supported transactional locking/atomic claims; apply reviewed unique constraints where suitable; query duplicate workflow evidence independently of requester visibility only after access validation; add real two-transaction tests.
- Data migration: likely duplicate cleanup before new constraints; never delete stock/QC history merely to satisfy uniqueness.

### F18 — High: custom reversals do not preserve standard return-move relationships

- Module: vagirest_production_record; vagirest_inventory_qms.
- File/function: correction_workflow.py:_reverse_done_picking; raw_material_receipt.py:_reverse_done_picking; material_request.py:_reverse_done_picking.
- Problem: reverse moves are constructed manually with swapped locations; no origin_returned_move_id or standard stock-return wizard flow is used. They record text origin and selected document links instead.
- Why it matters: inventory quantities may reverse while standard return traceability, valuation relationships, costing, packages/owners, or downstream routes differ. This is a staging validation risk, not proof that all existing valuation is incorrect.
- Recommended fix: evaluate supported stock return APIs, retain original-move links, and test costing/valuation plus lot, package, owner, reservation, backorder, and downstream-consumption cases.
- Data migration: possibly for return associations and reconciliation; any valuation correction requires an approved accounting migration.

### F19 — High: F02 company, stock availability, and role design are incomplete

- Module: vagirest_inventory_qms.
- File/function: raw_material_receipt.py:_locations, _create_and_validate_picking, action_finalize_qc; security/ir.model.access.csv.
- Problem: document company is absent and stock company is inferred from hardcoded locations. Unlike production QC, F02 finalization has no aggregate available-stock precheck. Only the F02 group has custom model ACLs; QC role alone has no F02 access.
- Why it matters: topology controls company implicitly; consumed/input stock can be overprocessed; granting inspectors receiver access to make the UI work also grants receiver edits, worsening F03.
- Recommended fix: define company-scoped receiver and inspector ACLs/rules, validate topology and source quantities, and separate editable fields/actions by role.
- Data migration: yes for company backfill; inspect receiver/QC assignments and existing receipt/stock consistency.

### F20 — High: phone uniqueness is visibility-dependent and race-prone

- Module: vagirest_unique_phone.
- File/function: models/res_partner.py:74 _vagirest_find_phone_conflict; :112 create; :150 write.
- Problem: conflict search uses the caller's record rules. Hidden contacts are excluded. Search-before-write is not a database uniqueness guarantee, and no shared constraint spans phone and mobile.
- Why it matters: different users/companies or concurrent transactions can create duplicate contact identities even though the limited smoke test passes. The algorithm also assumes Iranian prefixes for any ten-digit number and does not model extensions/country explicitly.
- Recommended fix: define uniqueness scope and numbering policy; implement a secure normalized-number registry or transactional constraint spanning both fields; provide a privacy-preserving error for hidden conflicts; preserve shared-phone exceptions.
- Data migration: yes if enforcing a stronger invariant; produce a read-only duplicate report and approve contact merges separately.

### F21 — High: operational balances have mutable historical inputs

- Module: vagirest_customer_receipts.
- File/function: models/balance.py:_compute_balance; CustomerBalance / BalanceLine CRUD; security/ir.model.access.csv.
- Problem: a “sale” entry reads live sale.order.amount_total even for draft/sent quotations, relying on manager attestation. Managers can edit/delete verified balances and their lines without a versioned verification record; these models do not inherit mail.thread.
- Why it matters: subsequent quotation changes retroactively change the operational debt report, and historical opening balances/adjustments lack durable approval evidence. The UI explicitly says this is follow-up tracking, not the accounting ledger.
- Recommended fix: choose a documented posted-accounting or immutable attested-event basis; capture amount/currency/date/evidence/version at approval; use append-only corrections and a review history while keeping operational and accounting purposes explicit.
- Data migration: yes if introducing snapshots/versions; reconcile opening balances and prior receipts to avoid double counting.

### F22 — Medium: receipt assignment rule is not scoped to its company/currency

- Module: vagirest_customer_receipts.
- File/function: security/rules.xml:receipt_personal_rule.
- Problem: read access follows partner_id.vagirest_balance_ids.followup_user_id across every balance for the partner without matching receipt company or currency.
- Why it matters: the global company rule still blocks unauthorized companies, but a multi-company user assigned in one company may read that customer's receipts in another allowed company beyond the intended assignment.
- Recommended fix: express assignment at the receipt's company scope and define whether assignment spans currencies; test users with two allowed companies and distinct assignments.
- Data migration: usually no; existing assignments may require review if scope changes.

### F23 — Medium: elevated aggregate reporting needs an explicit privacy contract

- Module: vagirest_customer_receipts.
- File/function: models/balance.py:_compute_balance; receipt.py eligible_for_collection; security/finance_privacy.xml.
- Problem: balances deliberately use sudo()/compute_sudo to read bank/receipt details, while financial fields and raw accounting models are restricted.
- Why it matters: this can be a legitimate aggregate-only design, but must prove that personal users receive only assigned approved aggregates, not raw bank details, names, attachments, or exception messages. Global finance-only deny rules can also block a manager who carries that group.
- Recommended fix: document the allowed outputs, test reads/exports/searches/report routes and attachments under actual role combinations, and review finance-only group assignment explicitly.
- Data migration: normally no; group-membership corrections may be required.

### F24 — Medium: balance status filtering performs a full Python scan

- Module: vagirest_customer_receipts.
- File/function: models/balance.py:_search_status and _compute_balance.
- Problem: searching status loads every visible balance, computes each balance, queries receipts separately, and filters IDs in Python. The compute validates lines and can raise on stale/cancelled order links.
- Why it matters: debtor filtering grows with the entire visible portfolio and receipt volume; one inconsistent link can make a list/report unreadable.
- Recommended fix: batch aggregate queries, index scoped inputs, define snapshot/freshness semantics, and expose invalid-input status separately from raising inside a read compute. Benchmark representative staging data.
- Data migration: possibly if adding stored summaries/snapshots; otherwise no.

### F25 — High: new production/QC correction buttons omit a required reason

- Module: vagirest_production_record.
- File/function: correction_request.py:589 action_request_correction; qc_correction_request.py:567 action_request_qc_correction; request models' reason fields.
- Problem: these actions eagerly create a persistent request without reason, while reason is required and no default is provided. They return a form only after creation.
- Why it matters: creating a new request is expected to fail required-field validation before the user can enter the reason. The newer rework request actions avoid this by opening an unsaved form with defaults.
- Recommended fix: use an unsaved form or a wizard that collects the reason before creation, matching the rework pattern; add first-request button tests.
- Data migration: no expected migration.

### F26 — Medium: legacy correction evidence remains editable after confirmation

- Module: vagirest_production_record.
- File/function: correction_workflow.py, VagirestProductionLegacyCorrection / Line and VagirestQCLegacyCorrection / Line.
- Problem: confirmation checks role/state/reason/quantities but neither parent nor line implements post-confirmation write guards. ERP ACLs permit write/create. Legacy corrections record alternate evidence rather than changing stock or original quantities.
- Why it matters: confirmed reasons and corrected values can later change, weakening the intended quality audit trail; consumers need a clear policy for original versus corrected history.
- Recommended fix: freeze confirmed evidence, use append-only superseding corrections, validate original-line ownership, and define which reporting views surface approved corrections.
- Data migration: possibly for versioning/ownership validation; preserve existing evidence.

### F27 — Medium: rework approvals and audit history have uneven safeguards

- Module: vagirest_production_record.
- File/function: rework_record.py:action_submit_decision; rework_correction_request.py action_approve/action_reject; correction_workflow.py direct ERP actions.
- Problem: original QC rejects operator self-inspection, but rework QC has no equivalent operator-versus-inspector check. ERP self-approval is explicitly allowed with a note in request approvals; some rejection/direct-correction paths use different policies.
- Why it matters: mixed group memberships can weaken separation of duties across workflow stages. This is a policy inconsistency requiring business confirmation, not a claim that documented ERP override authority is inherently wrong.
- Recommended fix: define one role/override matrix for production, QC, rework, cancellation, and correction, and test mixed-role users. Preserve explicit emergency authority with durable reasons.
- Data migration: no ordinary schema change; approval history should be retained, and role assignments may need review.

### F28 — Medium: inventory “viewer” restrictions are incomplete and broad

- Module: vagirest_production_record.
- File/function: models/stock_security.py, expense_security.py; security/ir.model.access.csv.
- Problem: viewer ACLs add read permission but do not revoke permissions from other groups. CRUD guards cover pickings/moves/move lines, not stock.quant or stock.lot. Expense writes are banned whenever the user has viewer status and is not ERP.
- Why it matters: a viewer who also has stock rights may retain quant/lot mutation access; legitimate expense/stock workflows for mixed-role users can also fail unexpectedly.
- Recommended fix: define intended group combinations and inventory mutation boundaries; test stock adjustment, lot editing, stock routes, and expense workflows before changing global overrides.
- Data migration: generally no; group assignment changes may be required.

### F29 — Medium: manufacturing visibility controls replace unrelated core menus

- Module: vagirest_production_record; impacts Native Dashboard and Customer Receipts.
- File/function: views/operational_menu_restrictions.xml.
- Problem: six core menu group lists are replaced using (6, 0, ...), including the dashboard root restricted to system/ERP groups. Native dashboards and receipts grant sales-manager/personal access without ensuring that root-menu access.
- Why it matters: users can hold model access but lose navigation; upgrades overwrite other menu customizations. Hiding menus does not restrict RPC access.
- Recommended fix: move organization-wide UI policy to an optional access addon, preserve intended existing groups, and test navigation and actual model permissions separately.
- Data migration: no business-data migration; menu/group metadata may need controlled restoration.

### F30 — Medium: dashboard generation is not an upgrade-safe provisioning service

- Module: vagirest_native_dashboard.
- File/function: setup_dashboards.py:post_init_hook and build_snapshot.
- Problem: the hook unconditionally creates a group, dashboard copies, and ir.model.data entries. It has no lookup/update strategy for reruns. post_init_hook runs on installation, not as an automatic dashboard refresh for every module upgrade. Templates assume pivot IDs 11/12, spare IDs 13/14, sheet “Data,” formula/cell layouts, and exact labels.
- Why it matters: manual reruns can duplicate records or collide on XML IDs; upgraded templates can fail or produce stale/misaligned dashboards. Existing generated dashboards will not automatically acquire code changes.
- Recommended fix: introduce explicit idempotent provisioning with schema/template validation, versioned updates, and preservation of user customizations.
- Data migration: yes for existing snapshots and generated metadata if behavior changes.

### F31 — Medium: dashboard currency labels depend on numeric currency IDs

- Module: vagirest_native_dashboard.
- File/function: setup_dashboards.py:198 apply_display_settings.
- Problem: IRR is identified by currency_id == 86 and USD by == 1, despite the hook correctly finding currencies by name.
- Why it matters: restored/custom databases can label charts incorrectly or fall back to generic units. Monetary aggregates use original currency and must remain scoped to one currency.
- Recommended fix: pass currency records/codes rather than IDs and test original-currency measures, labels, tax/discount handling, and drill-through consistency.
- Data migration: regenerated snapshot labels may need updating; no currency/amount conversion should be performed as part of this fix.

### F32 — Medium: the Jalali widget replaces a shared spreadsheet component globally

- Module: vagirest_native_dashboard.
- File/function: static/src/jalali_date_input.js, final DateFromToValue.components assignment; static/src/jalali_calendar.js.
- Problem: loading the backend bundle changes every spreadsheet from/to date input, not only VAGIREST dashboards. It depends on a specific internal import/component contract and browser Persian-calendar support.
- Why it matters: unrelated spreadsheet flows and users can receive the custom widget; Odoo minor upgrades can break asset resolution or callbacks.
- Recommended fix: scope behavior to an explicit dashboard/field option, use supported extension APIs, and add browser tests for keyboard entry, errors, clearing, localization, timezone boundaries, and standard dashboards.
- Data migration: normally no; review saved filter behavior if semantics change.

### F33 — Medium: calendar logic and timezone policies are duplicated

- Module: Jalali Calendar, Invoice Report, Native Dashboard.
- File/function: Jalali models/jalali_utils.py; Invoice models/account_move.py and sale_order.py; dashboard static/src/jalali_calendar.js; Jalali models/inventory_dates.py / production_input.py.
- Problem: two independent Python conversion implementations plus browser Intl conversion are used. Stock display reads env.user.tz while declaring depends_context("tz"); other adapters force Tehran. Production year selection is limited to 1390–1420.
- Why it matters: boundary/leap-year behavior and caching can diverge; context timezone and user timezone may disagree; supported historical/future inputs are inconsistent.
- Recommended fix: isolate shared calendar utilities from business adapters, define timezone/input ranges, align context dependencies, and test leap Esfand, Nowruz, Persian/Arabic digits, invalid dates, and UTC/local midnight round trips.
- Data migration: stored display fields may require recomputation only if results change; do not alter authoritative Gregorian dates without approval.

### F34 — High: invoice PDFs hardcode payment instructions and currency

- Module: vagirest_invoice_report.
- File/function: report/vagirest_invoice_report.xml and vagirest_sale_order_report.xml, company header, BANK DETAILS, SUMMARY.
- Problem: legal identity/contact/address, payment card/IBAN, stamp image, and “ریال” labels are literal template content. Amounts use zero-decimal formatting regardless of document currency, and line_before - price_subtotal is called discount even when tax-inclusive prices change that difference.
- Why it matters: another company's or foreign-currency document can show wrong beneficiary instructions or misleading amounts/discounts. The dynamic logo alone does not make the report multi-company safe.
- Recommended fix: use the document company's approved partner/bank/report configuration and currency-aware formatting; separate discounts and taxes; test IRR/USD, included/excluded taxes, refunds, rounding, draft/posted and multi-company PDFs.
- Data migration: configuration required; retain historic issued PDF copies and decide whether regenerated documents need controlled correction.

### F35 — Low: report assets include a public reusable stamp and untracked provenance

- Module: vagirest_invoice_report.
- File/function: static/src/img/stamp.png; static/src/fonts/BNazanin*.ttf; static/src/css/report_fonts.css; report/assets.xml.disabled.
- Problem: the stamp is shipped as a normal static asset and is embedded unconditionally. Font redistribution provenance/licensing is not documented. A disabled asset declaration and an unused CSS file coexist with duplicated inline @font-face/style blocks.
- Why it matters: a static stamp should not be treated as proof of authorized signing; duplicated/dead asset paths confuse maintenance and render testing.
- Recommended fix: confirm intended public stamp use, distinguish branding from approval/signature evidence, document font rights, and consolidate tested assets in a separate cleanup task.
- Data migration: no; signed-document semantics and issued PDFs require a business retention decision.

### F36 — Medium: large duplicated methods and layered fixes increase change risk

- Module: Production Record, Inventory QMS.
- File/function: material_request.py (1,425 lines), rework_correction_request.py (1,277), correction_workflow.py (1,242), rework_record.py (1,075), raw_material_receipt.py (1,050).
- Problem: reversal/availability/transfer code is copied across modules; company and sequence fixes are added as further classes in the same file. Largest methods include F02 reversal (179 lines), dashboard build_snapshot (177), shared reversal (174), F04 reversal (174), production submission (165), F04 finalization (152), and rework-QC approval (152).
- Why it matters: fixes can land in an overridden implementation, and variants diverge on company, rounding, traceability, validation, and audit policy. Broad refactors can silently change stock behavior.
- Recommended fix: first characterize behavior with tests; then extract narrowly scoped shared stock and transition services, one workflow at a time, preserving model names/XML IDs.
- Data migration: no for behavior-preserving refactors; any changed invariants must be handled separately.

### F37 — Medium: 59 legacy files are shipped beside live code

- Module: Production Record (54 files); Invoice Report (5).
- File/function: appendix inventory below; models/__init__.py and module manifests distinguish active imports/data.
- Problem: .before_*, .bak*, *_before_*.py/.xml, a notebook backup text file, and assets.xml.disabled remain tracked. Most contain older workflows/security rules. The current rework_correction_request.py.before_reviewnote_hardening_20261002T153623Z is identical to current code in the comparison.
- Why it matters: reviews/searches can mistake obsolete code for active behavior; wildcard imports/data loads or manual deployment copying can reintroduce weaker rules. They are not a tested rollback package.
- Recommended fix: preserve provenance in Git/tagged archives, then remove from deployable addon directories in a reviewed cleanup release; enforce packaging/import rules.
- Data migration: no; do not delete baseline evidence or restore these files on production ad hoc.

### F38 — Medium: repository lacks reproducible setup, migration, and CI contracts

- Module: repository; all addons.
- File/function: README.md, PROJECT_STATE.md; absent scripts/, compose/Dockerfile, pinned tool requirements, .github workflows, test directories, and migration scripts.
- Problem: documentation names operational scripts that are absent. Current-instance cloud helpers are outside the checkout; they use copied addon source in a Docker image and development-only PostgreSQL trust authentication. They are not a production deployment definition.
- Why it matters: another developer cannot reproduce all business workflows from repository instructions alone. Image-copy development requires rebuilding after source edits; retained anonymous addon volumes can preserve older code unless source is verified during container replacement.
- Recommended fix: add a separately reviewed, digest-pinned dev/staging contract with safe fixtures, explicit database/filestore isolation, source refresh verification, and no production endpoints; define supported module upgrade/migration commands.
- Data migration: no for tooling; staged upgrade fixtures and future migrations need documented data scope.

### F39 — High: automated security/integrity regression tests are absent

- Module: all nine addons.
- File/function: no tracked tests/ directories, test_*.py files, browser test suites, or CI runner definitions.
- Problem: installation and a small contact smoke check do not cover forms, role matrices, company rules, stock posting/reversal, receipts, upgrades, dashboards, or PDFs. checks.py mentions a standalone test suite that is not present.
- Why it matters: confirmed source gaps survived initialization; a login success is weak evidence for the ERP's critical workflows.
- Recommended fix: build Odoo TransactionCase/Savepoint-compatible tests with explicit roles/company fixtures; add concurrent transaction, upgrade, browser, and PDF checks. See test matrix below.
- Data migration: no; test fixtures must use synthetic/anonymized data and never production credentials.

### F40 — Low: manifest metadata and documentation need cleanup

- Module: vagirest_product_naming; repository/CRM.
- File/function: Product Naming __manifest__.py; Production Record one-line __manifest__.py; CRM README; docs/PRODUCTION_BASELINE_SHA256.txt.
- Problem: Product Naming omits license/author/category (Odoo warns and defaults license to LGPL-3); Production's manifest is difficult to review as one line. CRM README lists plans (visits/missions/access/integration) not implemented here. Recorded checksum inventory includes 26 absent historical paths.
- Why it matters: review quality, distribution metadata, and readiness claims can be misleading. No declared custom dependency cycle or missing manifest data file was found.
- Recommended fix: document implemented versus planned scope, normalize metadata in a later task, and explain excluded baseline archives without changing the original checksum evidence.
- Data migration: no.

### F41 — Medium: CRM synchronization is UI-only and naming affects every product display

- Module: vagirest_crm; vagirest_product_naming.
- File/function: crm_lead.py:_onchange_vagirest_partner_commercial_data; res_partner.py:vagirest_referrer_id; product_product.py:_compute_display_name.
- Problem: commercial fields are copied only through onchange, so imports/RPC creates omit them unless supplied. Referrer self-exclusion is a UI domain only. Standard naming globally replaces product display_name for configured variants.
- Why it matters: lead/contact classifications can diverge by entry route, self-reference can be supplied programmatically, and product lookup/context display can change in purchases/sales/stock. Product identity/default_code is preserved, which is a positive design.
- Recommended fix: define intentional snapshot versus synchronized CRM semantics and add server-side validation where required; test product display/name search across contexts and companies.
- Data migration: possibly for explicitly approved CRM backfill; do not overwrite lead history or rename product identities automatically.

### F42 — Medium: per-line searches and stored related history can be costly or misleading

- Module: Production Record, Inventory QMS, Native Dashboard.
- File/function: qc_record.py:_validate_decision_lines / _sync_lines_from_production; rework_record.py:_compute_available_rework_qty; rework_correction_request.py count computes; production_record.py:_compute_generated_lot; native models/sale_report.py.
- Problem: stock quantities and request counts are queried per record/line; duplicate product checks repeatedly filter all lines; QC stored related values depend on editable production lines; sale.report adds grouping on date text, creator, city and currency without workload evidence.
- Why it matters: query counts grow with document size, and related fields are live derivatives rather than immutable historical snapshots. Performance magnitude is unmeasured.
- Recommended fix: batch quant/count aggregation with scoped domains, snapshot authoritative QC inputs at submission, and benchmark report queries against representative staging volume before optimizing.
- Data migration: possibly for snapshots/index changes; preserve original stock/QC evidence.

## Per-addon conclusions

- CRM: comparatively small (243 Python lines including metadata/initializers), no explicit sudo/SQL; inherited contact/lead access remains the authority. Clarify UI-only synchronization and planned features.
- Customer Receipts: useful manager checks, positive/company/currency/customer validation, attachment read checks, exact rounded bank matching, and unique bank-line linkage. Matching does not post account moves/payments. Installation coupling, balance history, and assignment/aggregate privacy need work.
- Inventory QMS: largest stock-form surface (2,514 Python lines), real stock movements and reversals rather than quant edits. Missing compute method, F02 immutability/company/roles, and F04 aggregate/link/state enforcement are urgent.
- Invoice Report: read-oriented model helpers; escaped QWeb field output, no explicit sudo/SQL. Company/payment/currency hardcoding and PDF correctness need functional coverage.
- Jalali Calendar: parser checks round trips and normalizes digits; stored Gregorian dates remain authoritative. Split utilities from adapters, declare product_expiry, and test timezone/boundary behavior.
- Native Dashboard: explicit company/owner global rules and scoped source domains are positive. Hardcoded company/user/currency IDs, creator semantics, provisioning lifecycle, and global frontend replacement prevent portable deployment.
- Product Naming: small, preserves internal reference and product identity. Test global display behavior; repair metadata in a separate change.
- Production Record: 6,562 Python lines and multiple inheritance layers. Contains meaningful role checks, QC uniqueness, real reversals, reason collection, request snapshots, downstream rework checks, and deletion protection for rework. These do not close direct CRUD/context/company gaps.
- Unique Phone: indexed normalized values, Persian/Arabic digit normalization, batch duplicate checks, and formatting-only updates are positive. Strong uniqueness still requires visibility-independent and concurrent enforcement.

## Testing required before readiness or production rollout

| Target | Minimum meaningful cases |
|---|---|
| Installation | Fresh Odoo 17 database; each addon with only declared dependencies; all nine together; installation without company 3/user 19/production stock IDs |
| Upgrade | Restore a synthetic prior-version fixture; upgrade twice; verify SQL view recreation, sequences, XML IDs, record rules, dashboard snapshots, and retained audit records |
| Security | Operator, QC, ERP, F02 receiver, warehouse receiver, sales manager, personal follow-up, finance-only, normal internal, portal, and mixed-role users; direct RPC CRUD, context injection, exports, attachments |
| Multi-company | Two companies, one-company and multi-company users, active-company switching, shared/company products/contacts/lots, cross-company line/link rejection |
| Production/QC | Submit exactly once; rejected/approved/rework splits; separate inspector; invalid/negative/duplicate quantities; child edits after posting rejected; original evidence preserved |
| F02 | Receive/QC/split/reopen/reverse; receiver cannot set decisions; inspector cannot rewrite receipt facts; insufficient stock, serial tracking, company/type validation |
| F01/F04 | Open forms including warehouse_responsible_id; creator identity; ready/finalize link validation; duplicate product/lot lines, UoM conversion, partial requests, two concurrent calls, reversal |
| Rework | Return full batch, repeated rounds, operator-inspector separation, child advancement blocking upstream correction, company-correct reversals and immutable audit fields |
| Phone/CRM | Hidden/archived contacts, phone/mobile cross-conflicts, same-record phone/mobile, batch writes, concurrent creates, country/extension policy, ORM/import/onchange consistency |
| Receipts/balances | Company/customer/currency mismatch, duplicate bank line, reset/reject/match, source invalidation, aggregate privacy, opening overlap, cancelled/edited quotation, verified-history revisions |
| Calendar/frontend | Esfand leap years, Nowruz, invalid dates, digit scripts, UTC/local midnight and historical timezone cases, direct date permissions, standard dashboard compatibility |
| Reporting/PDF | Currency-aware amounts, included/excluded taxes, refunds, company/bank identity, multi-page layout, fonts/logo/stamp, original-currency aggregations and scoped drill-through |
| Deployment/recovery | Verify mounted addon commit/hash, restart, upgrade failure, restore DB+filestore+code+config together, rollback time and integrity checks |

No tests in this matrix were executed by this audit. No services were restarted. Existing onboarding smoke evidence is explicitly limited above.

## Remediation roadmap

### Phase 0 - Production safety

1. Freeze the authoritative baseline commit and retain the checksum inventory and historical artifacts.
2. Do not recreate production containers or mutate volumes. Arrange a separately authorized mount/configuration inventory.
3. Define a verified backup set: database, filestore, addon source, configuration, image digests, and volume metadata; rehearse restore on staging.
4. Open urgent tickets for F02–F08 and F14–F19; restrict operational correction procedures through documented governance until code fixes are tested. Do not silently revoke existing production users in this audit.
5. Exit gate: known recoverable deployment mapping, restore evidence, named release/rollback owners, and approval boundaries.

### Phase 1 - Reproducible development/staging

1. Keep the cloud stack isolated; document source-image refresh and persistence separately from running processes.
2. First make Jalali installation self-contained with product_expiry and a fresh-install regression.
3. Make dashboard installation independent of company/user IDs; introduce safe explicit provisioning and synthetic fixtures.
4. Supply configurable stock topology so production/QC/F02/rework tests run without production IDs.
5. Prove fresh install of all nine addons and exercise all forms; fix the missing F01/F04 compute method.
6. Exit gate: a clean database reproduces the addon suite, role fixtures and stock topology without production access. No need to renumber production records.

### Phase 2 - Critical/high-risk fixes

1. Close production, QC-line, F02, rework-context, and F01/F04 direct CRUD bypasses with negative tests.
2. Add company fields/rules/relational checks with a reviewed backfill plan before enabling them on existing data.
3. Enforce aggregated stock/UoM checks, safe company reversals, transaction serialization, and idempotent transitions.
4. Resolve phone uniqueness design, financial-history mutability, and company/currency/payment-report correctness.
5. Repair correction-button creation and separate receiver/inspector ACLs.
6. Exit gate: security/integrity test matrix passes; proposed data repair is independently reviewed; upgrade/restore rehearsal passes.

### Phase 3 - Architecture cleanup

1. Extract calendar utilities into a small addon and keep manufacturing/stock/sale integrations in dependency-specific adapters.
2. Move shared finance roles out of dashboards with an XML-ID/membership migration; retain optional integration.
3. Move organization-wide menu/security policy out of production business logic.
4. Consolidate tested stock reversal/availability and transition helpers; simplify overridden company/sequence fixes.
5. Archive legacy files outside deployable addon roots; consolidate report/frontend assets and metadata.
6. Exit gate: smaller dependency surface with unchanged approved stock behavior and traceable data/model/XML-ID mappings.

### Phase 4 - Automated testing

1. Establish CI for AST/XML/manifest integrity plus actual Odoo installation and transaction tests.
2. Add role/company/direct-RPC negative tests first, then stock/correction and concurrency tests.
3. Add frontend/dashboard and currency/tax/PDF suites; characterize historical upgrade fixtures.
4. Publish explicit pass/fail/test-count artifacts and performance query budgets.
5. Exit gate: required suites execute nonzero tests and protect changes to all nine addons; skips/unrun cases remain visible.

### Phase 5 - Deployment automation

1. Define immutable reviewed releases with exact source SHA, image digests, dependency pins, and verified addon mounts.
2. Separate backup, maintenance, controlled module upgrade, smoke checks, and rollback stages.
3. Preserve secrets outside Git and keep development trust authentication isolated from staging/production.
4. Gate production rollout on diff review, authorization, migration/backup validation, staging evidence, and rollback rehearsal.
5. Verify the running addon hash after deployment; retain logs and recovery artifacts. A code rollback alone is insufficient after schema/data upgrades.
6. Exit gate: predictable rollout and restoration with preserved lots, QC/manufacturing history, financial data, and filestore.

## Legacy-file inventory

These 59 files are tracked but are not referenced by current manifests/initializers as addon implementation. Python backups with ordinary .py extensions were checked against imports; no wildcard import was found. This inventory is preservation evidence, not a deletion instruction.

- custom_addons/vagirest_invoice_report/__init__.py.bak-20260812_181416
- custom_addons/vagirest_invoice_report/report/assets.xml.disabled
- custom_addons/vagirest_invoice_report/report/vagirest_invoice_report.xml.bak-20260812_181416
- custom_addons/vagirest_invoice_report/report/vagirest_invoice_report.xml.bak-FINAL-20260812_183331
- custom_addons/vagirest_invoice_report/report/vagirest_invoice_report.xml.bak-before-bnazanin
- custom_addons/vagirest_production_record/__manifest__.py.before_correction_request
- custom_addons/vagirest_production_record/__manifest__.py.before_final_hardening_20261002T152953Z
- custom_addons/vagirest_production_record/__manifest__.py.before_legacy_open_fix_20261002T155610Z
- custom_addons/vagirest_production_record/__manifest__.py.before_qc_request_20261002T132132Z
- custom_addons/vagirest_production_record/__manifest__.py.before_reviewnote_hardening_20261002T153512Z
- custom_addons/vagirest_production_record/__manifest__.py.before_reviewnote_hardening_20261002T153623Z
- custom_addons/vagirest_production_record/__manifest__.py.before_rework_20260706_074540
- custom_addons/vagirest_production_record/__manifest__.py.before_rework_requests_20261002T151919Z
- custom_addons/vagirest_production_record/__manifest__.py.before_rework_security_20261002T133703Z
- custom_addons/vagirest_production_record/__manifest__.py.before_safe_cancel_20261002T150522Z
- custom_addons/vagirest_production_record/data/correction_sequences.xml.before_correction_request
- custom_addons/vagirest_production_record/data/correction_sequences.xml.before_global_vcr_sequence_20261002T131407Z
- custom_addons/vagirest_production_record/data/correction_sequences.xml.before_qc_request_20261002T132132Z
- custom_addons/vagirest_production_record/data/correction_sequences.xml.before_rework_requests_20261002T151919Z
- custom_addons/vagirest_production_record/data/sequence.xml.before_rework_20260706_074540
- custom_addons/vagirest_production_record/models/__init__.py.before_correction_request
- custom_addons/vagirest_production_record/models/__init__.py.before_qc_request_20261002T132132Z
- custom_addons/vagirest_production_record/models/__init__.py.before_rework_20260706_074540
- custom_addons/vagirest_production_record/models/__init__.py.before_rework_requests_20261002T151919Z
- custom_addons/vagirest_production_record/models/__init__.py.before_rework_security_20261002T133703Z
- custom_addons/vagirest_production_record/models/correction_request.py.before_final_hardening_20261002T152953Z
- custom_addons/vagirest_production_record/models/correction_request.py.before_hardening_20261002T130949Z
- custom_addons/vagirest_production_record/models/correction_workflow.py.before_hardening_20261002T130949Z
- custom_addons/vagirest_production_record/models/correction_workflow.py.before_legacy_open_fix_20261002T155610Z
- custom_addons/vagirest_production_record/models/correction_workflow.py.before_qc_request_20261002T132132Z
- custom_addons/vagirest_production_record/models/production_record.py.before_raw_lock_20261002T124102Z
- custom_addons/vagirest_production_record/models/production_record_backup_before_category.py
- custom_addons/vagirest_production_record/models/production_record_bad_ipynb_backup.txt
- custom_addons/vagirest_production_record/models/production_record_before_auto_qc.py
- custom_addons/vagirest_production_record/models/production_record_before_category_change.py
- custom_addons/vagirest_production_record/models/production_record_before_return_draft.py
- custom_addons/vagirest_production_record/models/qc_correction_request.py.before_final_hardening_20261002T152953Z
- custom_addons/vagirest_production_record/models/qc_correction_request.py.before_message_post_fix_20261002T132555Z
- custom_addons/vagirest_production_record/models/qc_correction_request.py.before_resubmit_context_fix_20261002T132751Z
- custom_addons/vagirest_production_record/models/rework_correction_request.py.before_reviewnote_hardening_20261002T153512Z
- custom_addons/vagirest_production_record/models/rework_correction_request.py.before_reviewnote_hardening_20261002T153623Z
- custom_addons/vagirest_production_record/models/rework_record.py.before_company_fix_20260706_080755
- custom_addons/vagirest_production_record/models/rework_record.py.before_rework_qc_sequence_fix_20260706_081638
- custom_addons/vagirest_production_record/models/rework_record.py.before_sudo_fix_20260706_074825
- custom_addons/vagirest_production_record/models/rework_security.py.before_rework_requests_20261002T151919Z
- custom_addons/vagirest_production_record/models/rework_security.py.before_safe_cancel_20261002T150522Z
- custom_addons/vagirest_production_record/security/ir.model.access.csv.before_correction_request
- custom_addons/vagirest_production_record/security/ir.model.access.csv.before_hardening_20261002T130949Z
- custom_addons/vagirest_production_record/security/ir.model.access.csv.before_qc_request_20261002T132132Z
- custom_addons/vagirest_production_record/security/ir.model.access.csv.before_rework_20260706_074540
- custom_addons/vagirest_production_record/security/ir.model.access.csv.before_rework_requests_20261002T151919Z
- custom_addons/vagirest_production_record/security/security.xml.before_correction_request
- custom_addons/vagirest_production_record/security/security.xml.before_qc_request_20261002T132132Z
- custom_addons/vagirest_production_record/views/correction_request_views.xml.before_model_whitespace_fix_20261002T125722Z
- custom_addons/vagirest_production_record/views/correction_workflow_views.xml.before_correction_request
- custom_addons/vagirest_production_record/views/correction_workflow_views.xml.before_qc_request_20261002T132132Z
- custom_addons/vagirest_production_record/views/production_record_views_before_return_draft.xml
- custom_addons/vagirest_production_record/views/rework_security_views.xml.before_model_whitespace_fix_20261002T150637Z
- custom_addons/vagirest_production_record/views/rework_security_views.xml.before_safe_cancel_20261002T150522Z

## Top 10 recommended actions

1. Verify production addon mounts and rehearse complete recovery before any deployment/container recreation (F01).
2. Enforce immutable posted production/QC/F02 facts on parents and child models (F02, F03, F05).
3. Replace caller-controlled context authorization with validated private transitions (F04).
4. Add company isolation and fix company selection in elevated stock/reversal paths with reviewed backfills (F06–F08, F19).
5. Make fresh installation portable: product_expiry, configured dashboard company/owner, independent finance roles, configurable stock topology (F08–F12).
6. Fix F01/F04 form computation and lifecycle/link/aggregate-UoM validation (F13–F16).
7. Make stock transitions, approvals, and phone identity enforcement safe under concurrent transactions (F17, F20).
8. Preserve standard return traceability and validate stock valuation; retain immutable financial/legacy correction evidence (F18, F21, F26).
9. Remove literal report company/payment/currency assumptions and make dashboard provisioning/versioning explicit (F30–F35).
10. Establish security, company, stock, upgrade, browser and PDF tests before refactoring or deployment automation (F36–F42).

## Top 5 things that must NOT be changed directly in production

1. The live /mnt/extra-addons mount, addon Docker volume, or web container mapping; no compose down, force recreation, or volume replacement without verified recovery and explicit authorization.
2. Stock quantities, completed moves/pickings, reservations, warehouse/location identities, lot numbers, or product identities by SQL/manual field edits; use approved ORM/migration/reversal procedures.
3. Submitted production/QC/rework history, approved correction snapshots, reviewer/operator identities, or inspection totals to make records “look consistent.”
4. Posted accounting/bank data, verified customer balances, receipt links, or contact merges/phone identities without a dedicated reviewed reconciliation/migration plan.
5. Installed-module manifests, dependencies, security groups/rules, core-menu assignments, and schema/module versions through untested live edits; deploy a reviewed staging-tested release with backup and rollback evidence.

## Recommended first coding task

Declare the missing product_expiry dependency for vagirest_jalali_calendar and add a fresh-install regression in an isolated Odoo 17 database.

This is a narrow Phase 1 prerequisite that removes a confirmed registry failure without changing production IDs, stock quantities, financial history, or dashboard access policy. The intended scope is the Jalali manifest and isolated regression coverage; do not bundle stock/security refactors or deploy it to production.

Acceptance criteria:

- Installing Jalali with only its declared dependencies succeeds without preinstalling product_expiry manually.
- Expiration-related models/views resolve correctly and remain readable.
- A repeat module upgrade succeeds in the isolated fixture.
- No authoritative dates, lot identifiers, quantities, companies, users, or access memberships are rewritten.

Next coding task: make dashboard provisioning explicitly configurable and safe to skip on installation while preserving existing generated dashboards/XML IDs. Critical integrity/security repairs remain urgent Phase 2 work and must precede production rollout. No fix or migration is implemented by this report.


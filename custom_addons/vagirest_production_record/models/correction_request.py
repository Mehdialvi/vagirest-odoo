import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .correction_workflow import _reverse_done_picking


class VagirestProductionCorrectionRequest(models.Model):
    _name = "vagirest.production.correction.request"
    _description = "VAGIREST Production Correction Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Request Number",
        default="New",
        readonly=True,
        copy=False,
        tracking=True,
    )

    production_record_id = fields.Many2one(
        "vagirest.production.record",
        string="Production Record",
        required=True,
        readonly=True,
        ondelete="restrict",
        tracking=True,
    )

    requester_id = fields.Many2one(
        "res.users",
        string="Requested By",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
        tracking=True,
    )

    requested_at = fields.Datetime(
        string="Requested At",
        readonly=True,
        default=fields.Datetime.now,
        tracking=True,
    )

    action_type = fields.Selection(
        [
            ("return_to_draft", "Return to Draft for Correction"),
            ("cancel", "Cancel Production Record"),
        ],
        string="Requested Action",
        required=True,
        default="return_to_draft",
        tracking=True,
    )

    reason = fields.Text(
        string="Correction Reason",
        required=True,
        tracking=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Waiting for Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("applied", "Applied"),
        ],
        default="draft",
        required=True,
        readonly=True,
        tracking=True,
    )

    reviewed_by_id = fields.Many2one(
        "res.users",
        string="Reviewed By",
        readonly=True,
        tracking=True,
    )

    reviewed_at = fields.Datetime(
        string="Reviewed At",
        readonly=True,
        tracking=True,
    )

    review_note = fields.Text(
        string="Review Note",
        tracking=True,
    )

    reversal_picking_id = fields.Many2one(
        "stock.picking",
        string="Reversal Transfer",
        readonly=True,
        copy=False,
        tracking=True,
    )

    before_snapshot = fields.Text(
        string="Before Correction Snapshot",
        readonly=True,
        copy=False,
    )

    after_snapshot = fields.Text(
        string="After Correction Snapshot",
        readonly=True,
        copy=False,
    )

    change_summary = fields.Text(
        string="Recorded Changes",
        readonly=True,
        copy=False,
    )

    applied_at = fields.Datetime(
        string="Applied At",
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        Sequence = self.env["ir.sequence"].sudo()
        clean_vals_list = []

        for incoming in vals_list:
            vals = dict(incoming)

            if not vals.get("production_record_id"):
                raise UserError(
                    _("Production Record is required.")
                )

            number = Sequence.next_by_code(
                "vagirest.production.correction.request"
            )

            if not number:
                raise UserError(
                    _(
                        "Production Correction Request "
                        "sequence is missing."
                    )
                )

            # Never trust audit/system values supplied by RPC/UI.
            vals.update({
                "name": number,
                "requester_id": self.env.user.id,
                "requested_at": fields.Datetime.now(),
                "state": "draft",
                "reviewed_by_id": False,
                "reviewed_at": False,
                "review_note": False,
                "reversal_picking_id": False,
                "before_snapshot": False,
                "after_snapshot": False,
                "change_summary": False,
                "applied_at": False,
            })

            clean_vals_list.append(vals)

        return super().create(clean_vals_list)


    def write(self, vals):
        if not self.env.su:
            protected = {
                "name",
                "state",
                "reviewed_by_id",
                "reviewed_at",
                "reversal_picking_id",
                "before_snapshot",
                "after_snapshot",
                "change_summary",
                "applied_at",
                "requester_id",
                "requested_at",
                "production_record_id",
            }

            if protected.intersection(vals):
                raise UserError(
                    _("System-controlled correction fields cannot be edited.")
                )

            if "review_note" in vals:
                can_review = (
                    self.env.user.has_group(
                        "vagirest_production_record."
                        "group_vagirest_qc_manager"
                    )
                    or self.env.user.has_group(
                        "vagirest_production_record."
                        "group_vagirest_erp_manager"
                    )
                )

                if not can_review:
                    raise UserError(
                        _(
                            "Only QC Manager or ERP Manager "
                            "may enter the Review Note."
                        )
                    )

            for record in self:
                if record.state != "draft":
                    allowed_after_submit = {"review_note"}

                    if not set(vals).issubset(allowed_after_submit):
                        raise UserError(
                            _(
                                "A submitted correction request "
                                "cannot be edited."
                            )
                        )

        return super().write(vals)

    def unlink(self):
        raise UserError(
            _(
                "Correction requests cannot be deleted. "
                "They are part of the audit trail."
            )
        )

    def _snapshot(self):
        self.ensure_one()

        record = self.production_record_id

        data = {
            "production_record_id": record.id,
            "production_record_name": record.name,
            "state": record.state,
            "production_date": (
                str(record.production_date)
                if record.production_date
                else False
            ),
            "raw_material_batch": record.raw_material_batch,
            "note": record.note or "",
            "lines": [
                {
                    "line_id": line.id,
                    "product_id": line.product_id.id,
                    "product": line.product_id.display_name,
                    "quantity": line.quantity,
                    "lot_id": line.lot_id.id if line.lot_id else False,
                    "lot": line.lot_id.name if line.lot_id else False,
                    "stock_move_id": (
                        line.stock_move_id.id
                        if line.stock_move_id
                        else False
                    ),
                }
                for line in record.line_ids.sorted("id")
            ],
        }

        return json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )

    def action_submit_request(self):
        for request in self:
            if request.state != "draft":
                raise UserError(
                    _("Only Draft requests can be submitted.")
                )

            if not (request.reason or "").strip():
                raise UserError(
                    _("Correction reason is required.")
                )

            production = request.production_record_id

            if production.state != "submitted":
                raise UserError(
                    _(
                        "Only a Submitted production record "
                        "can be corrected through this workflow."
                    )
                )

            existing = self.search_count([
                ("id", "!=", request.id),
                (
                    "production_record_id",
                    "=",
                    production.id,
                ),
                ("state", "in", ["submitted", "approved"]),
            ])

            if existing:
                raise UserError(
                    _(
                        "Another correction request is already "
                        "open for this production record."
                    )
                )

            snapshot = request._snapshot()

            request.sudo().write({
                "state": "submitted",
                "before_snapshot": snapshot,
            })

            production.message_post(
                body=_(
                    "<b>Production correction requested.</b>"
                    "<br/>Request: %s"
                    "<br/>Requested by: %s"
                    "<br/>Reason: %s"
                )
                % (
                    request.display_name,
                    request.requester_id.display_name,
                    request.reason,
                )
            )

        return True

    def _check_approver(self):
        if not (
            self.env.user.has_group(
                "vagirest_production_record."
                "group_vagirest_qc_manager"
            )
            or self.env.user.has_group(
                "vagirest_production_record."
                "group_vagirest_erp_manager"
            )
        ):
            raise UserError(
                _("You are not authorized to approve corrections.")
            )

    def action_approve(self):
        self._check_approver()

        for request in self:
            if request.state != "submitted":
                raise UserError(
                    _("Only submitted requests can be approved.")
                )

            is_erp_manager = self.env.user.has_group(
                "vagirest_production_record."
                "group_vagirest_erp_manager"
            )

            if (
                request.requester_id == self.env.user
                and not is_erp_manager
            ):
                raise UserError(
                    _(
                        "You cannot approve your own "
                        "correction request."
                    )
                )

            if (
                request.requester_id == self.env.user
                and is_erp_manager
                and not (request.review_note or "").strip()
            ):
                raise UserError(
                    _(
                        "ERP Manager self-approval requires "
                        "an Override Reason in Review Note."
                    )
                )

            production = request.production_record_id.sudo()

            if production.state != "submitted":
                raise UserError(
                    _(
                        "The production record is no longer "
                        "in Submitted state."
                    )
                )

            qc_record = production._get_related_qc()

            if qc_record and qc_record.state == "done":
                raise UserError(
                    _(
                        "The related QC decision is already Done.\n\n"
                        "Correct/reopen the QC decision first."
                    )
                )

            reversal = False

            if production.stock_picking_id:
                reversal = _reverse_done_picking(
                    production,
                    production.stock_picking_id,
                    "Approved Production Correction Reversal",
                )

            if qc_record and qc_record.state == "draft":
                qc_record.line_ids.sudo().unlink()

            if request.action_type == "return_to_draft":
                production.line_ids.sudo().write({
                    "lot_id": False,
                    "stock_move_id": False,
                })

                production.write({
                    "state": "draft",
                    "stock_picking_id": False,
                    "reversal_picking_id": (
                        reversal.id if reversal else False
                    ),
                    "last_corrected_by_id": self.env.user.id,
                    "last_correction_date": fields.Datetime.now(),
                    "correction_count": (
                        production.correction_count + 1
                    ),
                    "correction_reason": False,
                    "active_correction_request_id": request.id,
                })

                new_state = "approved"

            else:
                if qc_record and qc_record.state == "draft":
                    qc_record.sudo().write({
                        "active": False,
                    })

                production.write({
                    "state": "cancelled",
                    "reversal_picking_id": (
                        reversal.id if reversal else False
                    ),
                    "last_corrected_by_id": self.env.user.id,
                    "last_correction_date": fields.Datetime.now(),
                    "correction_count": (
                        production.correction_count + 1
                    ),
                    "correction_reason": False,
                    "active_correction_request_id": False,
                })

                new_state = "applied"

            request.sudo().write({
                "state": new_state,
                "reviewed_by_id": self.env.user.id,
                "reviewed_at": fields.Datetime.now(),
                "reversal_picking_id": (
                    reversal.id if reversal else False
                ),
                "applied_at": (
                    fields.Datetime.now()
                    if new_state == "applied"
                    else False
                ),
            })

            production.message_post(
                body=_(
                    "<b>Correction request approved.</b>"
                    "<br/>Request: %s"
                    "<br/>Requester: %s"
                    "<br/>Approved by: %s"
                    "<br/>Reason: %s"
                    "<br/>Reversal: %s"
                )
                % (
                    request.display_name,
                    request.requester_id.display_name,
                    self.env.user.display_name,
                    request.reason,
                    (
                        reversal.display_name
                        if reversal
                        else "Not required"
                    ),
                )
            )

        return True

    def action_reject(self):
        self._check_approver()

        for request in self:
            if request.state != "submitted":
                raise UserError(
                    _("Only submitted requests can be rejected.")
                )

            is_erp_manager = self.env.user.has_group(
                "vagirest_production_record."
                "group_vagirest_erp_manager"
            )

            if (
                request.requester_id == self.env.user
                and not is_erp_manager
            ):
                raise UserError(
                    _(
                        "You cannot review your own "
                        "correction request."
                    )
                )

            if not (request.review_note or "").strip():
                raise UserError(
                    _("Enter a rejection reason in Review Note.")
                )

            request.sudo().write({
                "state": "rejected",
                "reviewed_by_id": self.env.user.id,
                "reviewed_at": fields.Datetime.now(),
            })

            request.production_record_id.message_post(
                body=_(
                    "<b>Correction request rejected.</b>"
                    "<br/>Request: %s"
                    "<br/>Reviewed by: %s"
                    "<br/>Review note: %s"
                )
                % (
                    request.display_name,
                    self.env.user.display_name,
                    request.review_note,
                )
            )

        return True


class VagirestProductionRecordCorrectionRequest(models.Model):
    _inherit = "vagirest.production.record"

    correction_request_ids = fields.One2many(
        "vagirest.production.correction.request",
        "production_record_id",
        string="Correction Requests",
    )

    active_correction_request_id = fields.Many2one(
        "vagirest.production.correction.request",
        string="Active Correction Request",
        readonly=True,
        copy=False,
    )

    correction_request_count = fields.Integer(
        compute="_compute_correction_request_count"
    )

    @api.depends("correction_request_ids")
    def _compute_correction_request_count(self):
        for record in self:
            record.correction_request_count = len(
                record.correction_request_ids
            )

    def action_request_correction(self):
        self.ensure_one()

        if self.state != "submitted":
            raise UserError(
                _(
                    "Correction can only be requested "
                    "for a Submitted production record."
                )
            )

        Correction = self.env[
            "vagirest.production.correction.request"
        ]

        request = Correction.search([
            ("production_record_id", "=", self.id),
            ("state", "=", "draft"),
            ("requester_id", "=", self.env.user.id),
        ], limit=1)

        if not request:
            request = Correction.create({
                "production_record_id": self.id,
                "requester_id": self.env.user.id,
            })

        return {
            "type": "ir.actions.act_window",
            "name": _("Production Correction Request"),
            "res_model": (
                "vagirest.production.correction.request"
            ),
            "res_id": request.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_correction_requests(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Correction Requests"),
            "res_model": (
                "vagirest.production.correction.request"
            ),
            "view_mode": "tree,form",
            "domain": [
                ("production_record_id", "=", self.id)
            ],
            "context": {
                "default_production_record_id": self.id
            },
        }

    def action_submit_to_qc(self):
        pending_request = {
            record.id: record.active_correction_request_id
            for record in self
            if record.active_correction_request_id
            and record.active_correction_request_id.state == "approved"
        }

        after_snapshots = {}

        for record in self:
            request = pending_request.get(record.id)

            if request:
                after_snapshots[record.id] = request._snapshot()

        result = super().action_submit_to_qc()

        for record in self:
            request = pending_request.get(record.id)

            if not request:
                continue

            before_text = request.before_snapshot or ""
            after_text = after_snapshots.get(record.id, "")

            summary = (
                "Production record was corrected and resubmitted.\n"
                "Original and corrected snapshots are stored "
                "on this request.\n"
            )

            if before_text == after_text:
                summary += (
                    "\nWarning: no user-data difference was detected."
                )

            request.sudo().write({
                "state": "applied",
                "after_snapshot": after_text,
                "change_summary": summary,
                "applied_at": fields.Datetime.now(),
            })

            record.sudo().write({
                "active_correction_request_id": False,
            })

            record.message_post(
                body=_(
                    "<b>Approved correction applied and "
                    "production resubmitted.</b>"
                    "<br/>Request: %s"
                )
                % request.display_name
            )

        return result

from odoo import fields, models, _
from odoo.exceptions import UserError


class VagirestReworkRecordSecurity(models.Model):
    _inherit = "vagirest.rework.record"

    # ------------------------------------------------------------------
    # SERVER-SIDE IMMUTABILITY
    # ------------------------------------------------------------------

    def write(self, vals):
        if not self.env.su and not self.env.context.get(
            "allow_rework_workflow_write"
        ):
            workflow_fields = {
                "name",
                "operator_id",
                "source_qc_line_id",
                "parent_rework_id",
                "rework_round",
                "product_id",
                "lot_id",
                "quantity",
                "return_picking_id",
                "rework_qc_record_id",
                "state",
                "company_id",
                "active_rework_correction_request_id",
            }

            if workflow_fields.intersection(vals):
                raise UserError(
                    _(
                        "System-controlled Rework fields cannot "
                        "be modified directly."
                    )
                )

            editable_fields = {
                "rework_date",
                "corrected_qty",
                "correction_note",
            }

            if editable_fields.intersection(vals):
                locked = self.filtered(
                    lambda record: record.state != "draft"
                )

                if locked:
                    raise UserError(
                        _(
                            "Submitted or completed Rework records "
                            "cannot be modified directly. "
                            "Use the controlled correction workflow."
                        )
                    )

        return super().write(vals)

    def unlink(self):
        raise UserError(
            _(
                "Rework records cannot be deleted. "
                "They are part of the manufacturing and "
                "quality audit trail."
            )
        )

    # ------------------------------------------------------------------
    # NORMAL SUBMISSION
    # Keep workflow fields writable only inside this controlled action.
    # ------------------------------------------------------------------

    def action_submit_to_qc(self):
        controlled_self = self.with_context(
            allow_rework_workflow_write=True
        )

        return super(
            VagirestReworkRecordSecurity,
            controlled_self
        ).action_submit_to_qc()

    # ------------------------------------------------------------------
    # DIRECT CANCELLATION
    #
    # Existing operator-side direct cancel is too risky because the
    # product physically remains in Rework location.
    #
    # ERP Manager keeps emergency authority, but must document reason.
    # ------------------------------------------------------------------

    def action_cancel(self):
        raise UserError(
            _(
                "Direct Rework cancellation is disabled because "
                "the material is still physically located in Rework. "
                "Use the controlled Rework correction / cancellation "
                "workflow so the stock disposition is recorded."
            )
        )


class VagirestReworkQCRecordSecurity(models.Model):
    _inherit = "vagirest.rework.qc.record"

    state = fields.Selection(
        selection_add=[
            ("cancelled", "Cancelled"),
        ],
        ondelete={
            "cancelled": "set default",
        },
    )

    def write(self, vals):
        if not self.env.su and not self.env.context.get(
            "allow_rework_qc_workflow_write"
        ):
            workflow_fields = {
                "name",
                "rework_record_id",
                "quantity",
                "inspector_id",
                "decision_date",
                "approved_picking_id",
                "rework_picking_id",
                "rejected_picking_id",
                "state",
                "company_id",
                "active_rework_qc_correction_request_id",
            }

            if workflow_fields.intersection(vals):
                raise UserError(
                    _(
                        "System-controlled Rework QC fields cannot "
                        "be modified directly."
                    )
                )

            decision_fields = {
                "approved_qty",
                "rework_qty",
                "rejected_qty",
                "note",
            }

            if decision_fields.intersection(vals):
                locked = self.filtered(
                    lambda record: record.state != "draft"
                )

                if locked:
                    raise UserError(
                        _(
                            "Submitted Rework QC decisions cannot "
                            "be modified directly. "
                            "Use the controlled correction workflow."
                        )
                    )

        return super().write(vals)

    def unlink(self):
        raise UserError(
            _(
                "Rework QC records cannot be deleted. "
                "They are part of the quality audit trail."
            )
        )

    def action_submit_decision(self):
        controlled_self = self.with_context(
            allow_rework_qc_workflow_write=True
        )

        return super(
            VagirestReworkQCRecordSecurity,
            controlled_self
        ).action_submit_decision()


class VagirestQCReworkHistorySecurity(models.Model):
    _inherit = "vagirest.qc.record"

    def _has_rework_history(self):
        self.ensure_one()

        # Cancelled Rework records remain permanently in the audit trail,
        # but must not prevent correction of an upstream QC record after
        # the physical stock flow has been completely reversed.
        return bool(
            self.env["vagirest.rework.record"]
            .sudo()
            .search_count([
                ("source_qc_record_id", "=", self.id),
                ("state", "!=", "cancelled"),
            ])
        )

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VagirestProductionRecord(models.Model):
    _name = "vagirest.production.record"
    _description = "VAGIREST Production Record"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "production_date desc, id desc"

    name = fields.Char(
        string="Record Number",
        default="New",
        readonly=True,
        copy=False,
        tracking=True,
    )

    production_date = fields.Date(
        string="Production Date",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )

    raw_material_batch = fields.Char(
        string="Raw Material Batch",
        required=True,
        tracking=True,
    )

    operator_id = fields.Many2one(
        "res.users",
        string="Operator",
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
    )

    note = fields.Text(string="Notes")

    line_ids = fields.One2many(
        "vagirest.production.record.line",
        "record_id",
        string="Produced Products",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted to QC"),
        ],
        default="draft",
        tracking=True,
    )

    def _get_input_qc_location(self):
        location = self.env["stock.location"].search([
            ("complete_name", "=", "اصلی/input-QC"),
            ("usage", "=", "internal"),
        ], limit=1)

        if not location:
            location = self.env["stock.location"].search([
                ("name", "=", "input-QC"),
                ("usage", "=", "internal"),
            ], limit=1)

        if not location:
            raise UserError(_("input-QC location was not found."))

        return location

    def action_submit_to_qc(self):
        input_qc_location = self._get_input_qc_location()

        for record in self:
            if record.state != "draft":
                raise UserError(_("Only draft records can be submitted."))

            valid_lines = record.line_ids.filtered(lambda line: line.quantity > 0)

            if not valid_lines:
                raise UserError(_("Please enter at least one product with quantity greater than zero."))

            if record.name == "New":
                record.name = self.env["ir.sequence"].next_by_code(
                    "vagirest.production.record"
                ) or "New"

            for line in valid_lines:
                lot = self.env["stock.lot"].search([
                    ("name", "=", line.generated_lot),
                    ("product_id", "=", line.product_id.id),
                ], limit=1)

                if not lot:
                    lot = self.env["stock.lot"].create({
                        "name": line.generated_lot,
                        "product_id": line.product_id.id,
                        "company_id": self.env.company.id,
                    })

                self.env["stock.quant"]._update_available_quantity(
                    line.product_id,
                    input_qc_location,
                    line.quantity,
                    lot_id=lot,
                )

            record.message_post(body=_("Production record submitted to QC."))

    def action_return_to_draft(self):
        input_qc_location = self._get_input_qc_location()

        for record in self:
            if record.state != "submitted":
                raise UserError(_("Only submitted records can be returned to draft."))

            for line in record.line_ids.filtered(lambda line: line.quantity > 0):
                lot = self.env["stock.lot"].search([
                    ("name", "=", line.generated_lot),
                    ("product_id", "=", line.product_id.id),
                ], limit=1)

                if not lot:
                    raise UserError(_("Lot was not found for product %s.") % line.product_id.display_name)

                qty_in_input_qc = self.env["stock.quant"]._get_available_quantity(
                    line.product_id,
                    input_qc_location,
                    lot_id=lot,
                )

                if qty_in_input_qc < line.quantity:
                    raise UserError(_("This record cannot be returned to draft because some quantity has already moved from input-QC."))

                self.env["stock.quant"]._update_available_quantity(
                    line.product_id,
                    input_qc_location,
                    -line.quantity,
                    lot_id=lot,
                )

            record.state = "draft"
            record.message_post(body=_("Production record returned to draft and input-QC quantity was reversed."))


class VagirestProductionRecordLine(models.Model):
    _name = "vagirest.production.record.line"
    _description = "VAGIREST Production Record Line"

    record_id = fields.Many2one(
        "vagirest.production.record",
        string="Production Record",
        required=True,
        ondelete="cascade",
    )

    product_categ_id = fields.Many2one(
        "product.category",
        string="Product Category",
        required=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        domain="[('categ_id', 'child_of', product_categ_id), ('type', '=', 'product'), ('tracking', '=', 'lot'), ('active', '=', True)]",
    )

    quantity = fields.Float(
        string="Quantity",
        required=True,
        default=0.0,
    )

    generated_lot = fields.Char(
        string="Generated Lot",
        compute="_compute_generated_lot",
        store=True,
        readonly=True,
    )

    @api.onchange("product_categ_id")
    def _onchange_product_categ_id(self):
        self.product_id = False

    @api.depends(
        "product_id",
        "record_id.raw_material_batch",
        "record_id.production_date",
    )
    def _compute_generated_lot(self):
        for line in self:
            if (
                line.product_id
                and line.record_id.raw_material_batch
                and line.record_id.production_date
            ):
                code = line.product_id.default_code or str(line.product_id.id)
                clean_batch = line.record_id.raw_material_batch.strip().replace(" ", "-")
                date_str = line.record_id.production_date.strftime("%Y%m%d")
                line.generated_lot = f"{code}-{clean_batch}-{date_str}"
            else:
                line.generated_lot = False

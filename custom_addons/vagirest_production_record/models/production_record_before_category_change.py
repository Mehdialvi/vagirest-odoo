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
                if line.product_id.tracking != "lot":
                    raise UserError(
                        _("Product %s must have Lot Tracking enabled.")
                        % line.product_id.display_name
                    )

                lot_name = line.generated_lot
                if not lot_name:
                    raise UserError(_("Generated lot is empty."))

                lot = self.env["stock.lot"].search([
                    ("name", "=", lot_name),
                    ("product_id", "=", line.product_id.id),
                ], limit=1)

                if not lot:
                    lot = self.env["stock.lot"].create({
                        "name": lot_name,
                        "product_id": line.product_id.id,
                        "company_id": self.env.company.id,
                    })

                quant = self.env["stock.quant"].search([
                    ("product_id", "=", line.product_id.id),
                    ("location_id", "=", input_qc_location.id),
                    ("lot_id", "=", lot.id),
                ], limit=1)

                if quant:
                    quant.inventory_quantity = quant.quantity + line.quantity
                    quant.action_apply_inventory()
                else:
                    quant = self.env["stock.quant"].create({
                        "product_id": line.product_id.id,
                        "location_id": input_qc_location.id,
                        "lot_id": lot.id,
                        "inventory_quantity": line.quantity,
                    })
                    quant.action_apply_inventory()

            record.state = "submitted"


class VagirestProductionRecordLine(models.Model):
    _name = "vagirest.production.record.line"
    _description = "VAGIREST Production Record Line"

    record_id = fields.Many2one(
        "vagirest.production.record",
        string="Production Record",
        required=True,
        ondelete="cascade",
    )

    product_family = fields.Selection(
        [
            ("vd", "Vaginal Dilator"),
            ("rd", "Rectal Dilator"),
            ("pessary", "Pessary"),
            ("other", "Other"),
        ],
        string="Product Family",
        required=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
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

    @api.onchange("product_family")
    def _onchange_product_family(self):
        self.product_id = False

        base_domain = [
            ("type", "=", "product"),
            ("tracking", "=", "lot"),
            ("active", "=", True),
        ]

        if self.product_family == "vd":
            return {
                "domain": {
                    "product_id": base_domain + [
                        "|",
                        ("default_code", "ilike", "VD"),
                        ("name", "ilike", "واژینال"),
                    ]
                }
            }

        if self.product_family == "rd":
            return {
                "domain": {
                    "product_id": base_domain + [
                        "|",
                        ("default_code", "ilike", "RD"),
                        ("name", "ilike", "رکتال"),
                    ]
                }
            }

        if self.product_family == "pessary":
            return {
                "domain": {
                    "product_id": base_domain + [
                        ("name", "ilike", "پساری"),
                    ]
                }
            }

        return {"domain": {"product_id": base_domain}}

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

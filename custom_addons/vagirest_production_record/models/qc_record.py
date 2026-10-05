from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class VagirestQCRecord(models.Model):
    _name = "vagirest.qc.record"
    _description = "VAGIREST QC Record"
    _order = "id desc"

    _sql_constraints = [
        (
            "unique_production_record",
            "unique(production_record_id)",
            "Only one QC record may exist for each production record.",
        ),
    ]

    name = fields.Char(
        string="QC Number",
        default="New",
        readonly=True,
        copy=False,
    )

    active = fields.Boolean(
        default=True,
    )

    production_record_id = fields.Many2one(
        "vagirest.production.record",
        string="Production Record",
        required=True,
        readonly=True,
        ondelete="restrict",
    )

    production_date = fields.Date(
        related="production_record_id.production_date",
        store=True,
        readonly=True,
    )

    operator_id = fields.Many2one(
        related="production_record_id.operator_id",
        store=True,
        readonly=True,
    )

    inspector_id = fields.Many2one(
        "res.users",
        string="QC Inspector",
        readonly=True,
        copy=False,
    )

    decision_date = fields.Datetime(
        string="Decision Date",
        readonly=True,
        copy=False,
    )

    note = fields.Text(
        string="QC Notes",
    )

    line_ids = fields.One2many(
        "vagirest.qc.record.line",
        "qc_record_id",
        string="QC Decision Lines",
        copy=False,
    )

    approved_picking_id = fields.Many2one(
        "stock.picking",
        string="Approved Transfer",
        readonly=True,
        copy=False,
    )

    rework_picking_id = fields.Many2one(
        "stock.picking",
        string="Rework Transfer",
        readonly=True,
        copy=False,
    )

    rejected_picking_id = fields.Many2one(
        "stock.picking",
        string="Rejected Transfer",
        readonly=True,
        copy=False,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("done", "Decision Submitted"),
        ],
        default="draft",
        required=True,
        readonly=True,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"].with_company(
            self.env.company
        )

        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = sequence.next_by_code(
                    "vagirest.qc.record"
                ) or "New"

        records = super().create(vals_list)

        for record in records:
            record._sync_lines_from_production()

        return records

    def _sync_lines_from_production(self):
        line_model = self.env[
            "vagirest.qc.record.line"
        ].sudo().with_company(self.env.company)

        for record in self:
            if not record.production_record_id:
                continue

            existing_production_line_ids = set(
                record.line_ids.mapped(
                    "production_line_id"
                ).ids
            )

            for production_line in (
                record.production_record_id.line_ids
            ):
                if (
                    production_line.id
                    not in existing_production_line_ids
                ):
                    line_model.create({
                        "qc_record_id": record.id,
                        "production_line_id": (
                            production_line.id
                        ),
                    })

    def _get_qc_picking_type(
        self,
        picking_type_id,
        source_location_id,
        destination_location_id,
    ):
        picking_type = self.env[
            "stock.picking.type"
        ].sudo().with_company(
            self.env.company
        ).with_context(active_test=False).browse(
            picking_type_id
        ).exists()

        if not picking_type:
            raise UserError(
                _(
                    "QC Operation Type %s was not found."
                )
                % picking_type_id
            )

        if not picking_type.active:
            raise UserError(
                _(
                    "QC Operation Type %s is archived."
                )
                % picking_type.display_name
            )

        if (
            picking_type.company_id
            and picking_type.company_id
            != self.env.company
        ):
            raise UserError(
                _("The QC Operation Type belongs to another company.")
            )

        if (
            picking_type.default_location_src_id.id
            != source_location_id
            or
            picking_type.default_location_dest_id.id
            != destination_location_id
        ):
            raise UserError(
                _(
                    "The source or destination of QC "
                    "Operation Type %s is incorrect."
                )
                % picking_type.display_name
            )

        return picking_type

    def _validate_decision_lines(self):
        self.ensure_one()
        self._sync_lines_from_production()

        if self.state != "draft":
            raise UserError(
                _("Only draft QC records can be submitted.")
            )

        if (
            not self.production_record_id
            or self.production_record_id.state
            != "submitted"
        ):
            raise UserError(
                _(
                    "The related production record has not "
                    "been submitted to QC."
                )
            )

        if not self.line_ids:
            raise UserError(
                _("No production lines were found for this QC record.")
            )

        for line in self.line_ids:
            if not line.product_id:
                raise UserError(
                    _("A QC line does not have a product.")
                )

            if not line.lot_id:
                raise UserError(
                    _(
                        "Product %s does not have a production lot."
                    )
                    % line.product_id.display_name
                )

            quantities = [
                line.approved_qty,
                line.rework_qty,
                line.rejected_qty,
            ]

            if any(quantity < 0 for quantity in quantities):
                raise UserError(
                    _(
                        "QC quantities cannot be negative "
                        "for product %s."
                    )
                    % line.product_id.display_name
                )

            total_decided = (
                line.approved_qty
                + line.rework_qty
                + line.rejected_qty
            )

            rounding = line.product_uom_id.rounding or 0.01

            if float_compare(
                total_decided,
                line.produced_qty,
                precision_rounding=rounding,
            ) != 0:
                raise UserError(
                    _(
                        "For product %s, Approved + Rework "
                        "+ Rejected must equal the produced "
                        "quantity of %s."
                    )
                    % (
                        line.product_id.display_name,
                        line.produced_qty,
                    )
                )

            quants = self.env[
                "stock.quant"
            ].sudo().with_company(self.env.company).search([
                ("company_id", "=", self.env.company.id),
                ("location_id", "=", 40),
                ("product_id", "=", line.product_id.id),
                ("lot_id", "=", line.lot_id.id),
            ])

            available_quantity = sum(
                quants.mapped("quantity")
            ) - sum(
                quants.mapped("reserved_quantity")
            )

            if float_compare(
                available_quantity,
                line.produced_qty,
                precision_rounding=rounding,
            ) < 0:
                raise UserError(
                    _(
                        "There is not enough available stock "
                        "in input-QC for product %s and lot %s.\n"
                        "Required: %s\nAvailable: %s"
                    )
                    % (
                        line.product_id.display_name,
                        line.lot_id.name,
                        line.produced_qty,
                        available_quantity,
                    )
                )

    def _create_qc_transfer(
        self,
        picking_type_id,
        source_location_id,
        destination_location_id,
        quantity_field,
        decision_label,
    ):
        self.ensure_one()

        decision_lines = self.line_ids.filtered(
            lambda line: (
                line[quantity_field] > 0
            )
        )

        if not decision_lines:
            return False

        picking_type = self._get_qc_picking_type(
            picking_type_id,
            source_location_id,
            destination_location_id,
        )

        stock_picking_model = self.env[
            "stock.picking"
        ].sudo().with_company(self.env.company)

        stock_move_model = self.env[
            "stock.move"
        ].sudo().with_company(self.env.company)

        stock_move_line_model = self.env[
            "stock.move.line"
        ].sudo().with_company(self.env.company)

        picking = stock_picking_model.create({
            "picking_type_id": picking_type.id,
            "location_id": source_location_id,
            "location_dest_id": destination_location_id,
            "origin": (
                "%s / %s"
                % (
                    self.name,
                    self.production_record_id.name,
                )
            ),
            "company_id": self.env.company.id,
        })

        move_data = []

        for line in decision_lines:
            quantity = line[quantity_field]

            move = stock_move_model.create({
                "name": (
                    "%s - %s"
                    % (
                        decision_label,
                        line.product_id.display_name,
                    )
                ),
                "origin": self.name,
                "product_id": line.product_id.id,
                "product_uom_qty": quantity,
                "product_uom": line.product_uom_id.id,
                "location_id": source_location_id,
                "location_dest_id": destination_location_id,
                "picking_id": picking.id,
                "company_id": self.env.company.id,
            })

            move_data.append(
                (line, move, quantity)
            )

        picking.action_confirm()

        for line, move, quantity in move_data:
            stock_move_line_model.create({
                "move_id": move.id,
                "picking_id": picking.id,
                "company_id": self.env.company.id,
                "product_id": line.product_id.id,
                "product_uom_id": line.product_uom_id.id,
                "quantity": quantity,
                "picked": True,
                "lot_id": line.lot_id.id,
                "location_id": source_location_id,
                "location_dest_id": destination_location_id,
            })

        validation_result = picking.with_context(
            cancel_backorder=True
        ).button_validate()

        if picking.state != "done":
            if isinstance(validation_result, dict):
                raise UserError(
                    _(
                        "The %s transfer requires an "
                        "unexpected validation wizard."
                    )
                    % decision_label
                )

            raise UserError(
                _(
                    "The %s stock transfer was not completed."
                )
                % decision_label
            )

        return picking

    def action_submit_decision(self):
        if not self.env.user.has_group(
            "vagirest_production_record."
            "group_vagirest_qc_manager"
        ):
            raise UserError(
                _(
                    "You do not have permission "
                    "to submit QC decisions."
                )
            )

        for record in self:
            if (
                record.operator_id
                and record.operator_id == self.env.user
            ):
                raise UserError(
                    _(
                        "The QC inspector must be different "
                        "from the production operator."
                    )
                )

            record._validate_decision_lines()

            approved_picking = record._create_qc_transfer(
                picking_type_id=51,
                source_location_id=40,
                destination_location_id=41,
                quantity_field="approved_qty",
                decision_label="QC Approved",
            )

            rework_picking = record._create_qc_transfer(
                picking_type_id=52,
                source_location_id=40,
                destination_location_id=76,
                quantity_field="rework_qty",
                decision_label="QC Rework",
            )

            rejected_picking = record._create_qc_transfer(
                picking_type_id=53,
                source_location_id=40,
                destination_location_id=77,
                quantity_field="rejected_qty",
                decision_label="QC Rejected",
            )

            record.write({
                "inspector_id": self.env.user.id,
                "decision_date": fields.Datetime.now(),
                "approved_picking_id": (
                    approved_picking.id
                    if approved_picking
                    else False
                ),
                "rework_picking_id": (
                    rework_picking.id
                    if rework_picking
                    else False
                ),
                "rejected_picking_id": (
                    rejected_picking.id
                    if rejected_picking
                    else False
                ),
                "state": "done",
            })

        return True

    def write(self, vals):
        allowed_done_fields = {
            "correction_reason",
        }

        protected_fields = set(vals) - allowed_done_fields

        if (
            not self.env.context.get("allow_qc_correction")
            and protected_fields
            and any(record.state == "done" for record in self)
        ):
            raise UserError(
                _("Submitted QC records cannot be modified.")
            )

        return super().write(vals)

    def unlink(self):
        done_records = self.filtered(
            lambda record: record.state == "done"
        )

        if done_records:
            raise UserError(
                _("Submitted QC records cannot be deleted.")
            )

        return super().unlink()


class VagirestQCRecordLine(models.Model):
    _name = "vagirest.qc.record.line"
    _description = "VAGIREST QC Record Line"
    _order = "id"

    _sql_constraints = [
        (
            "unique_qc_production_line",
            "unique(qc_record_id, production_line_id)",
            "This production line already exists in the QC record.",
        ),
    ]

    qc_record_id = fields.Many2one(
        "vagirest.qc.record",
        string="QC Record",
        required=True,
        ondelete="cascade",
    )

    production_line_id = fields.Many2one(
        "vagirest.production.record.line",
        string="Production Line",
        required=True,
        readonly=True,
        ondelete="restrict",
    )

    product_id = fields.Many2one(
        related="production_line_id.product_id",
        string="Product",
        store=True,
        readonly=True,
    )

    product_uom_id = fields.Many2one(
        related="production_line_id.product_id.uom_id",
        string="Unit of Measure",
        store=True,
        readonly=True,
    )

    lot_id = fields.Many2one(
        related="production_line_id.lot_id",
        string="Lot",
        store=True,
        readonly=True,
    )

    produced_qty = fields.Float(
        related="production_line_id.quantity",
        string="Produced",
        store=True,
        readonly=True,
    )

    approved_qty = fields.Float(
        string="Approved",
        default=0.0,
    )

    rework_qty = fields.Float(
        string="Rework",
        default=0.0,
    )

    rejected_qty = fields.Float(
        string="Rejected",
        default=0.0,
    )

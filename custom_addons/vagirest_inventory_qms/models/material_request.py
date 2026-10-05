from odoo import api, fields, models, _
from odoo.exceptions import UserError


class VagirestMaterialRequest(models.Model):
    _name = "vagirest.material.request"
    _description = "F01 - درخواست کالا از انبار"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="شماره درخواست",
        default="/",
        readonly=True,
        copy=False,
        tracking=True,
    )

    document_code = fields.Char(
        string="کد سند",
        default="F01-ST/00",
        readonly=True,
    )

    request_date = fields.Date(
        string="تاریخ درخواست",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )

    requester_id = fields.Many2one(
        "res.users",
        string="درخواست‌کننده",
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
        tracking=True,
    )

    requesting_unit = fields.Char(
        string="واحد درخواست‌کننده",
        required=True,
    )

    warehouse_receiver_id = fields.Many2one(
        "res.users",
        string="دریافت‌کننده در انبار",
        readonly=True,
        copy=False,
    )

    warehouse_received_at = fields.Datetime(
        string="تاریخ دریافت توسط انبار",
        readonly=True,
        copy=False,
    )

    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
        readonly=True,
    )

    state = fields.Selection(
        [
            ("draft", "پیش‌نویس"),
            ("submitted", "ارسال‌شده"),
            ("warehouse_received", "دریافت‌شده توسط انبار"),
            ("ready", "آماده تحویل"),
            ("done", "تکمیل‌شده"),
            ("cancelled", "لغوشده"),
        ],
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )

    line_ids = fields.One2many(
        "vagirest.material.request.line",
        "request_id",
        string="اقلام درخواستی",
        copy=True,
    )

    delivery_id = fields.Many2one(
        "vagirest.warehouse.delivery",
        string="برگه تحویل F04",
        readonly=True,
        copy=False,
    )

    note = fields.Text(string="توضیحات")

    company_logo = fields.Binary(
        related="company_id.logo",
        string="لوگوی شرکت",
        readonly=True,
    )

    warehouse_responsible_id = fields.Many2one(
        "res.users",
        string="مسئول انبار",
        compute="_compute_warehouse_responsible_id",
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for rec in records:
            if rec.name == "/":
                rec.name = (
                    self.env["ir.sequence"].next_by_code(
                        "vagirest.material.request"
                    )
                    or "/"
                )

        return records

    def _check_warehouse_receiver(self):
        if not self.env.user.has_group(
            "vagirest_inventory_qms."
            "group_vagirest_warehouse_receiver"
        ):
            raise UserError(
                _("فقط مسئول انبار مجاز به این عملیات است.")
            )

    def _is_erp_manager(self):
        return self.env.user.has_group(
            "vagirest_production_record."
            "group_vagirest_erp_manager"
        )

    def write(self, vals):
        if (
            self.env.context.get("allow_f01_workflow_write")
            or self._is_erp_manager()
        ):
            return super().write(vals)

        for rec in self:
            if rec.state != "draft":
                raise UserError(
                    _(
                        "پس از ارسال درخواست، اطلاعات F01 "
                        "قابل ویرایش مستقیم نیست."
                    )
                )

            if rec.requester_id != self.env.user:
                raise UserError(
                    _("فقط ثبت‌کننده می‌تواند پیش‌نویس خود را ویرایش کند.")
                )

        protected = {
            "requester_id",
            "company_id",
            "warehouse_receiver_id",
            "warehouse_received_at",
            "delivery_id",
            "state",
        }

        if protected.intersection(vals):
            raise UserError(
                _("تغییر مستقیم فیلدهای سیستمی F01 مجاز نیست.")
            )

        return super().write(vals)

    def action_submit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(
                    _("فقط درخواست پیش‌نویس قابل ارسال است.")
                )

            if rec.requester_id != self.env.user:
                raise UserError(
                    _("فقط ثبت‌کننده می‌تواند درخواست را ارسال کند.")
                )

            if not rec.line_ids:
                raise UserError(
                    _("حداقل یک قلم کالا ثبت کنید.")
                )

            for line in rec.line_ids:
                if line.requested_qty <= 0:
                    raise UserError(
                        _("مقدار درخواستی باید بیشتر از صفر باشد.")
                    )

            rec.with_context(
                allow_f01_workflow_write=True
            ).write({
                "state": "submitted",
            })

        return True

    def action_receive_warehouse(self):
        self._check_warehouse_receiver()

        for rec in self:
            if rec.state != "submitted":
                raise UserError(
                    _("فقط درخواست ارسال‌شده قابل دریافت است.")
                )

            rec.with_context(
                allow_f01_workflow_write=True
            ).write({
                "state": "warehouse_received",
                "warehouse_receiver_id": self.env.user.id,
                "warehouse_received_at": fields.Datetime.now(),
            })

        return True

    def action_create_f04(self):
        self._check_warehouse_receiver()

        Delivery = self.env["vagirest.warehouse.delivery"]

        for rec in self:
            if rec.state != "warehouse_received":
                raise UserError(
                    _("ابتدا درخواست باید توسط انبار دریافت شود.")
                )

            if rec.delivery_id:
                raise UserError(
                    _("برای این درخواست قبلاً F04 ایجاد شده است.")
                )

            delivery = Delivery.create({
                "request_id": rec.id,
                "recipient_id": rec.requester_id.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "request_line_id": line.id,
                            "product_id": line.product_id.id,
                            "requested_qty": line.requested_qty,
                            "uom_id": line.uom_id.id,
                            "requested_serial_or_lot": line.serial_or_lot,
                            "usage_location": line.usage_location,
                            "note": line.note,
                        },
                    )
                    for line in rec.line_ids
                ],
            })

            rec.with_context(
                allow_f01_workflow_write=True
            ).write({
                "delivery_id": delivery.id,
                "state": "ready",
            })

        return True

    def action_open_f04(self):
        self.ensure_one()

        if not self.delivery_id:
            raise UserError(_("F04 ایجاد نشده است."))

        return {
            "type": "ir.actions.act_window",
            "res_model": "vagirest.warehouse.delivery",
            "res_id": self.delivery_id.id,
            "view_mode": "form",
            "target": "current",
        }


class VagirestMaterialRequestLine(models.Model):
    _name = "vagirest.material.request.line"
    _description = "F01 - ردیف درخواست کالا"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)

    request_id = fields.Many2one(
        "vagirest.material.request",
        required=True,
        ondelete="cascade",
    )

    product_id = fields.Many2one(
        "product.product",
        string="کالا",
        required=True,
    )

    product_code = fields.Char(
        string="کد کالا",
        related="product_id.default_code",
        readonly=True,
    )

    description = fields.Char(
        string="شرح کالا",
        required=True,
    )

    serial_or_lot = fields.Char(
        string="شماره سریال / سری ساخت",
    )

    requested_qty = fields.Float(
        string="مقدار درخواستی",
        required=True,
        default=1.0,
    )

    delivered_qty = fields.Float(
        string="مقدار تحویل‌شده",
        readonly=True,
        copy=False,
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="واحد",
        required=True,
    )

    usage_location = fields.Char(
        string="محل مصرف",
    )

    note = fields.Char(
        string="توضیحات",
    )

    def _check_parent_editable(self):
        if self.env.context.get("allow_f01_workflow_write"):
            return

        if self.env.user.has_group(
            "vagirest_production_record."
            "group_vagirest_erp_manager"
        ):
            return

        for line in self:
            req = line.request_id

            if req.state != "draft":
                raise UserError(
                    _("ردیف‌های F01 پس از ارسال قابل ویرایش نیستند.")
                )

            if req.requester_id != self.env.user:
                raise UserError(
                    _("فقط ثبت‌کننده می‌تواند ردیف‌های درخواست خود را تغییر دهد.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_parent_editable()
        return records

    def write(self, vals):
        self._check_parent_editable()
        return super().write(vals)

    def unlink(self):
        self._check_parent_editable()
        return super().unlink()

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.description = line.product_id.display_name
                line.uom_id = line.product_id.uom_id


class VagirestWarehouseDelivery(models.Model):
    _name = "vagirest.warehouse.delivery"
    _description = "F04 - برگه تحویل و مجوز خروج انبار"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="شماره",
        default="/",
        readonly=True,
        copy=False,
        tracking=True,
    )

    document_code = fields.Char(
        string="کد سند",
        default="F04-ST/00",
        readonly=True,
    )

    delivery_date = fields.Date(
        string="تاریخ",
        default=fields.Date.context_today,
        required=True,
    )

    permit_number = fields.Char(
        string="شماره مجوز",
    )

    request_id = fields.Many2one(
        "vagirest.material.request",
        string="درخواست F01",
        required=True,
        readonly=True,
        ondelete="restrict",
    )

    recipient_id = fields.Many2one(
        "res.users",
        string="تحویل‌گیرنده",
        required=True,
        readonly=True,
    )

    warehouse_user_id = fields.Many2one(
        "res.users",
        string="مسئول انبار",
        default=lambda self: self.env.user,
        readonly=True,
    )

    technical_manager_id = fields.Many2one(
        "res.users",
        string="مسئول فنی",
    )

    company_id = fields.Many2one(
        related="request_id.company_id",
        store=True,
        readonly=True,
    )

    state = fields.Selection(
        [
            ("draft", "در حال تکمیل"),
            ("ready", "آماده تحویل"),
            ("done", "تحویل‌شده"),
            ("cancelled", "لغوشده"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )

    line_ids = fields.One2many(
        "vagirest.warehouse.delivery.line",
        "delivery_id",
        string="اقلام تحویلی",
    )

    note = fields.Text(string="توضیحات")

    company_logo = fields.Binary(
        related="company_id.logo",
        string="لوگوی شرکت",
        readonly=True,
    )

    warehouse_responsible_id = fields.Many2one(
        "res.users",
        string="مسئول انبار",
        compute="_compute_warehouse_responsible_id",
        readonly=True,
    )

    destination_location_id = fields.Many2one(
        "stock.location",
        string="محل تحویل / مقصد",
        domain=[
            ("usage", "=", "internal"),
        ],
        tracking=True,
    )

    picking_ids = fields.Many2many(
        "stock.picking",
        "vagirest_f04_stock_picking_rel",
        "delivery_id",
        "picking_id",
        string="انتقالات انبار",
        readonly=True,
        copy=False,
    )

    finalized_by_id = fields.Many2one(
        "res.users",
        string="تحویل نهایی توسط",
        readonly=True,
        copy=False,
    )

    finalized_at = fields.Datetime(
        string="زمان تحویل نهایی",
        readonly=True,
        copy=False,
    )

    reverse_reason = fields.Text(
        string="علت اصلاح / برگشت",
        copy=False,
        tracking=True,
    )

    reverse_picking_ids = fields.Many2many(
        "stock.picking",
        "vagirest_f04_reverse_picking_rel",
        "delivery_id",
        "picking_id",
        string="انتقالات برگشتی",
        readonly=True,
        copy=False,
    )

    reversed_by_id = fields.Many2one(
        "res.users",
        string="برگشت توسط",
        readonly=True,
        copy=False,
    )

    reversed_at = fields.Datetime(
        string="زمان برگشت",
        readonly=True,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for rec in records:
            if rec.name == "/":
                rec.name = (
                    self.env["ir.sequence"].next_by_code(
                        "vagirest.warehouse.delivery"
                    )
                    or "/"
                )

        return records

    def _check_warehouse_receiver(self):
        if not self.env.user.has_group(
            "vagirest_inventory_qms."
            "group_vagirest_warehouse_receiver"
        ):
            raise UserError(
                _("فقط مسئول انبار مجاز به این عملیات است.")
            )

    def _is_erp_manager(self):
        return self.env.user.has_group(
            "vagirest_production_record."
            "group_vagirest_erp_manager"
        )

    def write(self, vals):
        if (
            self.env.context.get("allow_f04_workflow_write")
            or self._is_erp_manager()
        ):
            return super().write(vals)

        for rec in self:
            if rec.state != "draft":
                raise UserError(
                    _(
                        "F04 پس از آماده تحویل شدن "
                        "قابل ویرایش مستقیم نیست."
                    )
                )

        protected = {
            "request_id",
            "recipient_id",
            "warehouse_user_id",
            "company_id",
            "state",
            "picking_ids",
            "finalized_by_id",
            "finalized_at",
            "reverse_picking_ids",
            "reversed_by_id",
            "reversed_at",
        }

        if protected.intersection(vals):
            raise UserError(
                _("تغییر مستقیم فیلدهای سیستمی F04 مجاز نیست.")
            )

        return super().write(vals)

    def action_mark_ready(self):
        self.ensure_one()

        if not self.env.user.has_group(
            "vagirest_inventory_qms."
            "group_vagirest_warehouse_receiver"
        ):
            raise UserError(
                _("فقط مسئول انبار مجاز به این عملیات است.")
            )

        if not self.destination_location_id:
            raise UserError(
                _("محل مقصد / تحویل را مشخص کنید.")
            )

        positive_lines = self.line_ids.filtered(
            lambda line: line.delivered_qty > 0
        )

        if not positive_lines:
            raise UserError(
                _("حداقل یک قلم با مقدار تحویلی بیشتر از صفر لازم است.")
            )

        for line in self.line_ids:
            if line.delivered_qty < 0:
                raise UserError(
                    _("مقدار تحویلی نمی‌تواند منفی باشد.")
                )

            if line.delivered_qty > line.requested_qty:
                raise UserError(
                    _("مقدار تحویلی بیشتر از مقدار درخواستی است.")
                )

            if line.delivered_qty > 0:
                if not line.source_location_id:
                    raise UserError(
                        _(
                            "برای کالای %s محل برداشت از انبار را مشخص کنید."
                        )
                        % line.product_id.display_name
                    )

                if (
                    line.source_location_id
                    == self.destination_location_id
                ):
                    raise UserError(
                        _(
                            "مبدأ و مقصد کالای %s نمی‌توانند یکسان باشند."
                        )
                        % line.product_id.display_name
                    )

                if (
                    line.product_id.tracking != "none"
                    and not line.lot_id
                ):
                    raise UserError(
                        _(
                            "برای کالای رهگیری‌شونده %s "
                            "Lot / سری ساخت را مشخص کنید."
                        )
                        % line.product_id.display_name
                    )

                if (
                    line.lot_id
                    and line.lot_id.product_id
                    != line.product_id
                ):
                    raise UserError(
                        _(
                            "Lot انتخاب‌شده متعلق به کالای %s نیست."
                        )
                        % line.product_id.display_name
                    )

                if (
                    line.product_id.tracking == "serial"
                    and line.delivered_qty > 1
                ):
                    raise UserError(
                        _(
                            "برای کالای سریال‌دار %s در هر ردیف "
                            "فقط یک واحد قابل تحویل است."
                        )
                        % line.product_id.display_name
                    )

        self.with_context(
            allow_f04_workflow_write=True
        ).write({
            "state": "ready",
        })

        return True



    def _available_quantity(
        self,
        product,
        lot,
        location,
        company,
    ):
        domain = [
            ("company_id", "=", company.id),
            ("location_id", "=", location.id),
            ("product_id", "=", product.id),
        ]

        if lot:
            domain.append(
                ("lot_id", "=", lot.id)
            )

        quants = self.env[
            "stock.quant"
        ].sudo().search(domain)

        return (
            sum(quants.mapped("quantity"))
            - sum(
                quants.mapped(
                    "reserved_quantity"
                )
            )
        )

    def _get_f04_picking_type(
        self,
        source_location,
        destination_location,
    ):
        self.ensure_one()

        company = self.company_id

        PickingType = self.env[
            "stock.picking.type"
        ].sudo().with_company(company)

        picking_type = PickingType.search(
            [
                ("code", "=", "internal"),
                ("company_id", "=", company.id),
                ("sequence_code", "=", "F04"),
            ],
            limit=1,
        )

        if not picking_type:
            warehouse = self.env[
                "stock.warehouse"
            ].sudo().search(
                [
                    ("company_id", "=", company.id),
                ],
                limit=1,
            )

            vals = {
                "name": "F04 - تحویل کالا از انبار",
                "code": "internal",
                "sequence_code": "F04",
                "company_id": company.id,
                "default_location_src_id": (
                    source_location.id
                ),
                "default_location_dest_id": (
                    destination_location.id
                ),
            }

            if warehouse:
                vals["warehouse_id"] = warehouse.id

            picking_type = PickingType.create(
                vals
            )

        return picking_type

    def _create_and_validate_stock_picking(
        self,
        source_location,
        destination_location,
        lines,
    ):
        self.ensure_one()

        company = self.company_id

        picking_type = (
            self._get_f04_picking_type(
                source_location,
                destination_location,
            )
        )

        Picking = self.env[
            "stock.picking"
        ].sudo().with_company(company)

        Move = self.env[
            "stock.move"
        ].sudo().with_company(company)

        MoveLine = self.env[
            "stock.move.line"
        ].sudo().with_company(company)

        origin = "%s / %s" % (
            self.name,
            self.request_id.name,
        )

        picking = Picking.create({
            "picking_type_id": (
                picking_type.id
            ),
            "location_id": (
                source_location.id
            ),
            "location_dest_id": (
                destination_location.id
            ),
            "origin": origin,
            "company_id": company.id,
        })

        created = []

        for line in lines:
            qty = line.delivered_qty

            move = Move.create({
                "name": (
                    line.product_id.display_name
                ),
                "origin": origin,
                "product_id": (
                    line.product_id.id
                ),
                "product_uom_qty": qty,
                "product_uom": (
                    line.uom_id.id
                ),
                "location_id": (
                    source_location.id
                ),
                "location_dest_id": (
                    destination_location.id
                ),
                "picking_id": picking.id,
                "company_id": company.id,
            })

            created.append(
                (move, line, qty)
            )

        picking.action_confirm()

        for move, line, qty in created:

            MoveLine.create({
                "move_id": move.id,
                "picking_id": picking.id,
                "company_id": company.id,
                "product_id": (
                    line.product_id.id
                ),
                "product_uom_id": (
                    line.uom_id.id
                ),
                "quantity": qty,
                "picked": True,
                "lot_id": (
                    line.lot_id.id
                    if line.lot_id
                    else False
                ),
                "location_id": (
                    source_location.id
                ),
                "location_dest_id": (
                    destination_location.id
                ),
            })

        result = picking.with_context(
            cancel_backorder=True
        ).button_validate()

        if picking.state != "done":
            if isinstance(result, dict):
                raise UserError(
                    _(
                        "تأیید انتقال انبار نیازمند "
                        "Wizard غیرمنتظره بود."
                    )
                )

            raise UserError(
                _("انتقال انبار نهایی نشد.")
            )

        return picking


    def _reverse_done_picking(self, picking):
        self.ensure_one()

        if picking.state != "done":
            raise UserError(
                _("فقط انتقال Done قابل برگشت است.")
            )

        company = self.company_id

        Picking = self.env[
            "stock.picking"
        ].sudo().with_company(company)

        Move = self.env[
            "stock.move"
        ].sudo().with_company(company)

        MoveLine = self.env[
            "stock.move.line"
        ].sudo().with_company(company)

        original_lines = (
            picking.move_line_ids.filtered(
                lambda ml: ml.quantity > 0
            )
        )

        if not original_lines:
            raise UserError(
                _(
                    "انتقال اصلی هیچ حرکت واقعی "
                    "برای برگشت ندارد."
                )
            )

        # IMPORTANT:
        # Check available stock BEFORE creating /
        # confirming the reverse picking.
        #
        # action_confirm() may reserve the same stock,
        # which would make available_quantity appear
        # artificially zero.
        for original_ml in original_lines:

            available = self._available_quantity(
                original_ml.product_id,
                original_ml.lot_id,
                original_ml.location_dest_id,
                company,
            )

            if (
                available
                + 1e-9
                < original_ml.quantity
            ):
                raise UserError(
                    _(
                        "موجودی برای برگشت %s کافی نیست. "
                        "موجودی قابل استفاده: %s - "
                        "مقدار لازم برای برگشت: %s"
                    )
                    % (
                        original_ml.product_id.display_name,
                        available,
                        original_ml.quantity,
                    )
                )

        reverse_type = (
            self._get_f04_picking_type(
                picking.location_dest_id,
                picking.location_id,
            )
        )

        reverse = Picking.create({
            "picking_type_id": reverse_type.id,
            "location_id": (
                picking.location_dest_id.id
            ),
            "location_dest_id": (
                picking.location_id.id
            ),
            "origin": "REV/%s/%s" % (
                self.name,
                picking.name,
            ),
            "company_id": company.id,
        })

        created = []

        for original_ml in original_lines:

            move = Move.create({
                "name": (
                    original_ml.product_id.display_name
                ),
                "origin": reverse.origin,
                "product_id": (
                    original_ml.product_id.id
                ),
                "product_uom_qty": (
                    original_ml.quantity
                ),
                "product_uom": (
                    original_ml.product_uom_id.id
                ),
                "location_id": (
                    original_ml.location_dest_id.id
                ),
                "location_dest_id": (
                    original_ml.location_id.id
                ),
                "picking_id": reverse.id,
                "company_id": company.id,
            })

            created.append(
                (move, original_ml)
            )

        reverse.action_confirm()

        for move, original_ml in created:

            MoveLine.create({
                "move_id": move.id,
                "picking_id": reverse.id,
                "company_id": company.id,
                "product_id": (
                    original_ml.product_id.id
                ),
                "product_uom_id": (
                    original_ml.product_uom_id.id
                ),
                "quantity": (
                    original_ml.quantity
                ),
                "picked": True,
                "lot_id": (
                    original_ml.lot_id.id
                    if original_ml.lot_id
                    else False
                ),
                "location_id": (
                    original_ml.location_dest_id.id
                ),
                "location_dest_id": (
                    original_ml.location_id.id
                ),
            })

        result = reverse.with_context(
            cancel_backorder=True
        ).button_validate()

        if reverse.state != "done":

            if isinstance(result, dict):
                raise UserError(
                    _(
                        "برگشت انتقال نیازمند Wizard "
                        "غیرمنتظره بود."
                    )
                )

            raise UserError(
                _("انتقال برگشتی نهایی نشد.")
            )

        return reverse


    def action_reverse_delivery(self):
        self.ensure_one()

        self._check_warehouse_receiver()

        if self.state != "done":
            raise UserError(
                _("فقط F04 نهایی‌شده قابل برگشت است.")
            )

        if self.reverse_picking_ids:
            raise UserError(
                _("این F04 قبلاً برگشت داده شده است.")
            )

        if not self.reverse_reason:
            raise UserError(
                _("علت اصلاح / برگشت را وارد کنید.")
            )

        if not self.picking_ids:
            raise UserError(
                _("هیچ انتقال انبار اصلی برای برگشت وجود ندارد.")
            )

        reverses = self.env["stock.picking"]

        for picking in self.picking_ids:
            reverses |= self._reverse_done_picking(
                picking
            )

        # reset F01 actual delivered quantities
        for line in self.line_ids:
            if line.request_line_id:
                line.request_line_id.with_context(
                    allow_f01_workflow_write=True
                ).write({
                    "delivered_qty": 0,
                })

        self.request_id.with_context(
            allow_f01_workflow_write=True
        ).write({
            "state": "warehouse_received",
            "delivery_id": False,
        })

        self.with_context(
            allow_f04_workflow_write=True
        ).write({
            "state": "cancelled",
            "reverse_picking_ids": [
                (6, 0, reverses.ids)
            ],
            "reversed_by_id": (
                self.env.user.id
            ),
            "reversed_at": (
                fields.Datetime.now()
            ),
        })

        return True


    def action_finalize_delivery(self):
        self.ensure_one()

        self._check_warehouse_receiver()

        if self.state != "ready":
            raise UserError(
                _(
                    "فقط F04 در وضعیت آماده تحویل "
                    "قابل نهایی‌سازی است."
                )
            )

        if self.picking_ids:
            raise UserError(
                _(
                    "برای این F04 قبلاً انتقال "
                    "انبار ثبت شده است."
                )
            )

        if not self.destination_location_id:
            raise UserError(
                _("محل مقصد مشخص نشده است.")
            )

        company = self.company_id

        lines = self.line_ids.filtered(
            lambda line: (
                line.delivered_qty > 0
            )
        )

        if not lines:
            raise UserError(
                _("هیچ مقدار تحویلی ثبت نشده است.")
            )

        grouped = {}

        for line in lines:

            source = line.source_location_id

            if not source:
                raise UserError(
                    _(
                        "محل برداشت کالای %s "
                        "مشخص نشده است."
                    )
                    % line.product_id.display_name
                )

            lot = (
                line.lot_id
                if line.product_id.tracking
                != "none"
                else False
            )

            available = (
                self._available_quantity(
                    line.product_id,
                    lot,
                    source,
                    company,
                )
            )

            if (
                available
                + 1e-9
                < line.delivered_qty
            ):
                raise UserError(
                    _(
                        "موجودی قابل استفاده برای %s "
                        "در %s کافی نیست. "
                        "موجودی قابل استفاده: %s - "
                        "مقدار تحویل: %s"
                    )
                    % (
                        line.product_id.display_name,
                        source.display_name,
                        available,
                        line.delivered_qty,
                    )
                )

            grouped.setdefault(
                source.id,
                self.env[
                    "vagirest."
                    "warehouse.delivery.line"
                ],
            )

            grouped[source.id] |= line

        pickings = self.env["stock.picking"]

        for source_id, group_lines in (
            grouped.items()
        ):
            source = self.env[
                "stock.location"
            ].sudo().browse(source_id)

            picking = (
                self._create_and_validate_stock_picking(
                    source,
                    self.destination_location_id,
                    group_lines,
                )
            )

            pickings |= picking

        # Copy actual delivered quantities to F01.
        for line in lines:
            if line.request_line_id:
                line.request_line_id.with_context(
                    allow_f01_workflow_write=True
                ).write({
                    "delivered_qty": (
                        line.delivered_qty
                    ),
                })

        self.request_id.with_context(
            allow_f01_workflow_write=True
        ).write({
            "state": "done",
        })

        self.with_context(
            allow_f04_workflow_write=True
        ).write({
            "state": "done",
            "picking_ids": [
                (6, 0, pickings.ids)
            ],
            "finalized_by_id": (
                self.env.user.id
            ),
            "finalized_at": (
                fields.Datetime.now()
            ),
        })

        return True


class VagirestWarehouseDeliveryLine(models.Model):
    _name = "vagirest.warehouse.delivery.line"
    _description = "F04 - ردیف تحویل کالا"

    delivery_id = fields.Many2one(
        "vagirest.warehouse.delivery",
        required=True,
        ondelete="cascade",
    )

    request_line_id = fields.Many2one(
        "vagirest.material.request.line",
        readonly=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="کالا",
        required=True,
        readonly=True,
    )

    requested_qty = fields.Float(
        string="مقدار درخواستی",
        readonly=True,
    )

    delivered_qty = fields.Float(
        string="مقدار تحویلی",
        default=0.0,
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="واحد",
        required=True,
        readonly=True,
    )

    requested_serial_or_lot = fields.Char(
        string="سری/لات درخواستی",
        readonly=True,
    )

    company_id = fields.Many2one(
        "res.company",
        related="delivery_id.company_id",
        store=True,
        readonly=True,
    )

    source_location_id = fields.Many2one(
        "stock.location",
        string="محل برداشت از انبار",
        domain=[
            ("usage", "=", "internal"),
        ],
    )

    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot / سری ساخت واقعی",
        domain="[('product_id', '=', product_id)]",
    )

    usage_location = fields.Char(
        string="محل مصرف",
        readonly=True,
    )

    note = fields.Char(
        string="توضیحات",
    )


    def _check_delivery_editable(self):
        if self.env.context.get("allow_f04_workflow_write"):
            return

        if self.env.user.has_group(
            "vagirest_production_record."
            "group_vagirest_erp_manager"
        ):
            return

        for line in self:
            if line.delivery_id.state != "draft":
                raise UserError(
                    _("ردیف‌های F04 پس از آماده تحویل شدن قابل ویرایش نیستند.")
                )

    def write(self, vals):
        self._check_delivery_editable()
        return super().write(vals)

    def unlink(self):
        self._check_delivery_editable()
        return super().unlink()

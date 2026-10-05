from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class VagirestRawMaterialReceipt(models.Model):
    _name = "vagirest.raw.material.receipt"
    _description = "VAGIREST Raw Material Receipt F02"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "receipt_date desc, id desc"

    name = fields.Char(
        string="شماره",
        default="New",
        readonly=True,
        copy=False,
        tracking=True,
    )

    form_code = fields.Char(
        string="کد سند",
        default="F02-ST/00",
        readonly=True,
        copy=False,
    )

    receipt_date = fields.Date(
        string="تاریخ",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )

    warehouse_keeper_id = fields.Many2one(
        "res.users",
        string="انباردار",
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
        tracking=True,
    )

    supplier_id = fields.Many2one(
        "res.partner",
        string="فروشنده / تأمین‌کننده",
        required=True,
        tracking=True,
    )

    invoice_reference = fields.Char(
        string="شماره بارنامه / فاکتور",
        tracking=True,
    )

    delivered_by = fields.Char(
        string="تحویل‌دهنده",
        tracking=True,
    )

    delivery_datetime = fields.Datetime(
        string="تاریخ و ساعت تحویل",
        tracking=True,
    )

    control_report_no = fields.Char(
        string="شماره گزارش کنترل",
        tracking=True,
    )

    note = fields.Text(
        string="توضیحات",
        tracking=True,
    )

    line_ids = fields.One2many(
        "vagirest.raw.material.receipt.line",
        "receipt_id",
        string="اقلام",
        copy=True,
    )

    state = fields.Selection(
        [
            ("draft", "پیش‌نویس"),
            ("received", "دریافت‌شده / منتظر QC"),
            ("approved", "تأیید QC"),
            ("rejected", "رد QC"),
            ("mixed", "تأیید/رد ترکیبی"),
            ("cancelled", "لغو شده"),
        ],
        string="وضعیت",
        default="draft",
        required=True,
        readonly=True,
        tracking=True,
        copy=False,
    )

    qc_inspector_id = fields.Many2one(
        "res.users",
        string="بازرسی‌کننده / QC",
        readonly=True,
        tracking=True,
        copy=False,
    )

    qc_decision_date = fields.Datetime(
        string="تاریخ تصمیم QC",
        readonly=True,
        tracking=True,
        copy=False,
    )

    incoming_picking_id = fields.Many2one(
        "stock.picking",
        string="رسید انبار / ورود به input-QC",
        readonly=True,
        copy=False,
        tracking=True,
    )

    raw_approved_picking_id = fields.Many2one(
        "stock.picking",
        string="انتقال مواد اولیه تأییدشده",
        readonly=True,
        copy=False,
    )

    packaging_approved_picking_id = fields.Many2one(
        "stock.picking",
        string="انتقال بسته‌بندی تأییدشده",
        readonly=True,
        copy=False,
    )

    rejected_picking_id = fields.Many2one(
        "stock.picking",
        string="انتقال اقلام ردشده",
        readonly=True,
        copy=False,
    )

    correction_reason = fields.Text(
        string="علت اصلاح",
        copy=False,
        tracking=True,
    )

    correction_count = fields.Integer(
        string="تعداد اصلاح",
        default=0,
        readonly=True,
        copy=False,
    )

    last_corrected_by_id = fields.Many2one(
        "res.users",
        string="آخرین اصلاح توسط",
        readonly=True,
        copy=False,
    )

    last_correction_date = fields.Datetime(
        string="تاریخ آخرین اصلاح",
        readonly=True,
        copy=False,
    )

    last_correction_reason = fields.Text(
        string="علت آخرین اصلاح",
        readonly=True,
        copy=False,
    )

    incoming_reversal_picking_id = fields.Many2one(
        "stock.picking",
        string="Reverse رسید ورودی",
        readonly=True,
        copy=False,
    )

    raw_approved_reversal_picking_id = fields.Many2one(
        "stock.picking",
        string="Reverse مواد اولیه تأییدشده",
        readonly=True,
        copy=False,
    )

    packaging_approved_reversal_picking_id = fields.Many2one(
        "stock.picking",
        string="Reverse بسته‌بندی تأییدشده",
        readonly=True,
        copy=False,
    )

    rejected_reversal_picking_id = fields.Many2one(
        "stock.picking",
        string="Reverse اقلام ردشده",
        readonly=True,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].with_company(self.env.company)

        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    seq.next_by_code("vagirest.raw.material.receipt")
                    or "New"
                )

            vals.setdefault("warehouse_keeper_id", self.env.user.id)

        return super().create(vals_list)

    def _check_f02_user(self):
        if not self.env.user.has_group(
            "vagirest_inventory_qms.group_vagirest_f02_user"
        ):
            raise UserError(_("شما دسترسی ثبت رسید F02 را ندارید."))

    def _check_qc_user(self):
        if not self.env.user.has_group(
            "vagirest_production_record.group_vagirest_qc_manager"
        ):
            raise UserError(_("شما دسترسی تصمیم کنترل کیفیت را ندارید."))

    def _locations(self):
        Location = self.env["stock.location"].sudo()

        locations = {
            "input": Location.browse(40).exists(),
            "packaging": Location.browse(74).exists(),
            "raw": Location.browse(75).exists(),
            "rejected": Location.browse(77).exists(),
        }

        for key, location in locations.items():
            if not location:
                raise UserError(
                    _("مکان انبار لازم برای F02 یافت نشد: %s") % key
                )

        return locations

    def _validate_lines(self, require_qc=False):
        for record in self:
            if not record.line_ids:
                raise UserError(_("حداقل یک قلم باید وارد شود."))

            for line in record.line_ids:
                if line.quantity <= 0:
                    raise UserError(
                        _("مقدار همه اقلام باید بیشتر از صفر باشد.")
                    )

                classification = (
                    line.product_id.product_tmpl_id.vagirest_inventory_class
                )

                if classification not in (
                    "raw_material",
                    "packaging_material",
                ):
                    raise UserError(
                        _(
                            "محصول %s به عنوان مواد اولیه یا "
                            "مواد بسته‌بندی طبقه‌بندی نشده است."
                        )
                        % line.product_id.display_name
                    )

                if (
                    line.product_id.tracking != "none"
                    and not (line.lot_name or "").strip()
                ):
                    raise UserError(
                        _("برای محصول %s شماره لات/بچ الزامی است.")
                        % line.product_id.display_name
                    )

                if require_qc and line.inspection_result == "pending":
                    raise UserError(
                        _("نتیجه بازرسی همه اقلام باید مشخص شود.")
                    )

    def _get_or_create_internal_picking_type(
        self, name, source_location, destination_location
    ):
        company = source_location.company_id

        PickingType = self.env["stock.picking.type"].sudo().with_company(company)

        picking_type = PickingType.search([
            ("company_id", "=", company.id),
            ("code", "=", "internal"),
            ("name", "=", name),
        ], limit=1)

        if not picking_type:
            warehouse = self.env["stock.warehouse"].sudo().search([
                ("company_id", "=", company.id),
            ], limit=1)

            vals = {
                "name": name,
                "code": "internal",
                "sequence_code": "F02",
                "company_id": company.id,
                "default_location_src_id": source_location.id,
                "default_location_dest_id": destination_location.id,
            }

            if warehouse:
                vals["warehouse_id"] = warehouse.id

            picking_type = PickingType.create(vals)

        return picking_type

    def _create_and_validate_picking(
        self,
        *,
        picking_type,
        source_location,
        destination_location,
        lines,
        origin,
        partner=False,
        line_qty_field="quantity",
    ):
        self.ensure_one()

        company = destination_location.company_id or source_location.company_id

        Picking = self.env["stock.picking"].sudo().with_company(company)
        Move = self.env["stock.move"].sudo().with_company(company)
        MoveLine = self.env["stock.move.line"].sudo().with_company(company)
        Lot = self.env["stock.lot"].sudo().with_company(company)

        picking = Picking.create({
            "picking_type_id": picking_type.id,
            "location_id": source_location.id,
            "location_dest_id": destination_location.id,
            "origin": origin,
            "partner_id": partner.id if partner else False,
            "company_id": company.id,
        })

        created = []

        for line in lines:
            qty = getattr(line, line_qty_field)

            move = Move.create({
                "name": line.product_id.display_name,
                "origin": origin,
                "product_id": line.product_id.id,
                "product_uom_qty": qty,
                "product_uom": line.uom_id.id,
                "location_id": source_location.id,
                "location_dest_id": destination_location.id,
                "picking_id": picking.id,
                "company_id": company.id,
            })

            created.append((move, line, qty))

        picking.action_confirm()

        for move, line, qty in created:
            lot = False

            if line.product_id.tracking != "none":
                lot = Lot.search([
                    ("name", "=", line.lot_name.strip()),
                    ("product_id", "=", line.product_id.id),
                    ("company_id", "in", [False, company.id]),
                ], limit=1)

                if not lot:
                    lot = Lot.create({
                        "name": line.lot_name.strip(),
                        "product_id": line.product_id.id,
                        "company_id": company.id,
                    })

                if not line.lot_id:
                    line.sudo().write({"lot_id": lot.id})

            MoveLine.create({
                "move_id": move.id,
                "picking_id": picking.id,
                "company_id": company.id,
                "product_id": line.product_id.id,
                "product_uom_id": line.uom_id.id,
                "quantity": qty,
                "picked": True,
                "lot_id": lot.id if lot else False,
                "location_id": source_location.id,
                "location_dest_id": destination_location.id,
            })

        result = picking.with_context(
            cancel_backorder=True
        ).button_validate()

        if picking.state != "done":
            if isinstance(result, dict):
                raise UserError(
                    _("تأیید انتقال انبار نیازمند Wizard غیرمنتظره بود.")
                )

            raise UserError(_("انتقال انبار نهایی نشد."))

        return picking

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
            domain.append(("lot_id", "=", lot.id))
        else:
            domain.append(("lot_id", "=", False))

        quants = self.env["stock.quant"].sudo().search(domain)

        return (
            sum(quants.mapped("quantity"))
            - sum(quants.mapped("reserved_quantity"))
        )

    def _reverse_done_picking(self, picking, label):
        self.ensure_one()

        if not picking:
            return False

        if picking.state != "done":
            raise UserError(
                _("%s در وضعیت Done نیست.") % label
            )

        move_lines = picking.move_line_ids.filtered(
            lambda ml: ml.quantity > 0
        )

        if not move_lines:
            raise UserError(
                _("%s هیچ حرکت واقعی برای Reverse ندارد.") % label
            )

        grouped = {}

        for ml in move_lines:
            key = (
                ml.product_id.id,
                ml.lot_id.id if ml.lot_id else False,
                ml.location_dest_id.id,
                ml.location_id.id,
                ml.product_uom_id.id,
            )

            grouped.setdefault(key, 0.0)
            grouped[key] += ml.quantity

        for (
            product_id,
            lot_id,
            source_id,
            destination_id,
            uom_id,
        ), qty in grouped.items():

            product = self.env["product.product"].sudo().browse(
                product_id
            )

            lot = (
                self.env["stock.lot"].sudo().browse(lot_id)
                if lot_id
                else False
            )

            source = self.env["stock.location"].sudo().browse(
                source_id
            )

            available = self._available_quantity(
                product,
                lot,
                source,
                picking.company_id,
            )

            if available < qty:
                raise UserError(
                    _(
                        "امکان Reverse %s وجود ندارد. "
                        "موجودی %s در %s کافی نیست. "
                        "موجودی قابل استفاده: %s | مقدار لازم: %s"
                    )
                    % (
                        label,
                        product.display_name,
                        source.display_name,
                        available,
                        qty,
                    )
                )

        picking_type = (
            picking.picking_type_id.return_picking_type_id
            or picking.picking_type_id
        )

        reverse = self.env["stock.picking"].sudo().with_company(
            picking.company_id
        ).create({
            "picking_type_id": picking_type.id,
            "location_id": picking.location_dest_id.id,
            "location_dest_id": picking.location_id.id,
            "origin": "REV/%s/%s" % (
                self.name,
                picking.name,
            ),
            "partner_id": picking.partner_id.id,
            "company_id": picking.company_id.id,
        })

        created_moves = []

        for (
            product_id,
            lot_id,
            source_id,
            destination_id,
            uom_id,
        ), qty in grouped.items():

            move = self.env["stock.move"].sudo().with_company(
                picking.company_id
            ).create({
                "name": "%s - Reverse" % label,
                "origin": reverse.origin,
                "product_id": product_id,
                "product_uom_qty": qty,
                "product_uom": uom_id,
                "location_id": source_id,
                "location_dest_id": destination_id,
                "picking_id": reverse.id,
                "company_id": picking.company_id.id,
            })

            created_moves.append(
                (
                    move,
                    product_id,
                    lot_id,
                    source_id,
                    destination_id,
                    uom_id,
                    qty,
                )
            )

        reverse.action_confirm()

        for (
            move,
            product_id,
            lot_id,
            source_id,
            destination_id,
            uom_id,
            qty,
        ) in created_moves:

            self.env["stock.move.line"].sudo().with_company(
                picking.company_id
            ).create({
                "move_id": move.id,
                "picking_id": reverse.id,
                "company_id": picking.company_id.id,
                "product_id": product_id,
                "product_uom_id": uom_id,
                "quantity": qty,
                "picked": True,
                "lot_id": lot_id or False,
                "location_id": source_id,
                "location_dest_id": destination_id,
            })

        result = reverse.with_context(
            cancel_backorder=True
        ).button_validate()

        if reverse.state != "done":
            if isinstance(result, dict):
                raise UserError(
                    _(
                        "Reverse %s نیازمند Wizard غیرمنتظره بود."
                    )
                    % label
                )

            raise UserError(
                _("Reverse %s نهایی نشد.") % label
            )

        return reverse

    def action_mark_received(self):
        self._check_f02_user()

        locations = self._locations()

        for record in self:
            if record.state != "draft":
                raise UserError(
                    _("فقط رکورد پیش‌نویس قابل ثبت دریافت است.")
                )

            if record.incoming_picking_id:
                raise UserError(
                    _("برای این F02 قبلاً رسید انبار ثبت شده است.")
                )

            record._validate_lines()

            if not record.delivery_datetime:
                record.delivery_datetime = fields.Datetime.now()

            incoming_type = self.env["stock.picking.type"].sudo().browse(11).exists()

            if not incoming_type:
                raise UserError(_("Picking Type رسید انبار یافت نشد."))

            vendor_location = record.supplier_id.property_stock_supplier

            if not vendor_location:
                raise UserError(
                    _("مکان تأمین‌کننده برای فروشنده تعیین نشده است.")
                )

            picking = record._create_and_validate_picking(
                picking_type=incoming_type,
                source_location=vendor_location,
                destination_location=locations["input"],
                lines=record.line_ids,
                origin=record.name,
                partner=record.supplier_id,
            )

            record.write({
                "incoming_picking_id": picking.id,
                "state": "received",
            })

            record.message_post(
                body=_(
                    "دریافت فیزیکی ثبت شد و کالاها به input-QC منتقل شدند. "
                    "Picking: %s"
                ) % picking.display_name
            )

        return True

    def action_finalize_qc(self):
        self._check_qc_user()
        locations = self._locations()

        for record in self:
            if record.state != "received":
                raise UserError(
                    _("فقط F02 در انتظار QC قابل تصمیم‌گیری است.")
                )

            record._validate_lines(require_qc=True)

            accepted_raw = record.line_ids.filtered(
                lambda l:
                    l.inspection_result == "accepted"
                    and l.product_id.product_tmpl_id.vagirest_inventory_class
                    == "raw_material"
            )

            accepted_packaging = record.line_ids.filtered(
                lambda l:
                    l.inspection_result == "accepted"
                    and l.product_id.product_tmpl_id.vagirest_inventory_class
                    == "packaging_material"
            )

            rejected = record.line_ids.filtered(
                lambda l: l.inspection_result == "rejected"
            )

            raw_picking = False
            packaging_picking = False
            rejected_picking = False

            if accepted_raw:
                picking_type = record._get_or_create_internal_picking_type(
                    "F02 QC Approved - Raw Materials",
                    locations["input"],
                    locations["raw"],
                )

                raw_picking = record._create_and_validate_picking(
                    picking_type=picking_type,
                    source_location=locations["input"],
                    destination_location=locations["raw"],
                    lines=accepted_raw,
                    origin=record.name,
                )

            if accepted_packaging:
                picking_type = record._get_or_create_internal_picking_type(
                    "F02 QC Approved - Packaging",
                    locations["input"],
                    locations["packaging"],
                )

                packaging_picking = record._create_and_validate_picking(
                    picking_type=picking_type,
                    source_location=locations["input"],
                    destination_location=locations["packaging"],
                    lines=accepted_packaging,
                    origin=record.name,
                )

            if rejected:
                picking_type = record._get_or_create_internal_picking_type(
                    "F02 QC Rejected",
                    locations["input"],
                    locations["rejected"],
                )

                rejected_picking = record._create_and_validate_picking(
                    picking_type=picking_type,
                    source_location=locations["input"],
                    destination_location=locations["rejected"],
                    lines=rejected,
                    origin=record.name,
                )

            accepted_count = len(accepted_raw) + len(accepted_packaging)
            rejected_count = len(rejected)

            if accepted_count and rejected_count:
                new_state = "mixed"
            elif accepted_count:
                new_state = "approved"
            else:
                new_state = "rejected"

            record.write({
                "qc_inspector_id": self.env.user.id,
                "qc_decision_date": fields.Datetime.now(),
                "raw_approved_picking_id": (
                    raw_picking.id if raw_picking else False
                ),
                "packaging_approved_picking_id": (
                    packaging_picking.id if packaging_picking else False
                ),
                "rejected_picking_id": (
                    rejected_picking.id if rejected_picking else False
                ),
                "state": new_state,
            })

            record.message_post(
                body=_(
                    "تصمیم QC ثبت شد. وضعیت نهایی F02: %s"
                ) % dict(record._fields["state"].selection).get(new_state)
            )

        return True

    def action_reset_to_draft(self):
        for record in self:
            if record.state != "received":
                raise UserError(
                    _(
                        "بعد از تصمیم QC امکان بازگشت مستقیم وجود ندارد. "
                        "اصلاح باید با Reverse کنترل‌شده انجام شود."
                    )
                )

            if record.incoming_picking_id:
                raise UserError(
                    _(
                        "این F02 اثر انباری دارد و نباید با تغییر ساده "
                        "به Draft برگردد."
                    )
                )

            record.write({"state": "draft"})

        return True

    def action_reopen_qc(self):
        self._check_qc_user()

        for record in self:
            if record.state not in (
                "approved",
                "rejected",
                "mixed",
            ):
                raise UserError(
                    _(
                        "فقط F02 دارای تصمیم نهایی QC "
                        "قابل بازگشایی است."
                    )
                )

            reason = (record.correction_reason or "").strip()

            if not reason:
                raise UserError(
                    _("ثبت علت اصلاح الزامی است.")
                )

            raw_rev = False
            packaging_rev = False
            rejected_rev = False

            if record.raw_approved_picking_id:
                raw_rev = record._reverse_done_picking(
                    record.raw_approved_picking_id,
                    "مواد اولیه تأییدشده",
                )

            if record.packaging_approved_picking_id:
                packaging_rev = record._reverse_done_picking(
                    record.packaging_approved_picking_id,
                    "مواد بسته‌بندی تأییدشده",
                )

            if record.rejected_picking_id:
                rejected_rev = record._reverse_done_picking(
                    record.rejected_picking_id,
                    "اقلام ردشده",
                )

            record.with_context(
                allow_f02_correction=True
            ).write({
                "state": "received",
                "qc_inspector_id": False,
                "qc_decision_date": False,

                "raw_approved_reversal_picking_id": (
                    raw_rev.id if raw_rev else False
                ),
                "packaging_approved_reversal_picking_id": (
                    packaging_rev.id if packaging_rev else False
                ),
                "rejected_reversal_picking_id": (
                    rejected_rev.id if rejected_rev else False
                ),

                "raw_approved_picking_id": False,
                "packaging_approved_picking_id": False,
                "rejected_picking_id": False,

                "last_corrected_by_id": self.env.user.id,
                "last_correction_date": fields.Datetime.now(),
                "last_correction_reason": reason,
                "correction_count": (
                    record.correction_count + 1
                ),
                "correction_reason": False,
            })

            record.message_post(
                body=_(
                    "تصمیم QC برای اصلاح بازگشایی شد. "
                    "علت: %s"
                )
                % reason
            )

        return True

    def action_reverse_receipt_to_draft(self):
        self._check_f02_user()

        for record in self:
            if record.state != "received":
                raise UserError(
                    _(
                        "فقط F02 در وضعیت دریافت‌شده "
                        "قابل بازگشت به Draft است."
                    )
                )

            reason = (record.correction_reason or "").strip()

            if not reason:
                raise UserError(
                    _("ثبت علت اصلاح الزامی است.")
                )

            if not record.incoming_picking_id:
                raise UserError(
                    _("Picking ورودی F02 یافت نشد.")
                )

            reverse = record._reverse_done_picking(
                record.incoming_picking_id,
                "رسید ورودی F02",
            )

            record.with_context(
                allow_f02_correction=True
            ).write({
                "state": "draft",
                "incoming_reversal_picking_id": reverse.id,
                "incoming_picking_id": False,

                "last_corrected_by_id": self.env.user.id,
                "last_correction_date": fields.Datetime.now(),
                "last_correction_reason": reason,
                "correction_count": (
                    record.correction_count + 1
                ),
                "correction_reason": False,
            })

            record.line_ids.sudo().write({
                "inspection_result": "pending",
            })

            record.message_post(
                body=_(
                    "رسید F02 با Reverse انبار به Draft برگشت. "
                    "علت: %s"
                )
                % reason
            )

        return True

    def unlink(self):
        for record in self:
            if record.state != "draft":
                raise UserError(
                    _("فقط F02 پیش‌نویس قابل حذف است.")
                )

            if record.incoming_picking_id:
                raise UserError(
                    _("F02 دارای اثر انباری قابل حذف نیست.")
                )

        return super().unlink()


class VagirestRawMaterialReceiptLine(models.Model):
    _name = "vagirest.raw.material.receipt.line"
    _description = "VAGIREST Raw Material Receipt F02 Line"
    _order = "id"

    receipt_id = fields.Many2one(
        "vagirest.raw.material.receipt",
        string="رسید",
        required=True,
        ondelete="cascade",
    )

    product_id = fields.Many2one(
        "product.product",
        string="شرح مواد / کالا",
        required=True,
        domain=[
            ("type", "=", "product"),
            ("active", "=", True),
        ],
    )

    product_code = fields.Char(
        string="کد مواد / کالا",
        related="product_id.default_code",
        readonly=True,
        store=True,
    )

    inventory_class = fields.Selection(
        related="product_id.product_tmpl_id.vagirest_inventory_class",
        string="نوع قلم",
        readonly=True,
        store=True,
    )

    quantity = fields.Float(
        string="تعداد / مقدار",
        required=True,
        default=1.0,
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="واحد",
        related="product_id.uom_id",
        readonly=True,
        store=True,
    )

    lot_name = fields.Char(
        string="شماره لات / بچ تأمین‌کننده",
    )

    lot_id = fields.Many2one(
        "stock.lot",
        string="لات Odoo",
        readonly=True,
        copy=False,
    )

    inspection_result = fields.Selection(
        [
            ("pending", "در انتظار"),
            ("accepted", "قبول"),
            ("rejected", "رد"),
        ],
        string="نتیجه بازرسی",
        default="pending",
        required=True,
    )

    note = fields.Char(
        string="توضیحات",
    )

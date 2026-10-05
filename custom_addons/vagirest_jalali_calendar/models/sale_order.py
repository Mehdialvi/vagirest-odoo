from datetime import datetime, time

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

from .jalali_utils import format_jalali_date, parse_jalali_date


class SaleOrder(models.Model):
    _inherit = "sale.order"

    date_order_jalali = fields.Char(
        string="تاریخ سفارش شمسی",
        compute="_compute_date_order_jalali",
        inverse="_inverse_date_order_jalali",
        store=True,
        index=True,
        readonly=False,
    )

    @api.depends("date_order")
    def _compute_date_order_jalali(self):
        for record in self:
            if not record.date_order:
                record.date_order_jalali = False
                continue

            local_datetime = fields.Datetime.context_timestamp(
                record.with_context(tz="Asia/Tehran"),
                record.date_order,
            )

            record.date_order_jalali = format_jalali_date(
                local_datetime.date()
            )

    def _inverse_date_order_jalali(self):
        if not self.env.user.has_group(
            "vagirest_jalali_calendar.group_sale_order_jalali_date_edit"
        ):
            raise AccessError(
                _("شما اجازه ویرایش تاریخ سفارش شمسی را ندارید.")
            )

        tehran = pytz.timezone("Asia/Tehran")

        for record in self:
            value = (record.date_order_jalali or "").strip()

            if not value:
                raise ValidationError(
                    _("تاریخ سفارش شمسی نمی‌تواند خالی باشد.")
                )

            try:
                gregorian_date = parse_jalali_date(value)
            except Exception as exc:
                raise ValidationError(
                    _(
                        "تاریخ شمسی معتبر نیست. "
                        "فرمت صحیح مانند 1405/06/07 است."
                    )
                ) from exc

            # Keep the previous order time; only replace the calendar date.
            if record.date_order:
                old_local = fields.Datetime.context_timestamp(
                    record.with_context(tz="Asia/Tehran"),
                    record.date_order,
                )
                local_time = old_local.time().replace(tzinfo=None)
            else:
                local_time = time(12, 0, 0)

            local_naive = datetime.combine(
                gregorian_date,
                local_time,
            )

            local_aware = tehran.localize(local_naive)

            utc_naive = (
                local_aware
                .astimezone(pytz.UTC)
                .replace(tzinfo=None)
            )

            record.date_order = fields.Datetime.to_string(
                utc_naive
            )

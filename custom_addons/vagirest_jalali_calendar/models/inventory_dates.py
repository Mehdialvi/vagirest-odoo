from odoo import api, fields, models

from .jalali_utils import format_jalali_datetime


def _format_for_user(record, value):
    if not value:
        return False

    return format_jalali_datetime(
        value,
        timezone_name=(
            record.env.user.tz
            or "Asia/Tehran"
        ),
    )


class StockPicking(models.Model):
    _inherit = "stock.picking"

    scheduled_date_jalali = fields.Char(
        string="تاریخ برنامه‌ریزی شمسی",
        compute="_compute_inventory_jalali_dates",
        readonly=True,
    )

    date_done_jalali = fields.Char(
        string="تاریخ انتقال شمسی",
        compute="_compute_inventory_jalali_dates",
        readonly=True,
    )

    @api.depends(
        "scheduled_date",
        "date_done",
    )
    @api.depends_context("tz")
    def _compute_inventory_jalali_dates(self):
        for record in self:
            record.scheduled_date_jalali = (
                _format_for_user(
                    record,
                    record.scheduled_date,
                )
            )

            record.date_done_jalali = (
                _format_for_user(
                    record,
                    record.date_done,
                )
            )


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    date_jalali = fields.Char(
        string="تاریخ جابه‌جایی شمسی",
        compute="_compute_move_line_jalali_dates",
        readonly=True,
    )

    expiration_date_jalali = fields.Char(
        string="تاریخ انقضا شمسی",
        compute="_compute_move_line_jalali_dates",
        readonly=True,
    )

    @api.depends(
        "date",
        "expiration_date",
    )
    @api.depends_context("tz")
    def _compute_move_line_jalali_dates(self):
        for record in self:
            record.date_jalali = (
                _format_for_user(
                    record,
                    record.date,
                )
            )

            record.expiration_date_jalali = (
                _format_for_user(
                    record,
                    record.expiration_date,
                )
            )


class StockLot(models.Model):
    _inherit = "stock.lot"

    create_date_jalali = fields.Char(
        string="تاریخ ایجاد شمسی",
        compute="_compute_lot_jalali_dates",
        readonly=True,
    )

    expiration_date_jalali = fields.Char(
        string="تاریخ انقضا شمسی",
        compute="_compute_lot_jalali_dates",
        readonly=True,
    )

    use_date_jalali = fields.Char(
        string="بهترین زمان مصرف شمسی",
        compute="_compute_lot_jalali_dates",
        readonly=True,
    )

    removal_date_jalali = fields.Char(
        string="تاریخ خروج شمسی",
        compute="_compute_lot_jalali_dates",
        readonly=True,
    )

    alert_date_jalali = fields.Char(
        string="تاریخ هشدار شمسی",
        compute="_compute_lot_jalali_dates",
        readonly=True,
    )

    @api.depends(
        "create_date",
        "expiration_date",
        "use_date",
        "removal_date",
        "alert_date",
    )
    @api.depends_context("tz")
    def _compute_lot_jalali_dates(self):
        for record in self:
            record.create_date_jalali = (
                _format_for_user(
                    record,
                    record.create_date,
                )
            )

            record.expiration_date_jalali = (
                _format_for_user(
                    record,
                    record.expiration_date,
                )
            )

            record.use_date_jalali = (
                _format_for_user(
                    record,
                    record.use_date,
                )
            )

            record.removal_date_jalali = (
                _format_for_user(
                    record,
                    record.removal_date,
                )
            )

            record.alert_date_jalali = (
                _format_for_user(
                    record,
                    record.alert_date,
                )
            )

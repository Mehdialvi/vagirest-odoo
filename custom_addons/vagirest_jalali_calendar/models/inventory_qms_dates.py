
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from .jalali_utils import (
    format_jalali_date,
    parse_jalali_date,
)


def _format_jalali_datetime(record, value):
    if not value:
        return False

    local_dt = fields.Datetime.context_timestamp(
        record.with_context(
            tz="Asia/Tehran"
        ),
        value,
    )

    date_part = format_jalali_date(
        local_dt.date()
    )

    return (
        f"{date_part} "
        f"{local_dt.strftime('%H:%M')}"
    )


def _parse_jalali_date_safe(value):
    value = (value or "").strip()

    if not value:
        raise ValidationError(
            _(
                "تاریخ شمسی نمی‌تواند خالی باشد."
            )
        )

    try:
        return parse_jalali_date(value)

    except Exception as exc:
        raise ValidationError(
            _(
                "تاریخ شمسی معتبر نیست. "
                "فرمت صحیح مانند "
                "1405/07/06 است."
            )
        ) from exc


class VagirestMaterialRequest(models.Model):
    _inherit = "vagirest.material.request"

    request_date_jalali = fields.Char(
        string="تاریخ درخواست شمسی",
        compute="_compute_request_date_jalali",
        inverse="_inverse_request_date_jalali",
        store=True,
        index=True,
        readonly=False,
    )

    warehouse_received_at_jalali = fields.Char(
        string="زمان دریافت در انبار شمسی",
        compute="_compute_warehouse_received_at_jalali",
    )

    @api.depends("request_date")
    def _compute_request_date_jalali(self):
        for record in self:
            record.request_date_jalali = (
                format_jalali_date(
                    record.request_date
                )
                if record.request_date
                else False
            )

    def _inverse_request_date_jalali(self):
        for record in self:
            record.request_date = (
                _parse_jalali_date_safe(
                    record.request_date_jalali
                )
            )

    @api.depends("warehouse_received_at")
    def _compute_warehouse_received_at_jalali(
        self
    ):
        for record in self:
            record.warehouse_received_at_jalali = (
                _format_jalali_datetime(
                    record,
                    record.warehouse_received_at,
                )
            )


class VagirestWarehouseDelivery(models.Model):
    _inherit = "vagirest.warehouse.delivery"

    delivery_date_jalali = fields.Char(
        string="تاریخ تحویل شمسی",
        compute="_compute_delivery_date_jalali",
        inverse="_inverse_delivery_date_jalali",
        store=True,
        index=True,
        readonly=False,
    )

    finalized_at_jalali = fields.Char(
        string="زمان نهایی‌سازی شمسی",
        compute="_compute_finalized_at_jalali",
    )

    reversed_at_jalali = fields.Char(
        string="زمان برگشت شمسی",
        compute="_compute_reversed_at_jalali",
    )

    @api.depends("delivery_date")
    def _compute_delivery_date_jalali(self):
        for record in self:
            record.delivery_date_jalali = (
                format_jalali_date(
                    record.delivery_date
                )
                if record.delivery_date
                else False
            )

    def _inverse_delivery_date_jalali(self):
        for record in self:
            record.delivery_date = (
                _parse_jalali_date_safe(
                    record.delivery_date_jalali
                )
            )

    @api.depends("finalized_at")
    def _compute_finalized_at_jalali(self):
        for record in self:
            record.finalized_at_jalali = (
                _format_jalali_datetime(
                    record,
                    record.finalized_at,
                )
            )

    @api.depends("reversed_at")
    def _compute_reversed_at_jalali(self):
        for record in self:
            record.reversed_at_jalali = (
                _format_jalali_datetime(
                    record,
                    record.reversed_at,
                )
            )


class VagirestRawMaterialReceipt(models.Model):
    _inherit = "vagirest.raw.material.receipt"

    receipt_date_jalali = fields.Char(
        string="تاریخ رسید شمسی",
        compute="_compute_receipt_date_jalali",
        inverse="_inverse_receipt_date_jalali",
        store=True,
        index=True,
        readonly=False,
    )

    delivery_datetime_jalali = fields.Char(
        string="زمان تحویل شمسی",
        compute="_compute_delivery_datetime_jalali",
    )

    qc_decision_date_jalali = fields.Char(
        string="زمان تصمیم QC شمسی",
        compute="_compute_qc_decision_date_jalali",
    )

    last_correction_date_jalali = fields.Char(
        string="زمان آخرین اصلاح شمسی",
        compute="_compute_last_correction_date_jalali",
    )

    @api.depends("receipt_date")
    def _compute_receipt_date_jalali(self):
        for record in self:
            record.receipt_date_jalali = (
                format_jalali_date(
                    record.receipt_date
                )
                if record.receipt_date
                else False
            )

    def _inverse_receipt_date_jalali(self):
        for record in self:
            record.receipt_date = (
                _parse_jalali_date_safe(
                    record.receipt_date_jalali
                )
            )

    @api.depends("delivery_datetime")
    def _compute_delivery_datetime_jalali(
        self
    ):
        for record in self:
            record.delivery_datetime_jalali = (
                _format_jalali_datetime(
                    record,
                    record.delivery_datetime,
                )
            )

    @api.depends("qc_decision_date")
    def _compute_qc_decision_date_jalali(
        self
    ):
        for record in self:
            record.qc_decision_date_jalali = (
                _format_jalali_datetime(
                    record,
                    record.qc_decision_date,
                )
            )

    @api.depends("last_correction_date")
    def _compute_last_correction_date_jalali(
        self
    ):
        for record in self:
            record.last_correction_date_jalali = (
                _format_jalali_datetime(
                    record,
                    record.last_correction_date,
                )
            )

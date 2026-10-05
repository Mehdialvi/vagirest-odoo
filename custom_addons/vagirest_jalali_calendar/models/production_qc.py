from odoo import api, fields, models

from .jalali_utils import (
    format_jalali_date,
    format_jalali_datetime,
)


class VagirestProductionRecord(models.Model):
    _inherit = "vagirest.production.record"

    production_date_jalali = fields.Char(
        string="تاریخ تولید شمسی",
        compute="_compute_production_date_jalali",
        store=True,
        readonly=True,
    )

    @api.depends("production_date")
    def _compute_production_date_jalali(self):
        for record in self:
            record.production_date_jalali = (
                format_jalali_date(
                    record.production_date
                )
            )


class VagirestQCRecord(models.Model):
    _inherit = "vagirest.qc.record"

    production_date_jalali = fields.Char(
        string="تاریخ تولید شمسی",
        compute="_compute_jalali_dates",
        store=True,
        readonly=True,
    )

    decision_date_jalali = fields.Char(
        string="تاریخ تصمیم شمسی",
        compute="_compute_jalali_dates",
        store=True,
        readonly=True,
    )

    @api.depends(
        "production_date",
        "decision_date",
    )
    def _compute_jalali_dates(self):
        for record in self:
            record.production_date_jalali = (
                format_jalali_date(
                    record.production_date
                )
            )

            record.decision_date_jalali = (
                format_jalali_datetime(
                    record.decision_date
                )
            )

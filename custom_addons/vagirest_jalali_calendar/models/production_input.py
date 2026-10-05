from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

from .jalali_utils import (
    gregorian_to_jalali,
    parse_jalali_date,
)


JALALI_MONTHS = [
    ("1", "فروردین"),
    ("2", "اردیبهشت"),
    ("3", "خرداد"),
    ("4", "تیر"),
    ("5", "مرداد"),
    ("6", "شهریور"),
    ("7", "مهر"),
    ("8", "آبان"),
    ("9", "آذر"),
    ("10", "دی"),
    ("11", "بهمن"),
    ("12", "اسفند"),
]

JALALI_DAYS = [
    (str(day), str(day))
    for day in range(1, 32)
]


class VagirestProductionRecord(models.Model):
    _inherit = "vagirest.production.record"

    production_jalali_year = fields.Selection(
        selection="_selection_jalali_years",
        string="سال",
        compute="_compute_production_jalali_parts",
        inverse="_inverse_production_jalali_parts",
        readonly=False,
    )

    production_jalali_month = fields.Selection(
        selection=JALALI_MONTHS,
        string="ماه",
        compute="_compute_production_jalali_parts",
        inverse="_inverse_production_jalali_parts",
        readonly=False,
    )

    production_jalali_day = fields.Selection(
        selection=JALALI_DAYS,
        string="روز",
        compute="_compute_production_jalali_parts",
        inverse="_inverse_production_jalali_parts",
        readonly=False,
    )

    @api.model
    def _selection_jalali_years(self):
        return [
            (str(year), str(year))
            for year in range(1390, 1421)
        ]

    @api.depends("production_date")
    def _compute_production_jalali_parts(self):
        for record in self:
            if not record.production_date:
                record.production_jalali_year = False
                record.production_jalali_month = False
                record.production_jalali_day = False
                continue

            year, month, day = gregorian_to_jalali(
                record.production_date.year,
                record.production_date.month,
                record.production_date.day,
            )

            record.production_jalali_year = str(year)
            record.production_jalali_month = str(month)
            record.production_jalali_day = str(day)

    def _get_jalali_date_from_parts(
        self,
        adjust_invalid_day=False,
    ):
        self.ensure_one()

        if not (
            self.production_jalali_year
            and self.production_jalali_month
            and self.production_jalali_day
        ):
            return False

        year = int(self.production_jalali_year)
        month = int(self.production_jalali_month)
        day = int(self.production_jalali_day)

        if adjust_invalid_day:
            if 7 <= month <= 11 and day > 30:
                day = 30
                self.production_jalali_day = "30"

            if month == 12 and day > 30:
                day = 30
                self.production_jalali_day = "30"

        value = "%04d/%02d/%02d" % (
            year,
            month,
            day,
        )

        try:
            return parse_jalali_date(value)
        except ValueError:
            if (
                adjust_invalid_day
                and month == 12
                and day == 30
            ):
                self.production_jalali_day = "29"

                return parse_jalali_date(
                    "%04d/12/29" % year
                )

            raise

    def _inverse_production_jalali_parts(self):
        for record in self:
            if record.state != "draft":
                continue

            try:
                converted_date = (
                    record._get_jalali_date_from_parts()
                )
            except ValueError as error:
                raise ValidationError(
                    _(
                        "The selected Jalali date is invalid."
                    )
                ) from error

            if converted_date:
                record.production_date = converted_date

    @api.onchange(
        "production_jalali_year",
        "production_jalali_month",
        "production_jalali_day",
    )
    def _onchange_production_jalali_parts(self):
        for record in self:
            if record.state != "draft":
                continue

            try:
                converted_date = (
                    record._get_jalali_date_from_parts(
                        adjust_invalid_day=True,
                    )
                )
            except ValueError:
                return {
                    "warning": {
                        "title": _("Invalid Jalali Date"),
                        "message": _(
                            "Please select a valid Jalali "
                            "year, month and day."
                        ),
                    },
                }

            if converted_date:
                record.production_date = converted_date

    def action_set_production_date_today(self):
        for record in self:
            if record.state != "draft":
                raise UserError(
                    _(
                        "Only draft production records "
                        "can have their date changed."
                    )
                )

            record.production_date = (
                fields.Date.context_today(record)
            )

        return False

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _vagirest_format_jalali(self, value):
        """Convert an Odoo date/datetime to YYYY/MM/DD Jalali format."""
        if not value:
            return "-"

        # sale.order.date_order is stored in UTC. Convert it to Tehran local
        # time before taking the calendar date, so imported historical dates
        # do not shift one day backward in the PDF.
        if isinstance(value, str):
            try:
                value = fields.Datetime.to_datetime(value)
            except Exception:
                value = fields.Date.to_date(value)

        if hasattr(value, "hour"):
            local_dt = fields.Datetime.context_timestamp(
                self.with_context(tz="Asia/Tehran"),
                value,
            )
            gdate = local_dt.date()
        else:
            gdate = fields.Date.to_date(value)

        jy, jm, jd = self._vagirest_gregorian_to_jalali(
            gdate.year,
            gdate.month,
            gdate.day,
        )

        return f"{jy:04d}/{jm:02d}/{jd:02d}"

    @staticmethod
    def _vagirest_gregorian_to_jalali(gy, gm, gd):
        g_day_no = (
            365 * (gy - 1600)
            + ((gy - 1600 + 3) // 4)
            - ((gy - 1600 + 99) // 100)
            + ((gy - 1600 + 399) // 400)
        )

        g_month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

        leap = (
            (gy % 4 == 0 and gy % 100 != 0)
            or (gy % 400 == 0)
        )

        for month in range(gm - 1):
            g_day_no += g_month_days[month]

        if gm > 2 and leap:
            g_day_no += 1

        g_day_no += gd - 1

        j_day_no = g_day_no - 79

        j_np = j_day_no // 12053
        j_day_no %= 12053

        jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
        j_day_no %= 1461

        if j_day_no >= 366:
            jy += (j_day_no - 1) // 365
            j_day_no = (j_day_no - 1) % 365

        if j_day_no < 186:
            jm = 1 + j_day_no // 31
            jd = 1 + j_day_no % 31
        else:
            jm = 7 + (j_day_no - 186) // 30
            jd = 1 + (j_day_no - 186) % 30

        return jy, jm, jd

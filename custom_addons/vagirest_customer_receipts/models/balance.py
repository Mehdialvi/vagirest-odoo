from datetime import datetime
import pytz
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.vagirest_jalali_calendar.models.jalali_utils import format_jalali_date, parse_jalali_date


def prepare_date(vals, jalali_field, date_field):
    if jalali_field in vals:
        try:
            day = parse_jalali_date(vals.pop(jalali_field))
        except (ValueError, TypeError) as exc:
            raise ValidationError('تاریخ شمسی معتبر وارد کنید.') from exc
        if vals.get(date_field) and fields.Date.to_date(vals[date_field]) != day:
            raise ValidationError('تاریخ شمسی و میلادی متفاوت‌اند.')
        vals[date_field] = day


class CustomerBalance(models.Model):
    _name = 'vagirest.customer.balance'
    _description = 'مانده بررسی‌شده مشتری برای پیگیری فروش'
    _rec_name = 'partner_id'
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company, index=True)
    partner_id = fields.Many2one('res.partner', required=True, string='مشتری اصلی', index=True)
    currency_id = fields.Many2one('res.currency', required=True, default=lambda s: s.env.company.currency_id, string='ارز')
    followup_user_id = fields.Many2one('res.users', string='مسئول پیگیری', required=True, index=True)
    verified = fields.Boolean(string='مانده اولیه و پوشش حساب بررسی شده', default=False)
    opening_date = fields.Date(required=True, string='حساب تا پایان این تاریخ بررسی شده', groups='sales_team.group_sale_manager')
    opening_date_jalali = fields.Char(compute='_compute_opening_jalali', inverse='_inverse_opening_jalali', store=True, string='تاریخ مبنای حساب شمسی', groups='sales_team.group_sale_manager')
    opening_amount = fields.Monetary(string='مانده تا پایان تاریخ مبنا؛ مثبت بدهکار، منفی بستانکار', groups='sales_team.group_sale_manager')
    evidence = fields.Text(string='مرجع بررسی مانده اولیه و پوشش دریافت‌های قبلی', groups='sales_team.group_sale_manager')
    line_ids = fields.One2many('vagirest.customer.balance.line', 'balance_id', string='فروش‌ها و اصلاحات پس از تاریخ مبنا', groups='sales_team.group_sale_manager')
    current_balance = fields.Monetary(compute='_compute_balance', compute_sudo=True, string='مانده فعلی برای پیگیری')
    sales_after_opening = fields.Monetary(compute='_compute_balance', compute_sudo=True, string='فروش‌ها و اصلاحات پس از مبنا')
    receipts_after_opening = fields.Monetary(compute='_compute_balance', compute_sudo=True, string='دریافت‌های تطبیق‌شده پس از مبنا')
    as_of_jalali = fields.Char(compute='_compute_balance', compute_sudo=True, string='گزارش تا تاریخ شمسی')
    status = fields.Selection([('unknown', 'در انتظار بررسی حساب'), ('debtor', 'بدهکار'), ('creditor', 'بستانکار'), ('settled', 'مانده صفر')], compute='_compute_balance', compute_sudo=True, search='_search_status', string='وضعیت حساب')
    _sql_constraints = [('balance_unique', 'unique(company_id,partner_id,currency_id)', 'پرونده مانده این مشتری و ارز در شرکت موجود است.')]

    @api.depends('opening_date')
    def _compute_opening_jalali(self):
        for r in self:
            r.opening_date_jalali = format_jalali_date(r.opening_date) if r.opening_date else False

    def _inverse_opening_jalali(self):
        for r in self:
            r.opening_date = parse_jalali_date(r.opening_date_jalali)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            prepare_date(vals, 'opening_date_jalali', 'opening_date')
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        prepare_date(vals, 'opening_date_jalali', 'opening_date')
        return super().write(vals)

    def _search_status(self, operator, value):
        if operator not in ('=', '!=', 'in', 'not in'):
            raise ValidationError('فیلتر وضعیت معتبر نیست.')
        values = value if operator in ('in', 'not in') else [value]
        records = self.search([])
        found = records.filtered(lambda r: (r.status in values) if operator in ('=', 'in') else (r.status not in values))
        return [('id', 'in', found.ids)]

    @api.constrains('company_id', 'partner_id', 'currency_id', 'followup_user_id', 'verified', 'opening_date', 'evidence')
    def _check_scope(self):
        today = datetime.now(pytz.timezone('Asia/Tehran')).date()
        for r in self:
            if r.partner_id != r.partner_id.commercial_partner_id:
                raise ValidationError('مشتری اصلی را انتخاب کنید.')
            if r.partner_id.company_id and r.partner_id.company_id != r.company_id:
                raise ValidationError('شرکت مشتری با پرونده مانده متفاوت است.')
            if r.company_id not in r.followup_user_id.company_ids:
                raise ValidationError('مسئول پیگیری به شرکت پرونده دسترسی ندارد.')
            if r.opening_date > today:
                raise ValidationError('تاریخ مبنای مانده نمی‌تواند در آینده باشد.')
            if r.verified and not (r.evidence or '').strip():
                raise ValidationError('پیش از تأیید، مرجع بررسی مانده اولیه و دریافت‌های قبلی را ثبت کنید.')
            if r.line_ids.filtered(lambda l: l.date <= r.opening_date):
                raise ValidationError('تاریخ مبنا با رویدادهای ثبت‌شده تداخل دارد؛ ابتدا رویدادها را بررسی کنید.')

    @api.depends('verified', 'opening_amount', 'opening_date', 'company_id', 'currency_id', 'partner_id', 'line_ids.amount', 'line_ids.date', 'line_ids.order_id.amount_total', 'line_ids.order_id.state', 'partner_id.vagirest_receipt_ids.amount', 'partner_id.vagirest_receipt_ids.eligible_for_collection', 'partner_id.vagirest_receipt_ids.bank_line_id.date')
    def _compute_balance(self):
        today = datetime.now(pytz.timezone('Asia/Tehran')).date()
        for r in self:
            r.as_of_jalali = format_jalali_date(today)
            r.current_balance = r.sales_after_opening = r.receipts_after_opening = 0
            r.status = 'unknown'
            if not r.verified:
                continue
            lines = r.line_ids.filtered(lambda l: r.opening_date < l.date <= today)
            lines._check_line()
            # A manager attests actual sale independently of sale.order.state.
            sales = sum(l.order_id.amount_total if l.kind == 'sale' and l.order_id.state != 'cancel' else l.amount if l.kind == 'adjustment' else 0 for l in lines)
            receipts = self.env['vagirest.customer.receipt'].sudo().search([
                ('company_id', '=', r.company_id.id), ('partner_id', '=', r.partner_id.id),
                ('currency_id', '=', r.currency_id.id), ('eligible_for_collection', '=', True),
                ('bank_line_id.date', '>', r.opening_date), ('bank_line_id.date', '<=', today),
            ])
            # Recheck source validity even when a source changed in the current transaction.
            collected = sum(x.amount for x in receipts if not x._matching_error())
            r.sales_after_opening, r.receipts_after_opening = sales, collected
            r.current_balance = r.opening_amount + sales - collected
            sign = r.currency_id.compare_amounts(r.current_balance, 0)
            r.status = 'debtor' if sign > 0 else 'creditor' if sign < 0 else 'settled'


class BalanceLine(models.Model):
    _name = 'vagirest.customer.balance.line'
    _description = 'فروش واقعی یا اصلاح مستند حساب مشتری'
    balance_id = fields.Many2one('vagirest.customer.balance', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='balance_id.company_id', store=True)
    currency_id = fields.Many2one(related='balance_id.currency_id')
    date = fields.Date(required=True, string='تاریخ رویداد')
    date_jalali = fields.Char(compute='_compute_jalali', inverse='_inverse_jalali', store=True, string='تاریخ شمسی')
    kind = fields.Selection([('sale', 'فروش واقعی بررسی‌شده'), ('adjustment', 'اصلاح یا برگشت مستند')], required=True, default='sale', string='نوع')
    order_id = fields.Many2one('sale.order', string='کوتیشن فروش واقعی', ondelete='restrict')
    amount = fields.Monetary(string='مبلغ اصلاح؛ مثبت بدهی، منفی کاهش بدهی')
    sale_amount = fields.Monetary(related='order_id.amount_total', string='مبلغ قابل پرداخت فروش')
    evidence = fields.Text(required=True, string='شاهد فروش یا مرجع اصلاح')
    _sql_constraints = [('sale_once', 'unique(order_id)', 'این فروش قبلاً در پرونده مانده وارد شده است.')]

    @api.depends('date')
    def _compute_jalali(self):
        for r in self:
            r.date_jalali = format_jalali_date(r.date) if r.date else False

    def _inverse_jalali(self):
        for r in self:
            r.date = parse_jalali_date(r.date_jalali)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            prepare_date(vals, 'date_jalali', 'date')
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        prepare_date(vals, 'date_jalali', 'date')
        return super().write(vals)

    @api.constrains('balance_id', 'date', 'kind', 'order_id', 'evidence')
    def _check_line(self):
        for r in self:
            if not (r.evidence or '').strip():
                raise ValidationError('مرجع رویداد را ثبت کنید.')
            if r.date <= r.balance_id.opening_date:
                raise ValidationError('رویداد باید پس از تاریخ مبنا باشد؛ دریافت‌ها و فروش‌های قبل از آن در مانده اولیه پوشش داده می‌شوند.')
            if r.kind == 'sale':
                o = r.order_id
                if not o or o.state == 'cancel' or o.company_id != r.balance_id.company_id or o.currency_id != r.balance_id.currency_id or o.partner_id.commercial_partner_id != r.balance_id.partner_id:
                    raise ValidationError('فروش باید متعلق به همین مشتری، شرکت و ارز و غیرلغوشده باشد.')
            elif r.order_id:
                raise ValidationError('برای اصلاح حساب، سفارش را خالی بگذارید تا فروش دوباره شمرده نشود.')


class PartnerBalance(models.Model):
    _inherit = 'res.partner'
    vagirest_balance_ids = fields.One2many('vagirest.customer.balance', 'partner_id', string='مانده برای پیگیری')

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.vagirest_jalali_calendar.models.jalali_utils import parse_jalali_date, format_jalali_date
from .checks import matching_error


class CustomerReceipt(models.Model):
    _name = 'vagirest.customer.receipt'
    _description = 'رسید ارسالی مشتری و تطبیق عملیاتی با بانک'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'reference'
    _order = 'payment_date desc, id desc'
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company, index=True)
    partner_id = fields.Many2one('res.partner', required=True, string='مشتری اصلی', tracking=True, index=True)
    payment_date = fields.Date(required=True, string='تاریخ پرداخت اعلام‌شده', tracking=True)
    payment_date_jalali = fields.Char(compute='_compute_jalali', inverse='_inverse_jalali', string='تاریخ پرداخت شمسی', store=True)
    currency_id = fields.Many2one('res.currency', required=True, default=lambda s: s.env.company.currency_id, string='واحد پول')
    amount = fields.Monetary(required=True, string='مبلغ رسید در واحد پول انتخابی', tracking=True)
    payment_method = fields.Selection([('transfer', 'واریز بانکی'), ('card', 'کارت / درگاه'), ('check', 'وصول چک اعلام‌شده'), ('cash', 'نقدی')], required=True, default='transfer', string='روش پرداخت')
    reference = fields.Char(required=True, string='شماره پیگیری یا عنوان رسید', tracking=True)
    order_id = fields.Many2one('sale.order', string='سفارش / کوتیشن مرتبط', ondelete='restrict', tracking=True)
    attachment_ids = fields.Many2many('ir.attachment', 'vagirest_customer_receipt_attachment_rel', 'receipt_id', 'attachment_id', string='تصویر / فایل رسید')
    note = fields.Text(string='توضیح مشتری یا مبنای شناسایی', tracking=True)
    review_note = fields.Text(string='یادداشت بررسی مدیر', groups='sales_team.group_sale_manager')
    state = fields.Selection([('pending', 'در انتظار تطبیق'), ('matched', 'تطبیق‌شده با گردش بانک'), ('rejected', 'رد شده')], required=True, default='pending', readonly=True, tracking=True, index=True)
    bank_line_id = fields.Many2one('account.bank.statement.line', string='گردش بانکی موجود', ondelete='restrict', groups='sales_team.group_sale_manager')
    bank_date = fields.Date(related='bank_line_id.date', groups='sales_team.group_sale_manager')
    bank_date_jalali = fields.Char(compute='_compute_bank_jalali', string='تاریخ بانک شمسی', groups='sales_team.group_sale_manager')
    bank_amount = fields.Monetary(related='bank_line_id.amount', string='مبلغ گردش بانک', groups='sales_team.group_sale_manager')
    bank_reference = fields.Char(related='bank_line_id.payment_ref', string='شرح گردش بانک', groups='sales_team.group_sale_manager')
    matched_by_id = fields.Many2one('res.users', readonly=True, string='بررسی‌کننده')
    matched_at = fields.Datetime(readonly=True, string='زمان تطبیق')
    eligible_for_collection = fields.Boolean(compute='_compute_collection_eligibility', compute_sudo=True, store=True, string='تطبیق فعلی معتبر برای گزارش وصول')
    _sql_constraints = [('unique_bank_line', 'unique(bank_line_id)', 'این گردش بانک به رسید دیگری متصل است؛ رسید تکراری ثبت نکنید.')]

    @api.depends('payment_date')
    def _compute_jalali(self):
        for r in self:
            r.payment_date_jalali = format_jalali_date(r.payment_date) if r.payment_date else False

    def _inverse_jalali(self):
        for r in self:
            try:
                r.payment_date = parse_jalali_date(r.payment_date_jalali)
            except (ValueError, TypeError) as exc:
                raise ValidationError('تاریخ شمسی را به شکل 1405/07/09 وارد کنید.') from exc

    @api.depends('bank_line_id.date')
    def _compute_bank_jalali(self):
        for r in self:
            r.bank_date_jalali = format_jalali_date(r.bank_date) if r.bank_date else False

    @api.constrains('attachment_ids')
    def _check_attachments(self):
        for r in self:
            r.attachment_ids.check_access_rights('read')
            r.attachment_ids.check_access_rule('read')

    @api.depends('state', 'amount', 'company_id', 'currency_id', 'partner_id',
                 'attachment_ids', 'note', 'bank_line_id.amount', 'bank_line_id.partner_id',
                 'bank_line_id.partner_id.commercial_partner_id', 'bank_line_id.move_id.state',
                 'bank_line_id.company_id', 'bank_line_id.company_id.currency_id',
                 'bank_line_id.journal_id.currency_id', 'bank_line_id.foreign_currency_id')
    def _compute_collection_eligibility(self):
        for r in self:
            r.eligible_for_collection = r.state == 'matched' and not r._matching_error()

    @api.constrains('amount', 'partner_id', 'company_id', 'order_id', 'currency_id')
    def _check_details(self):
        for r in self:
            if r.amount <= 0:
                raise ValidationError('مبلغ رسید باید مثبت باشد.')
            if r.partner_id != r.partner_id.commercial_partner_id:
                raise ValidationError('رسید را روی مشتری اصلی ثبت کنید، نه مخاطب زیرمجموعه.')
            if r.partner_id.company_id and r.partner_id.company_id != r.company_id:
                raise ValidationError('شرکت مشتری با شرکت رسید متفاوت است.')
            if r.order_id:
                o = r.order_id
                if o.company_id != r.company_id or o.currency_id != r.currency_id or o.partner_id.commercial_partner_id != r.partner_id:
                    raise ValidationError('مشتری، شرکت و ارز سفارش باید با رسید یکسان باشد.')
                if o.state == 'cancel':
                    raise ValidationError('رسید را به سفارش لغوشده متصل نکنید.')

    @api.model_create_multi
    def create(self, vals_list):
        protected = {'state', 'matched_by_id', 'matched_at', 'eligible_for_collection'}
        for vals in vals_list:
            if {'bank_line_id', 'review_note'} & vals.keys() and not self.env.user.has_group('sales_team.group_sale_manager'):
                raise AccessError('اتصال گردش بانک و یادداشت بررسی فقط توسط مدیر فروش انجام می‌شود.')
            self._prepare_dates(vals)
            if any(vals.get(k) for k in protected if k != 'state') or vals.get('state', 'pending') != 'pending':
                raise AccessError('رسید جدید باید ابتدا در انتظار تطبیق باشد.')
        return super().create(vals_list)

    def write(self, vals):
        if {'bank_line_id', 'review_note'} & vals.keys() and not self.env.user.has_group('sales_team.group_sale_manager'):
            raise AccessError('اتصال گردش بانک و یادداشت بررسی فقط توسط مدیر فروش انجام می‌شود.')
        vals = dict(vals)
        self._prepare_dates(vals)
        if {'state', 'matched_by_id', 'matched_at', 'eligible_for_collection'} & vals.keys():
            raise AccessError('وضعیت را با دکمه‌های بررسی رسید تغییر دهید.')
        if any(r.state != 'pending' for r in self) and set(vals) - {'message_follower_ids', 'activity_ids', 'message_main_attachment_id'}:
            raise ValidationError('برای اصلاح رسید بررسی‌شده، ابتدا مدیر آن را به انتظار تطبیق برگرداند.')
        return super().write(vals)

    @staticmethod
    def _prepare_dates(vals):
        if 'payment_date_jalali' in vals:
            try:
                date = parse_jalali_date(vals.pop('payment_date_jalali'))
            except (ValueError, TypeError) as exc:
                raise ValidationError('تاریخ شمسی معتبر وارد کنید.') from exc
            if vals.get('payment_date') and fields.Date.to_date(vals['payment_date']) != date:
                raise ValidationError('تاریخ شمسی و میلادی پرداخت متفاوت‌اند.')
            vals['payment_date'] = date

    def unlink(self):
        if any(r.state != 'pending' for r in self):
            raise ValidationError('رسید بررسی‌شده حذف نمی‌شود؛ ابتدا به انتظار تطبیق برگردانید.')
        return super().unlink()

    def _require_manager(self):
        self.check_access_rights('write')
        self.check_access_rule('write')
        if not self.env.user.has_group('sales_team.group_sale_manager'):
            raise AccessError('تطبیق و رد رسید فقط توسط مدیر فروش انجام می‌شود.')

    def _matching_error(self):
        self.ensure_one()
        bank = self.bank_line_id
        if not bank:
            return 'گردش بانکی موجود را انتخاب کنید.'
        bank_currency = bank.journal_id.currency_id or bank.company_id.currency_id
        return matching_error(amount=self.amount, bank_amount=bank.amount,
            rounding=self.currency_id.rounding, company_id=self.company_id.id,
            bank_company_id=bank.company_id.id, currency_id=self.currency_id.id,
            bank_currency_id=bank_currency.id, partner_id=self.partner_id.id,
            bank_partner_id=bank.partner_id.commercial_partner_id.id if bank.partner_id else False,
            posted=bank.move_id.state == 'posted',
            foreign_currency=bool(bank.foreign_currency_id and bank.foreign_currency_id != bank_currency),
            evidence=bool(self.attachment_ids or (self.note or '').strip()))

    def action_match(self):
        self._require_manager()
        for r in self:
            if r.state != 'pending':
                raise ValidationError('رسید باید در انتظار تطبیق باشد.')
            r._check_details()
            error = r._matching_error()
            if error:
                raise ValidationError(error)
        # No account.move/payment/statement/order/stock writes occur here.
        return super(CustomerReceipt, self).write({'state': 'matched', 'matched_by_id': self.env.uid, 'matched_at': fields.Datetime.now()})

    def action_reject(self):
        self._require_manager()
        if any(r.state != 'pending' or not (r.review_note or '').strip() for r in self):
            raise ValidationError('فقط رسید در انتظار تطبیق با یادداشت دلیل رد قابل رد است.')
        return super(CustomerReceipt, self).write({'state': 'rejected'})

    def action_reset(self):
        self._require_manager()
        return super(CustomerReceipt, self).write({'state': 'pending', 'bank_line_id': False, 'matched_by_id': False, 'matched_at': False})


class Partner(models.Model):
    _inherit = 'res.partner'
    vagirest_receipt_ids = fields.One2many('vagirest.customer.receipt', 'partner_id', string='واریزی‌ها و رسیدها')

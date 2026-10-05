from odoo import fields, models


class SaleReport(models.Model):
    _inherit = 'sale.report'

    vagirest_city = fields.Char(string='شهر مشتری', readonly=True)
    vagirest_jalali_month = fields.Char(string='ماه شمسی سفارش', readonly=True)
    vagirest_creator_id = fields.Many2one('res.users', string='ایجادکننده سفارش', readonly=True)
    vagirest_order_currency_id = fields.Many2one('res.currency', string='ارز اصلی سفارش', readonly=True)
    vagirest_amount_untaxed = fields.Monetary(
        string='مبلغ بدون مالیات در ارز اصلی', readonly=True,
        currency_field='vagirest_order_currency_id', group_operator='sum')
    vagirest_customer_id = fields.Many2one(
        'res.partner', string='مشتری یکتا', readonly=True,
        group_operator='count_distinct')

    def _select_additional_fields(self):
        values = super()._select_additional_fields()
        values.update({
            'vagirest_jalali_month': "LEFT(s.date_order_jalali, 7)",
            'vagirest_city': "COALESCE(NULLIF(BTRIM(partner.city), ''), 'نامشخص')",
            'vagirest_creator_id': 's.create_uid',
            'vagirest_order_currency_id': 's.currency_id',
            'vagirest_amount_untaxed': 'SUM(l.price_subtotal)',
            'vagirest_customer_id': 'partner.commercial_partner_id',
        })
        return values

    def _group_by_sale(self):
        return super()._group_by_sale() + ', partner.city, s.create_uid, s.currency_id, partner.commercial_partner_id, s.date_order_jalali'

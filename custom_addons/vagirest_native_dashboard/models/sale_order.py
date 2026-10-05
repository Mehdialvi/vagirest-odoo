from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    vagirest_commercial_customer_id = fields.Many2one(
        related='partner_id.commercial_partner_id', store=True, readonly=True,
        string='مشتری دارای کوتیشن', group_operator='count_distinct')

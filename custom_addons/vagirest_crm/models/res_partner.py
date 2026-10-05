from odoo import fields, models

from .commercial_constants import (
    COMMERCIAL_POTENTIAL_SELECTION,
    CUSTOMER_TYPE_SELECTION,
    PREFERRED_CONTACT_SELECTION,
    SALES_CHANNEL_SELECTION,
)


class ResPartner(models.Model):
    _inherit = "res.partner"

    vagirest_customer_type = fields.Selection(
        selection=CUSTOMER_TYPE_SELECTION,
        string="نوع مشتری واژیرست",
        tracking=True,
    )

    vagirest_product_interest_ids = fields.Many2many(
        comodel_name="vagirest.product.interest",
        relation="vagirest_partner_product_interest_rel",
        column1="partner_id",
        column2="interest_id",
        string="محصولات موردعلاقه",
    )

    vagirest_sales_channel = fields.Selection(
        selection=SALES_CHANNEL_SELECTION,
        string="کانال اصلی فروش",
        tracking=True,
    )

    vagirest_commercial_potential = fields.Selection(
        selection=COMMERCIAL_POTENTIAL_SELECTION,
        string="پتانسیل تجاری",
        tracking=True,
    )

    vagirest_preferred_contact = fields.Selection(
        selection=PREFERRED_CONTACT_SELECTION,
        string="روش ارتباط ترجیحی",
    )

    vagirest_referrer_id = fields.Many2one(
        comodel_name="res.partner",
        string="معرف",
        domain="[('id', '!=', id)]",
        ondelete="set null",
        tracking=True,
    )

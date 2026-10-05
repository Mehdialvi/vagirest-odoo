from odoo import api, fields, models

from .commercial_constants import (
    COMMERCIAL_POTENTIAL_SELECTION,
    CUSTOMER_TYPE_SELECTION,
    PREFERRED_CONTACT_SELECTION,
    SALES_CHANNEL_SELECTION,
)


class CrmLead(models.Model):
    _inherit = "crm.lead"

    vagirest_customer_type = fields.Selection(
        selection=CUSTOMER_TYPE_SELECTION,
        string="نوع مشتری",
        tracking=True,
    )

    vagirest_product_interest_ids = fields.Many2many(
        comodel_name="vagirest.product.interest",
        relation="vagirest_lead_product_interest_rel",
        column1="lead_id",
        column2="interest_id",
        string="محصولات موردعلاقه",
    )

    vagirest_sales_channel = fields.Selection(
        selection=SALES_CHANNEL_SELECTION,
        string="کانال فروش",
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
        ondelete="set null",
        tracking=True,
    )

    @api.onchange("partner_id")
    def _onchange_vagirest_partner_commercial_data(self):
        for record in self:
            partner = record.partner_id

            if not partner:
                continue

            if not record.vagirest_customer_type:
                record.vagirest_customer_type = (
                    partner.vagirest_customer_type
                )

            if not record.vagirest_product_interest_ids:
                record.vagirest_product_interest_ids = (
                    partner.vagirest_product_interest_ids
                )

            if not record.vagirest_sales_channel:
                record.vagirest_sales_channel = (
                    partner.vagirest_sales_channel
                )

            if not record.vagirest_commercial_potential:
                record.vagirest_commercial_potential = (
                    partner.vagirest_commercial_potential
                )

            if not record.vagirest_preferred_contact:
                record.vagirest_preferred_contact = (
                    partner.vagirest_preferred_contact
                )

            if not record.vagirest_referrer_id:
                record.vagirest_referrer_id = (
                    partner.vagirest_referrer_id
                )

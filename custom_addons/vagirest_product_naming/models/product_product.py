from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    vagirest_standard_name = fields.Char(
        string="VAGIREST Standard Name",
        copy=False,
        index=True,
        help="Controlled product name. Does not replace Internal Reference or product identity.",
    )

    @api.depends(
        "product_tmpl_id.name",
        "product_template_attribute_value_ids",
        "default_code",
        "vagirest_standard_name",
    )
    def _compute_display_name(self):
        super()._compute_display_name()
        for product in self:
            if product.vagirest_standard_name:
                if product.default_code:
                    product.display_name = "[%s] %s" % (
                        product.default_code,
                        product.vagirest_standard_name,
                    )
                else:
                    product.display_name = product.vagirest_standard_name

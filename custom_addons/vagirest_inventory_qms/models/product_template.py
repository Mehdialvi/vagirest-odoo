from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    vagirest_inventory_class = fields.Selection(
        selection=[
            ("raw_material", "مواد اولیه"),
            ("packaging_material", "مواد بسته‌بندی"),
            ("finished_product", "محصول نهایی"),
            ("other", "سایر"),
        ],
        string="طبقه‌بندی انبار واژیرست",
        help=(
            "طبقه‌بندی اختصاصی انبار/QMS واژیرست. "
            "این فیلد مستقل از Product Category استاندارد Odoo است."
        ),
    )

from odoo import fields, models


class VagirestProductInterest(models.Model):
    _name = "vagirest.product.interest"
    _description = "VAGIREST Product Interest"
    _order = "sequence, id"

    name = fields.Char(
        string="نام",
        required=True,
        translate=True,
    )

    code = fields.Char(
        string="کد",
        required=True,
        index=True,
    )

    sequence = fields.Integer(
        string="ترتیب",
        default=10,
    )

    active = fields.Boolean(
        string="فعال",
        default=True,
    )

    _sql_constraints = [
        (
            "vagirest_product_interest_code_unique",
            "unique(code)",
            "کد گروه محصول باید یکتا باشد.",
        ),
    ]

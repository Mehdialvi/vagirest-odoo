from odoo import api, models, _
from odoo.exceptions import AccessError


INVENTORY_VIEWER_GROUP = (
    "vagirest_production_record."
    "group_vagirest_inventory_viewer"
)

ERP_MANAGER_GROUP = (
    "vagirest_production_record."
    "group_vagirest_erp_manager"
)


def _check_vagirest_direct_stock_write(env):
    """Block direct inventory changes by operational users.

    Controlled Production and QC stock operations use sudo and therefore
    bypass this restriction. ERP managers remain unrestricted.
    """

    if env.su:
        return

    user = env.user

    if (
        user.has_group(INVENTORY_VIEWER_GROUP)
        and not user.has_group(ERP_MANAGER_GROUP)
    ):
        raise AccessError(
            _(
                "Direct inventory changes are not permitted for "
                "your VAGIREST role. Use the controlled Production "
                "or QC forms."
            )
        )


class StockPicking(models.Model):
    _inherit = "stock.picking"

    @api.model_create_multi
    def create(self, vals_list):
        _check_vagirest_direct_stock_write(self.env)
        return super().create(vals_list)

    def write(self, vals):
        _check_vagirest_direct_stock_write(self.env)
        return super().write(vals)

    def unlink(self):
        _check_vagirest_direct_stock_write(self.env)
        return super().unlink()


class StockMove(models.Model):
    _inherit = "stock.move"

    @api.model_create_multi
    def create(self, vals_list):
        _check_vagirest_direct_stock_write(self.env)
        return super().create(vals_list)

    def write(self, vals):
        _check_vagirest_direct_stock_write(self.env)
        return super().write(vals)

    def unlink(self):
        _check_vagirest_direct_stock_write(self.env)
        return super().unlink()


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.model_create_multi
    def create(self, vals_list):
        _check_vagirest_direct_stock_write(self.env)
        return super().create(vals_list)

    def write(self, vals):
        _check_vagirest_direct_stock_write(self.env)
        return super().write(vals)

    def unlink(self):
        _check_vagirest_direct_stock_write(self.env)
        return super().unlink()

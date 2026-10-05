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


def _check_vagirest_expense_write(env):
    """Block expense changes for VAGIREST operational users."""

    if env.su:
        return

    user = env.user

    if (
        user.has_group(INVENTORY_VIEWER_GROUP)
        and not user.has_group(ERP_MANAGER_GROUP)
    ):
        raise AccessError(
            _(
                "Expense creation and modification are not "
                "permitted for your VAGIREST role."
            )
        )


class HrExpense(models.Model):
    _inherit = "hr.expense"

    @api.model_create_multi
    def create(self, vals_list):
        _check_vagirest_expense_write(self.env)
        return super().create(vals_list)

    def write(self, vals):
        _check_vagirest_expense_write(self.env)
        return super().write(vals)

    def unlink(self):
        _check_vagirest_expense_write(self.env)
        return super().unlink()

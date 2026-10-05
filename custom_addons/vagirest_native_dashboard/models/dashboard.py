from odoo import fields, models


class SpreadsheetDashboard(models.Model):
    _inherit = 'spreadsheet.dashboard'

    vagirest_dashboard_owner_id = fields.Many2one('res.users', readonly=True, copy=False)
    vagirest_dashboard_company_id = fields.Many2one('res.company', readonly=True, copy=False)

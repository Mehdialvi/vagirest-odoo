{
    'name': 'VAGIREST Customer Receipts',
    'version': '17.0.1.1.0',
    'summary': 'Customer payment evidence and operational bank matching',
    'author': 'VAGIREST', 'license': 'LGPL-3',
    'depends': ['sale', 'account', 'mail', 'vagirest_jalali_calendar', 'vagirest_native_dashboard'],
    'data': ['security/ir.model.access.csv', 'security/rules.xml', 'security/finance_privacy.xml', 'views/receipts.xml', 'views/customer_balance.xml'],
    'installable': True, 'application': False,
}

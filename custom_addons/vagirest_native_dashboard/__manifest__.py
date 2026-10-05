{
    'name': 'VAGIREST Native Spreadsheet Dashboards',
    'version': '17.0.1.0.2',
    'license': 'LGPL-3',
    'author': 'VAGIREST',
    'depends': ['spreadsheet_dashboard_sale', 'vagirest_jalali_calendar'],
    'assets': {'web.assets_backend': [
        'vagirest_native_dashboard/static/src/jalali_calendar.js',
        'vagirest_native_dashboard/static/src/jalali_date_input.js',
        'vagirest_native_dashboard/static/src/jalali_date_input.xml',
    ]},
    'data': ['security/security.xml'],
    'post_init_hook': 'post_init_hook',
    'installable': True,
}

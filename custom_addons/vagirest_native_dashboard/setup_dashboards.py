import base64
from copy import deepcopy
import json
import re
from uuid import uuid4

from odoo.exceptions import UserError


def build_snapshot(snapshot, company_id, currency_id, creator_id=None, product=False):
    """Copy the installed native template; change sources, not sale documents."""
    data = deepcopy(snapshot)
    def transform(value):
        if isinstance(value, dict):
            return {k: transform(v) for k, v in value.items()}
        if isinstance(value, list):
            return [transform(v) for v in value]
        if isinstance(value, str):
            return (value.replace('price_subtotal', 'vagirest_amount_untaxed')
                    .replace('__count', 'order_reference')
                    .replace('Monthly Sales', 'روند ماهانه کوتیشن‌ها (شمسی)')
                    .replace('date:month', 'vagirest_jalali_month')
                    .replace('Top Sales Orders', 'آخرین کوتیشن‌ها')
                    .replace('Top Quotations', 'کوتیشن‌های بزرگ‌تر')
                    .replace('Best Sellers by Revenue', 'محصولات به ترتیب مبلغ کوتیشن'))
        return value
    data = transform(data)

    def domain(model):
        result = [('company_id', '=', company_id), ('state', 'in', ['draft', 'sent'])]
        result.append(('vagirest_order_currency_id' if model == 'sale.report' else 'currency_id', '=', currency_id))
        if creator_id:
            result.append(('vagirest_creator_id' if model == 'sale.report' else 'create_uid', '=', creator_id))
        return result

    for kind in ('pivots', 'lists'):
        for source in data.get(kind, {}).values():
            if source.get('model') not in ('sale.report', 'sale.order'):
                raise UserError('Unexpected native dashboard source model.')
            source['domain'] = domain(source['model'])
            source.setdefault('context', {}).pop('params', None)
            source['context']['allowed_company_ids'] = [company_id]
    if not product and '2' in data.get('lists', {}):
        data['lists']['2']['orderBy'] = [{'name': 'date_order', 'asc': False}, {'name': 'id', 'asc': False}]
        data['lists']['2']['name'] = 'آخرین کوتیشن‌ها'
    if not product:
        if '13' in data['pivots'] or '14' in data['pivots']:
            raise UserError('Native pivot IDs 13/14 are already used; template needs review.')
        for ident in ('11', '12'):
            source = data['pivots'].get(ident)
            if not source:
                raise UserError('Native statistics pivots 11/12 are missing.')
            source['measures'].append({'field': 'vagirest_customer_id'})
        for ident, source_id in [('13', '11'), ('14', '12')]:
            data['pivots'][ident] = {
                'id': ident, 'model': 'sale.order', 'domain': domain('sale.order'),
                'context': {'allowed_company_ids': [company_id]},
                'rowGroupBys': ['state'], 'colGroupBys': [],
                'measures': [{'field': '__count'}, {'field': 'vagirest_commercial_customer_id'}],
                'name': 'تعداد اسناد — ' + ('دوره جاری' if ident == '13' else 'دوره قبل'),
                'sortedColumn': None,
            }
        data['pivotNextId'] = max(int(data.get('pivotNextId', 0)), 15)
        field_map = {'date': 'date_order', 'product_id': 'order_line.product_id',
                     'categ_id': 'order_line.product_id.categ_id',
                     'product_tmpl_id': 'order_line.product_id.product_tmpl_id',
                     'state_id': 'partner_id.state_id', 'country_id': 'partner_id.country_id',
                     'vagirest_city': 'partner_id.city'}
        for definition in data.get('globalFilters', []):
            mapping = definition.setdefault('pivotFields', {})
            for ident, source_id in [('13', '11'), ('14', '12')]:
                if source_id in mapping:
                    match = deepcopy(mapping[source_id])
                    match['field'] = field_map.get(match['field'], match['field'])
                    mapping[ident] = match
        sheet = next((s for s in data['sheets'] if s.get('name') == 'Data'), None)
        if not sheet:
            raise UserError('Native Data sheet is missing.')
        cells = sheet['cells']
        for column, pivot, order_pivot in [('B', 11, 13), ('C', 12, 14)]:
            formulas = {
                '2': '=IFERROR(ODOO.PIVOT(%s,"__count","state","draft"),0)' % order_pivot,
                '3': '=IFERROR(ODOO.PIVOT(%s,"__count","state","sent"),0)' % order_pivot,
                '4': '=%s2+%s3' % (column, column),
                '5': '=IFERROR(ODOO.PIVOT(%s,"vagirest_commercial_customer_id"),0)' % order_pivot,
                '6': '=%s4' % column,
                '7': '=IFERROR(ODOO.PIVOT(%s,"vagirest_amount_untaxed"),0)' % pivot,
                '8': '=IFERROR(%s7/%s4,0)' % (column, column),
            }
            for row, formula in formulas.items():
                cells.setdefault(column + row, {})['content'] = formula
        for address, label in [('A5', 'مشتری دارای کوتیشن'), ('A6', 'تعداد کوتیشن'),
                               ('A7', 'مبلغ کوتیشن بدون مالیات'), ('A8', 'میانگین مبلغ کوتیشن')]:
            cells.setdefault(address, {})['content'] = label

    for sheet in data['sheets']:
        for figure in sheet.get('figures', []):
            chart = figure.get('data', {})
            model = chart.get('metaData', {}).get('resModel')
            if model:
                chart.setdefault('searchParams', {})['domain'] = domain(model)
                chart['searchParams'].setdefault('context', {})['allowed_company_ids'] = [company_id]
            if chart.get('type') == 'scorecard' and not product:
                config = {
                    'Quotations': ('تعداد کوتیشن', '4'),
                    'Orders': ('مشتری دارای کوتیشن', '5'),
                    'Revenue': ('مبلغ کوتیشن بدون مالیات', '7'),
                    'Average Order': ('میانگین مبلغ کوتیشن', '8'),
                }.get(chart.get('title'))
                if config:
                    title, row = config
                    chart.update(title=title, keyValue='Data!B' + row, baseline='Data!C' + row,
                                 baselineDescr='نسبت به دوره قبل')
            elif chart.get('type') == 'scorecard' and product:
                chart['title'] = {'Best Seller': 'محصول با بیشترین مبلغ کوتیشن',
                                  'Best Category': 'دسته با بیشترین مبلغ کوتیشن'}.get(chart.get('title'), chart.get('title', ''))
                chart['baselineDescr'] = 'تعداد در کوتیشن‌ها'
        # Native headings contain drill-through action URLs. Keep them scoped.
        for cell in sheet.get('cells', {}).values():
            content = cell.get('content', '')
            match = re.search(r'odoo://view/(\{.*\})', content)
            if match:
                payload = json.loads(match.group(1))
                action = payload.get('action', {})
                model = action.get('modelName')
                if model in ('sale.report', 'sale.order'):
                    action['domain'] = domain(model)
                    action.setdefault('context', {})['allowed_company_ids'] = [company_id]
                    cell['content'] = content[:match.start(1)] + json.dumps(payload, ensure_ascii=False) + content[match.end(1):]

    # Filters map across all native sources. Province is already in sale.report;
    # city is the only new geographic grouping field.
    def add_filter(label, kind, model_name, field_report, field_order, field_type):
        if any(f.get('label') == label for f in data.get('globalFilters', [])):
            return
        definition = {
            'id': str(uuid4()), 'type': kind, 'label': label,
            'defaultValue': [] if kind == 'relation' else '',
            'pivotFields': {}, 'listFields': {}, 'graphFields': {},
        }
        if kind == 'relation':
            definition.update(modelName=model_name, defaultValueDisplayNames=[])
        for key, target in [('pivots', 'pivotFields'), ('lists', 'listFields')]:
            for ident, source in data.get(key, {}).items():
                definition[target][ident] = {
                    'field': field_report if source['model'] == 'sale.report' else field_order,
                    'type': field_type,
                }
        data.setdefault('globalFilters', []).append(definition)
    add_filter('استان', 'relation', 'res.country.state', 'state_id', 'partner_id.state_id', 'many2one')
    add_filter('شهر', 'text', None, 'vagirest_city', 'partner_id.city', 'char')
    if product:
        add_filter('مشتری', 'relation', 'res.partner', 'partner_id', 'partner_id', 'many2one')
        add_filter('مسئول فروش', 'relation', 'res.users', 'user_id', 'user_id', 'many2one')

    geography = deepcopy(data['sheets'][0])
    geography.update(id=str(uuid4()), name='استان و شهر', cells={}, figures=[], merges=[])
    geography['figures'] = []
    for index, (field, label) in enumerate([('state_id', 'مبلغ کوتیشن به تفکیک استان'),
                                            ('vagirest_city', 'مبلغ کوتیشن به تفکیک شهر')]):
        ident = str(uuid4())
        geography['figures'].append({
            'id': ident, 'x': 0, 'y': index * 370, 'width': 1000, 'height': 330, 'tag': 'chart',
            'data': {'title': label, 'background': '#FFFFFF', 'legendPosition': 'none',
                     'type': 'odoo_bar', 'verticalAxisPosition': 'left', 'stacked': False,
                     'metaData': {'groupBy': [field], 'measure': 'vagirest_amount_untaxed',
                                  'order': 'DESC', 'resModel': 'sale.report'},
                     'searchParams': {'comparison': None, 'context': {'allowed_company_ids': [company_id]},
                                      'domain': domain('sale.report'), 'groupBy': [field], 'orderBy': []}},
        })
        for definition in data['globalFilters']:
            exemplar = next(iter(definition.get('pivotFields', {}).values()), None)
            if exemplar:
                definition.setdefault('graphFields', {})[ident] = deepcopy(exemplar)
    # Add the new province/city/customer filters to existing native graphs too.
    for sheet in data['sheets']:
        for figure in sheet.get('figures', []):
            if figure.get('data', {}).get('metaData', {}).get('resModel') == 'sale.report':
                for definition in data['globalFilters']:
                    if definition['label'] in ('استان', 'شهر', 'مشتری', 'مسئول فروش'):
                        exemplar = next(iter(definition.get('pivotFields', {}).values()), None)
                        if exemplar:
                            definition.setdefault('graphFields', {})[figure['id']] = deepcopy(exemplar)
    data['sheets'].append(geography)
    apply_display_settings(data, currency_id)
    return data


def apply_display_settings(data, currency_id):
    # Numeric values remain numeric, including the previous-period baseline.
    formats = data.setdefault('formats', {})
    for key, value in list(formats.items()):
        if '$' in value:
            formats[key] = '#,##0'
    number_id = max([int(k) for k in formats] + [0]) + 1
    formats[str(number_id)] = '#,##0'
    # Explicit units in headings avoid any implicit rial/toman conversion.
    unit = 'ریال' if currency_id == 86 else 'دلار آمریکا' if currency_id == 1 else 'ارز اصلی'
    for sheet in data['sheets']:
        for address, cell in sheet.get('cells', {}).items():
            content = cell.get('content', '')
            if content.startswith('=FORMAT.LARGE.NUMBER(') and content.endswith(')'):
                cell['content'] = '=' + content[len('=FORMAT.LARGE.NUMBER('):-1]
                cell['format'] = number_id
            if 'ODOO.LIST' in content:
                cell['content'] = cell['content'].replace('"date_order"', '"date_order_jalali"')
            if sheet.get('name') == 'Data' and address[0] in ('B', 'C', 'D', 'E'):
                if address[1:] in ('2', '3', '4', '5', '6', '7', '8'):
                    cell['format'] = number_id
        for figure in sheet.get('figures', []):
            chart = figure.get('data', {})
            title = chart.get('title', '')
            if 'مبلغ' in title or 'روند ماهانه' in title:
                chart['title'] = title + ' — ' + unit
    for source in data.get('lists', {}).values():
        # Native list column metadata uses field-name strings.
        source['columns'] = [
            'date_order_jalali' if column == 'date_order' else column
            for column in source.get('columns', [])
        ]
    for definition in data.get('globalFilters', []):
        if definition.get('type') == 'date':
            definition['label'] = 'بازه تاریخ شمسی'
            definition['rangeType'] = 'from_to'
            definition['defaultValue'] = {}


def post_init_hook(env):
    company = env['res.company'].browse(3).exists()
    owner = env['res.users'].browse(19).exists()
    if not company or not owner or company not in owner.company_ids:
        raise UserError('Expected company 3 and salesperson 19 with company access.')
    irr = env['res.currency'].search([('name', '=', 'IRR')], limit=1)
    usd = env['res.currency'].search([('name', '=', 'USD')], limit=1)
    if not irr:
        raise UserError('IRR currency is missing.')
    personal_group = env.ref('vagirest_native_dashboard.group_personal_dashboard')
    manager_group = env.ref('sales_team.group_sale_manager')
    owner.write({'groups_id': [(4, personal_group.id)]})
    group = env['spreadsheet.dashboard.group'].create({'name': 'واژیرست — کوتیشن‌ها', 'sequence': 5})
    env['ir.model.data'].create({'module': 'vagirest_native_dashboard', 'name': 'dashboard_group',
                               'model': group._name, 'res_id': group.id, 'noupdate': True})
    cases = [('company_irr', 'شرکت — ریال', irr, None),
             ('sanaz_irr', 'ثبت‌شده توسط ساناز — ریال', irr, owner)]
    if usd:
        cases.append(('company_usd', 'شرکت — دلار', usd, None))
    for prefix, title, currency, person in cases:
        for product, suffix, source_xmlid in [
            (False, 'عملکرد', 'spreadsheet_dashboard_sale.spreadsheet_dashboard_sales'),
            (True, 'محصولات', 'spreadsheet_dashboard_sale.spreadsheet_dashboard_product'),
        ]:
            source = env.ref(source_xmlid)
            snapshot = json.loads(source.spreadsheet_data)
            data = build_snapshot(snapshot, company.id, currency.id, person.id if person else None, product)
            access = [manager_group.id] + ([personal_group.id] if person else [])
            created = source.copy({
                'name': title + ' / ' + suffix,
                'dashboard_group_id': group.id, 'sequence': 10 if person is None else 30,
                'group_ids': [(6, 0, access)],
                'vagirest_dashboard_company_id': company.id,
                'vagirest_dashboard_owner_id': person.id if person else False,
                'spreadsheet_binary_data': base64.b64encode(json.dumps(data, ensure_ascii=False).encode()),
            })
            env['ir.model.data'].create({'module': 'vagirest_native_dashboard',
                                        'name': prefix + ('_products' if product else '_overview'),
                                        'model': created._name, 'res_id': created.id, 'noupdate': True})

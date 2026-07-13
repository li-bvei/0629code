from pathlib import Path

from django.conf import settings


PRIMARY_TEMPLATE_DIR = Path(settings.BASE_DIR) / 'assets' / 'pdf_templates' / 'zei' / 'pdf'
UPLOADED_TEMPLATE_DIR = Path(settings.BASE_DIR) / 'assets' / 'pdf_templates' / 'tax'

TEMPLATE_DEFINITIONS = [
    {
        'key': 'social_insurance_payment_certificate_power_of_attorney',
        'name': '社会保险纳入证明兼委任状',
        'category': 'renewal',
        'condition': 'none',
        'order': 1,
        'match_terms': ['社会保険', '納入証明', '委任状'],
        'required_fields': [
            'company_name',
            'company_address',
            'representative_name',
            'representative_position',
            'establishment_symbol',
            'establishment_number',
            'application_reason',
            'fiscal_period_start',
            'fiscal_period_end',
            'agent_name',
            'agent_address',
            'agent_phone',
            'agent_relationship',
            'submit_date',
        ],
    },
    {
        'key': 'tax_certificate_request_tax_office',
        'name': '纳税证明书交付请求书-税务署',
        'category': 'renewal',
        'condition': 'none',
        'order': 2,
        'match_terms': ['納税証明書税務署'],
        'required_fields': [],
    },
    {
        'key': 'tax_certificate_power_of_attorney_tax_office',
        'name': '纳税证明委任状-税务署',
        'category': 'renewal',
        'condition': 'none',
        'order': 3,
        'match_terms': ['納税証明書税務署委任状'],
        'required_fields': [],
    },
    {
        'key': 'tax_certificate_request_osaka_city',
        'name': '纳税证明书交付请求书-大阪市税',
        'category': 'renewal',
        'condition': 'none',
        'order': 4,
        'match_terms': ['法人市民税証明書'],
        'required_fields': [],
    },
    {
        'key': 'tax_certificate_power_of_attorney_osaka_city',
        'name': '纳税证明委任状-大阪市税',
        'category': 'renewal',
        'condition': 'none',
        'order': 5,
        'match_terms': ['法人市民税委任状'],
        'required_fields': [],
    },
    {
        'key': 'tax_certificate_request_power_of_attorney_osaka_prefecture',
        'name': '纳税证明书交付请求书兼委任状-大阪府税',
        'category': 'renewal',
        'condition': 'none',
        'order': 6,
        'match_terms': ['大阪府', '納税証明書', '委任状'],
        'required_fields': [],
    },
    {
        'key': 'labor_insurance_payment_certificate',
        'name': '労働保険料等納入証明書',
        'category': 'renewal',
        'condition': 'has_employees',
        'order': 7,
        'match_terms': ['労働保険', '納入証明'],
        'required_fields': [],
    },
    {
        'key': 'pension_office_application',
        'name': '年金适用事务所加入届',
        'category': 'pension',
        'condition': 'none',
        'order': 8,
        'match_terms': ['年金新規適用届'],
        'required_fields': [],
    },
    {
        'key': 'pension_insured_qualification_acquisition',
        'name': '年金被保险者资格取得届',
        'category': 'pension',
        'condition': 'none',
        'order': 9,
        'match_terms': ['年金被保険者資格取得届'],
        'required_fields': [],
    },
    {
        'key': 'dependent_change_notification',
        'name': '被扶养者（异动）届',
        'category': 'pension',
        'condition': 'has_dependents',
        'order': 10,
        'match_terms': ['被扶養者', '異動'],
        'required_fields': [],
    },
]


def scan_pdf_files():
    directories = [PRIMARY_TEMPLATE_DIR]
    if not PRIMARY_TEMPLATE_DIR.exists():
        directories.append(UPLOADED_TEMPLATE_DIR)

    files = []
    seen = set()
    for directory in directories:
        if not directory.exists():
            continue
        for path in sorted(directory.glob('*.pdf')):
            if path.name in seen:
                continue
            seen.add(path.name)
            files.append(path)
    return files


def find_matching_pdf(definition, pdf_files):
    for path in pdf_files:
        stem = path.stem
        if all(term in stem for term in definition['match_terms']):
            return path
    return None


def get_tax_renewal_templates():
    pdf_files = scan_pdf_files()
    templates = []
    matched_names = set()

    for definition in TEMPLATE_DEFINITIONS:
        match = find_matching_pdf(definition, pdf_files)
        if match:
            matched_names.add(match.name)
        templates.append({
            'key': definition['key'],
            'name': definition['name'],
            'category': definition['category'],
            'filename': match.name if match else '',
            'file_path': str(match) if match else '',
            'file_exists': bool(match and match.exists()),
            'condition': definition['condition'],
            'order': definition['order'],
            'required_fields': definition.get('required_fields', []),
        })

    return templates


def get_unmatched_pdf_files():
    matched = {template['filename'] for template in get_tax_renewal_templates() if template['filename']}
    return [path.name for path in scan_pdf_files() if path.name not in matched]


def get_missing_template_names():
    return [template['name'] for template in get_tax_renewal_templates() if not template['file_exists']]

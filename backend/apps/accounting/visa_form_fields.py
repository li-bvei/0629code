import json
import shutil
from datetime import date, datetime
from pathlib import Path

import fitz
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .visa_return_pdf import CHECKED_VALUES, TEMPLATE_DIR, format_date, get_form_data, get_snapshot


VISA_FORM_TEMPLATE_PATH = TEMPLATE_DIR / 'visa_tem.pdf'
FORM_FIELD_MAPPING_PATH = TEMPLATE_DIR / 'form_field_mapping.json'

SYSTEM_VARIABLE_GROUPS = [
    {
        'label': '申请人信息',
        'items': [
            'applicant_name',
            'applicant_kana',
            'applicant_name_en',
            'birth_date',
            'gender',
            'nationality',
            'marital_status',
            'occupation',
            'passport_number',
            'passport_issue_date',
            'passport_expiry_date',
            'residence_card_number',
            'residence_status',
            'residence_expiry_date',
            'postal_code',
            'address',
            'phone',
            'email',
            'note',
        ],
    },
    {
        'label': '旧 visa 表 form_data 字段',
        'items': [
            'pinyin_name1',
            'pinyin_name2',
            'chinese_name1',
            'chinese_name2',
            'used_name1',
            'used_name2',
            'othernationality',
            'birth_place',
            'chinese_id',
            'passport_address',
            'passport_a',
            'zailiu_number',
            'entry_port',
            'airline',
            'entry_time1',
            'entry_time2',
            'entry_time3',
            'home_address1',
            'home_address2',
            'home_phone',
            'workplace_name',
            'workplace_address',
            'workplace_phone',
            'hotel',
            'hotel_phone',
            'hotel_address',
            'last',
            'job_title2',
            'guarantor_name_en',
            'guarantor_address_en',
            'guarantor_birth_date',
            'guarantor_nationality',
            'gender2',
            'x1',
            'x2',
            'x3',
            'x4',
            'x5',
            'x6',
        ],
    },
    {
        'label': '保证人字段',
        'items': [
            'guarantor_name',
            'guarantor_kana',
            'guarantor_postal_code',
            'guarantor_address',
            'guarantor_phone',
            'guarantor_company_name',
            'guarantor_occupation',
            'guarantor_relationship',
            'guarantor_guarantee_text',
        ],
    },
]


def flat_system_variables():
    return [
        {'group': group['label'], 'name': item}
        for group in SYSTEM_VARIABLE_GROUPS
        for item in group['items']
    ]


def load_form_field_mapping():
    if not FORM_FIELD_MAPPING_PATH.exists():
        return {'template': 'visa_tem.pdf', 'mappings': {}}
    with FORM_FIELD_MAPPING_PATH.open('r', encoding='utf-8') as file:
        return json.load(file)


def save_form_field_mapping(mapping):
    if FORM_FIELD_MAPPING_PATH.exists():
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        backup_path = TEMPLATE_DIR / f'form_field_mapping.backup.{timestamp}.json'
        shutil.copy2(FORM_FIELD_MAPPING_PATH, backup_path)

    with FORM_FIELD_MAPPING_PATH.open('w', encoding='utf-8') as file:
        json.dump(mapping, file, ensure_ascii=False, indent=2)
        file.write('\n')


def widget_type(widget):
    field_type = (widget.field_type_string or '').lower()
    if 'check' in field_type:
        return 'checkbox'
    if 'radio' in field_type:
        return 'radio'
    if 'combo' in field_type or 'list' in field_type:
        return 'choice'
    return 'text'


def widget_options(widget):
    options = []
    choice_values = getattr(widget, 'choice_values', None)
    if choice_values:
        for option in choice_values:
            if isinstance(option, (tuple, list)):
                value = option[0] if option else ''
                label = option[1] if len(option) > 1 else value
                options.append({'value': value, 'label': label})
            else:
                options.append({'value': option, 'label': option})

    try:
        states = widget.button_states()
    except Exception:
        states = None
    if states:
        options.append({'value': states, 'label': 'button_states'})

    return options


def inspect_form_fields():
    if not VISA_FORM_TEMPLATE_PATH.exists():
        return {
            'template': 'visa_tem.pdf',
            'fields': [],
            'error': f'Template not found: {VISA_FORM_TEMPLATE_PATH}',
        }

    doc = fitz.open(str(VISA_FORM_TEMPLATE_PATH))
    fields = []
    pages = {}
    for page_index, page in enumerate(doc, start=1):
        pages[str(page_index)] = {
            'width': page.rect.width,
            'height': page.rect.height,
        }
        for widget_index, widget in enumerate(page.widgets() or []):
            rect = widget.rect
            fields.append({
                'name': widget.field_name,
                'type': widget_type(widget),
                'raw_type': widget.field_type_string,
                'value': widget.field_value,
                'options': widget_options(widget),
                'page': page_index,
                'index': widget_index,
                'rect': {
                    'x0': rect.x0,
                    'y0': rect.y0,
                    'x1': rect.x1,
                    'y1': rect.y1,
                    'width': rect.width,
                    'height': rect.height,
                },
            })
    doc.close()

    result = {
        'template': 'visa_tem.pdf',
        'fields': fields,
        'pages': pages,
    }
    if not fields:
        result['error'] = 'visa_tem.pdf に AcroForm フィールドが見つかりません。'
    return result


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def visa_form_fields(request):
    payload = inspect_form_fields()
    payload['mapping'] = load_form_field_mapping()
    payload['system_variables'] = flat_system_variables()
    payload['system_variable_groups'] = SYSTEM_VARIABLE_GROUPS
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def visa_form_fields_preview(request):
    page_number = request.query_params.get('page', '1')
    if page_number not in ('1', '2'):
        return Response({'detail': 'page must be 1 or 2.'}, status=400)
    if not VISA_FORM_TEMPLATE_PATH.exists():
        return Response({'detail': f'Template not found: {VISA_FORM_TEMPLATE_PATH}'}, status=404)

    doc = fitz.open(str(VISA_FORM_TEMPLATE_PATH))
    try:
        page_index = int(page_number) - 1
        if page_index < 0 or page_index >= doc.page_count:
            return Response({'detail': 'page not found.'}, status=404)
        page = doc[page_index]
        matrix = fitz.Matrix(2, 2)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        return HttpResponse(pixmap.tobytes('png'), content_type='image/png')
    finally:
        doc.close()


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def visa_form_field_mapping(request):
    if request.method == 'GET':
        return Response(load_form_field_mapping())

    mapping = request.data
    if not isinstance(mapping, dict):
        return Response({'detail': 'mapping must be an object.'}, status=400)
    mapping.setdefault('template', 'visa_tem.pdf')
    mapping.setdefault('mappings', {})
    save_form_field_mapping(mapping)
    return Response({'detail': 'saved'})


def format_mapped_date(value, output_format):
    if not value:
        return ''
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, str):
        for input_format in ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d'):
            try:
                value = datetime.strptime(value, input_format).date()
                break
            except ValueError:
                continue
    if isinstance(value, date):
        if output_format == 'yyyy-mm-dd':
            return value.strftime('%Y-%m-%d')
        if output_format == 'yyyy年mm月dd日':
            return f'{value.year}年{value.month}月{value.day}日'
        return value.strftime('%d/%m/%Y')
    return str(value)


def get_application_variables(application):
    form_data = get_form_data(application)
    snapshot = get_snapshot(application)
    variables = {
        'applicant_name': getattr(application, 'applicant_name', ''),
        'birth_date': getattr(application, 'birth_date', ''),
        'gender': getattr(application, 'gender', ''),
        'nationality': getattr(application, 'nationality', ''),
        'marital_status': getattr(application, 'marital_status', ''),
        'occupation': getattr(application, 'occupation', ''),
        'passport_number': getattr(application, 'passport_number', ''),
        'passport_issue_date': getattr(application, 'passport_issue_date', ''),
        'passport_expiry_date': getattr(application, 'passport_expiry_date', ''),
        'residence_status': getattr(application, 'residence_status', ''),
        'address': getattr(application, 'address', ''),
        'phone': getattr(application, 'phone', ''),
        'email': getattr(application, 'email', ''),
        'note': getattr(application, 'note', ''),
        'guarantor_name': getattr(application, 'guarantor_name', ''),
        'guarantor_address': getattr(application, 'guarantor_address', ''),
        'guarantor_phone': getattr(application, 'guarantor_phone', ''),
        'guarantor_occupation': getattr(application, 'guarantor_occupation', ''),
        'guarantor_relationship': getattr(application, 'guarantor_relationship', ''),
    }
    variables.update({key: value for key, value in form_data.items() if value not in (None, '')})
    variables.update({key: value for key, value in snapshot.items() if value not in (None, '')})
    return variables


def mapped_value(value, config):
    if config.get('format'):
        return format_mapped_date(value, config.get('format'))
    if isinstance(value, (datetime, date)):
        return format_date(value)
    if value is None:
        return ''
    return str(value)


def checked_value(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if value is None:
        return False
    return str(value).strip().lower() in CHECKED_VALUES


def update_widget(widget, value):
    widget.field_value = value
    widget.update()


def fill_form_pdf(application):
    if not VISA_FORM_TEMPLATE_PATH.exists():
        raise FileNotFoundError(f'visa_tem.pdf not found: {VISA_FORM_TEMPLATE_PATH}')
    mapping = load_form_field_mapping()
    mappings = mapping.get('mappings') or {}
    if not mappings:
        raise ValueError('form_field_mapping.json has no mappings.')

    variables = get_application_variables(application)
    doc = fitz.open(str(VISA_FORM_TEMPLATE_PATH))
    widgets_by_name = {}
    for page in doc:
        for widget in page.widgets() or []:
            widgets_by_name.setdefault(widget.field_name, []).append(widget)

    for variable_name, config in mappings.items():
        config_type = config.get('type', 'text')
        if config_type == 'choice':
            value = variables.get(variable_name, '')
            rule = (config.get('rules') or {}).get(str(value))
            if not rule:
                continue
            pdf_field = rule.get('pdf_field')
            checked = rule.get('value', rule.get('checked_value', 'Yes'))
            for widget in widgets_by_name.get(pdf_field, []):
                update_widget(widget, checked)
            continue

        pdf_field = config.get('pdf_field')
        if not pdf_field:
            continue
        value = variables.get(variable_name, '')
        for widget in widgets_by_name.get(pdf_field, []):
            if config_type in ('checkbox', 'radio'):
                next_value = config.get('checked_value', config.get('value', 'Yes')) if checked_value(value) else config.get('unchecked_value', 'Off')
            else:
                next_value = mapped_value(value, config)
            update_widget(widget, next_value)

    output = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return output


def form_pdf_response(application):
    return HttpResponse(fill_form_pdf(application), content_type='application/pdf')

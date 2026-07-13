import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import fitz
from django.conf import settings
from django.http import HttpResponse

from .tax_renewal_templates import get_tax_renewal_templates


SUPPORTED_TEMPLATE_KEY = 'social_insurance_payment_certificate_power_of_attorney'
MAPPING_DIR = Path(settings.BASE_DIR) / 'assets' / 'pdf_templates' / 'zei' / 'field_mappings'
FONT_DIR = Path(settings.BASE_DIR) / 'assets' / 'fonts'
FONT_PATH = FONT_DIR / 'YuMincho.ttf'
FONT_NAME = 'TaxRenewalCJK'
ALIGN_VALUES = {
    'left': fitz.TEXT_ALIGN_LEFT,
    'center': fitz.TEXT_ALIGN_CENTER,
    'right': fitz.TEXT_ALIGN_RIGHT,
}
VALIGN_VALUES = {'top', 'middle', 'bottom'}
RENDER_MODES = {'text', 'split', 'boxes'}

FIELD_ALIASES = {
    '記号': 'establishment_symbol',
    '事業所番号': 'establishment_number',
    '申請事由': 'application_reason',
    '開始年': 'fiscal_start_year_jp',
    '開始月': 'fiscal_start_month',
    '終了年': 'fiscal_end_year_jp',
    '終了月': 'fiscal_end_month',
    '事業所所在地': 'company_address',
    '代表者名': 'representative_name',
    '代表者肩書': 'representative_position',
    '代理人氏名': 'agent_name',
    '代理人住所': 'agent_address',
    '代理人関係': 'agent_relationship',
}


@dataclass
class TaxRenewalPdfStats:
    mapping_field_count: int = 0
    written_field_count: int = 0
    skipped_empty_field_count: int = 0
    warning_fields: list[str] = field(default_factory=list)


@dataclass
class TaxRenewalPdfResult:
    pdf_bytes: bytes
    stats: TaxRenewalPdfStats


def generate_tax_renewal_template_pdf(record, template_key):
    return generate_tax_renewal_template_pdf_result(record, template_key).pdf_bytes


def generate_tax_renewal_template_pdf_result(record, template_key):
    if template_key != SUPPORTED_TEMPLATE_KEY:
        raise ValueError('PDF字段映射未完成')

    template = get_template(template_key)
    if not template.get('file_exists'):
        raise FileNotFoundError('模板文件不存在')
    mapping = read_mapping(template_key)
    fields = mapping.get('fields') if isinstance(mapping.get('fields'), dict) else {}
    if not fields:
        raise ValueError('mapping 没有字段')

    font_path = find_font()
    if not font_path:
        raise FileNotFoundError(f'PDF生成用字体不存在：{FONT_PATH}')

    data = build_record_data(record)
    stats = TaxRenewalPdfStats(mapping_field_count=len(fields))
    doc = fitz.open(template['file_path'])
    try:
        for page in doc:
            page.insert_font(fontname=FONT_NAME, fontfile=str(font_path))

        for field_key, raw_field in fields.items():
            if not isinstance(raw_field, dict):
                stats.warning_fields.append(str(field_key))
                continue
            field = normalize_field(str(field_key), raw_field)
            value = resolve_field_value(str(field_key), data)
            if value == '':
                stats.skipped_empty_field_count += 1
                continue
            if field['page'] < 1 or field['page'] > doc.page_count:
                stats.warning_fields.append(str(field_key))
                continue
            page = doc[field['page'] - 1]
            before_warnings = len(stats.warning_fields)
            if field['render_mode'] == 'split':
                written = draw_split_field(page, str(field_key), value, field, stats)
            elif field['render_mode'] == 'boxes':
                written = draw_boxes_field(page, str(field_key), value, field, stats)
            else:
                written = draw_text_field(page, str(field_key), value, field, stats)
            if written and len(stats.warning_fields) == before_warnings:
                stats.written_field_count += 1
            elif written:
                stats.written_field_count += 1

        output = BytesIO()
        doc.save(output, garbage=4, deflate=True, clean=True)
        output.seek(0)
        return TaxRenewalPdfResult(pdf_bytes=output.getvalue(), stats=stats)
    finally:
        doc.close()


def tax_renewal_pdf_response(record, template_key):
    result = generate_tax_renewal_template_pdf_result(record, template_key)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    filename = f'社会保険納入証明書兼委任状_{safe_filename(record.title)}_{timestamp}.pdf'
    response = HttpResponse(result.pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="social_insurance.pdf"; filename*=UTF-8\'\'{quote(filename)}'
    )
    response['X-Mapping-Field-Count'] = str(result.stats.mapping_field_count)
    response['X-Written-Field-Count'] = str(result.stats.written_field_count)
    response['X-Skipped-Empty-Field-Count'] = str(result.stats.skipped_empty_field_count)
    response['X-Warning-Fields'] = quote(','.join(result.stats.warning_fields))
    return response


def get_template(template_key):
    template = next((item for item in get_tax_renewal_templates() if item['key'] == template_key), None)
    if not template:
        raise ValueError('模板不存在')
    return template


def read_mapping(template_key):
    path = MAPPING_DIR / f'{template_key}.json'
    if not path.exists():
        raise FileNotFoundError('mapping 文件不存在')
    with path.open('r', encoding='utf-8') as file:
        mapping = json.load(file)
    if not isinstance(mapping, dict):
        raise ValueError('mapping 格式不正确')
    return mapping


def find_font():
    return FONT_PATH if FONT_PATH.exists() else None


def safe_filename(value):
    cleaned = re.sub(r'[\\/:*?"<>|\r\n]+', '_', str(value or '').strip())
    return cleaned or 'record'


def stringify(value):
    if value is None:
        return ''
    if isinstance(value, (date, datetime)):
        return value.strftime('%Y-%m-%d')
    return str(value).strip()


def object_value(obj, key):
    if not obj:
        return ''
    return stringify(getattr(obj, key, ''))


def form_value(form_data, key):
    value = form_data.get(key)
    if value is None:
        return ''
    return stringify(value)


def japanese_era_year(value):
    try:
        year = int(value)
    except (TypeError, ValueError):
        return ''
    if year >= 2019:
        return str(year - 2018)
    return str(year)


def build_record_data(record):
    form_data = record.form_data if isinstance(record.form_data, dict) else {}
    data = {}

    for key, value in form_data.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            data[key] = stringify(value)

    agent_snapshot = form_data.get('agent_snapshot')
    if isinstance(agent_snapshot, dict):
        for key, value in agent_snapshot.items():
            data.setdefault(key, stringify(value))
            if str(key).startswith('agent_'):
                data.setdefault(str(key), stringify(value))

    company = getattr(record, 'company', None)
    customer = getattr(record, 'customer', None)
    employee = getattr(record, 'employee', None)
    fallbacks = {
        'company_name': object_value(company, 'name'),
        'company_number': object_value(company, 'corporate_number') or object_value(company, 'corporate_registration_number'),
        'company_address': object_value(company, 'address'),
        'company_phone': object_value(company, 'phone'),
        'representative_name': object_value(company, 'representative_name'),
        'representative_kana': object_value(company, 'representative_name_kana'),
        'applicant_name': object_value(customer, 'name'),
        'applicant_kana': object_value(customer, 'name_kana'),
        'applicant_address': object_value(customer, 'address'),
        'applicant_phone': object_value(customer, 'phone'),
        'applicant_birth_date': object_value(customer, 'birth_date'),
        'employee_name': object_value(employee, 'name'),
        'employee_phone': object_value(employee, 'phone'),
    }
    for key, value in fallbacks.items():
        if not data.get(key) and value:
            data[key] = value

    if not data.get('fiscal_start_year_jp'):
        data['fiscal_start_year_jp'] = japanese_era_year(data.get('fiscal_start_year'))
    if not data.get('fiscal_end_year_jp'):
        data['fiscal_end_year_jp'] = japanese_era_year(data.get('fiscal_end_year'))
    if not data.get('establishment_symbol') and data.get('social_insurance_symbol'):
        data['establishment_symbol'] = data['social_insurance_symbol']
    if not data.get('establishment_number') and data.get('social_insurance_office_number'):
        data['establishment_number'] = data['social_insurance_office_number']

    return data


def resolve_field_value(field_key, data):
    keys = [field_key]
    alias = FIELD_ALIASES.get(field_key)
    if alias:
        keys.append(alias)
    for key in keys:
        value = data.get(key)
        if value not in (None, ''):
            return stringify(value)
    return ''


def number_value(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def int_value(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_field(field_key, field):
    font_size = number_value(field.get('font_size'), 10)
    render_mode = str(field.get('render_mode') or field.get('type') or 'text')
    align = str(field.get('align') or 'left')
    valign = str(field.get('valign') or 'top')
    if render_mode not in RENDER_MODES:
        render_mode = 'text'
    if align not in ALIGN_VALUES:
        align = 'left'
    if valign not in VALIGN_VALUES:
        valign = 'top'
    return {
        'page': int_value(field.get('page'), 1),
        'x': number_value(field.get('x'), 100),
        'y': number_value(field.get('y'), 100),
        'font_size': font_size,
        'width': number_value(field.get('width'), 150),
        'height': number_value(field.get('height'), number_value(field.get('box_height'), font_size * 1.5)),
        'align': align,
        'valign': valign,
        'max_lines': max(int_value(field.get('max_lines'), 1), 1),
        'letter_spacing': number_value(field.get('letter_spacing'), 0),
        'render_mode': render_mode,
        'split_pattern': field.get('split_pattern') or '-',
        'parts': field.get('parts') if isinstance(field.get('parts'), list) else [],
        'box_count': max(int_value(field.get('box_count'), 0), 0),
        'start_x': number_value(field.get('start_x'), number_value(field.get('x'), 100)),
        'box_width': number_value(field.get('box_width'), 18),
        'box_height': number_value(field.get('box_height'), number_value(field.get('height'), font_size * 1.5)),
        'box_gap': number_value(field.get('box_gap'), 2),
    }


def estimate_max_chars(width, font_size):
    return max(int(width / max(font_size * 0.55, 1)), 1)


def split_lines(value, max_chars):
    if max_chars <= 0:
        return [value]
    lines = []
    text = value
    while text:
        lines.append(text[:max_chars])
        text = text[max_chars:]
    return lines or ['']


def textbox_rect(field):
    return fitz.Rect(
        field['x'],
        field['y'],
        field['x'] + max(field['width'], 1),
        field['y'] + max(field['height'], 1),
    )


def adjusted_rect_for_valign(rect, field, line_count):
    text_height = max(line_count, 1) * field['font_size'] * 1.25
    if field['valign'] == 'middle' and rect.height > text_height:
        top = rect.y0 + (rect.height - text_height) / 2
        return fitz.Rect(rect.x0, top, rect.x1, top + text_height)
    if field['valign'] == 'bottom' and rect.height > text_height:
        return fitz.Rect(rect.x0, rect.y1 - text_height, rect.x1, rect.y1)
    return rect


def draw_text_field(page, field_key, value, field, stats):
    rect = textbox_rect(field)
    max_chars = estimate_max_chars(field['width'], field['font_size'])
    all_lines = split_lines(value, max_chars)
    lines = all_lines[:field['max_lines']]
    if len(all_lines) > field['max_lines']:
        stats.warning_fields.append(field_key)
    text = '\n'.join(lines)
    if field['letter_spacing'] and field['max_lines'] == 1:
        return draw_spaced_line(page, field_key, text.replace('\n', ''), rect, field, stats)
    rect = adjusted_rect_for_valign(rect, field, len(lines))
    rc = page.insert_textbox(
        rect,
        text,
        fontsize=field['font_size'],
        fontname=FONT_NAME,
        color=(0, 0, 0),
        align=ALIGN_VALUES[field['align']],
        overlay=True,
    )
    if rc < 0:
        stats.warning_fields.append(field_key)
    return True


def draw_spaced_line(page, field_key, text, rect, field, stats):
    font_size = field['font_size']
    spacing = field['letter_spacing']
    char_width = font_size * 0.55
    total_width = len(text) * char_width + max(len(text) - 1, 0) * spacing
    if total_width > rect.width:
        stats.warning_fields.append(field_key)
    if field['align'] == 'center':
        x = rect.x0 + max((rect.width - total_width) / 2, 0)
    elif field['align'] == 'right':
        x = rect.x1 - total_width
    else:
        x = rect.x0
    if field['valign'] == 'middle':
        y = rect.y0 + (rect.height - font_size) / 2 + font_size
    elif field['valign'] == 'bottom':
        y = rect.y1
    else:
        y = rect.y0 + font_size
    for char in text:
        page.insert_text(
            fitz.Point(x, y),
            char,
            fontsize=font_size,
            fontname=FONT_NAME,
            color=(0, 0, 0),
            overlay=True,
        )
        x += char_width + spacing
    return True


def draw_split_field(page, field_key, value, field, stats):
    parts = field.get('parts') or []
    if not parts:
        return draw_text_field(page, field_key, value, field, stats)
    pattern = field.get('split_pattern') or '-'
    values = value.split(pattern) if pattern else list(value)
    if len(values) > len(parts):
        stats.warning_fields.append(field_key)
    wrote = False
    for index, part in enumerate(parts):
        if not isinstance(part, dict):
            continue
        part_value = values[index] if index < len(values) else ''
        if part_value == '':
            continue
        part_field = normalize_field(f'{field_key}_{index + 1}', {
            **field,
            **part,
            'x': part.get('x', field['x']),
            'y': part.get('y', field['y']),
            'width': part.get('width', field['width']),
            'height': part.get('height', field['height']),
            'font_size': part.get('font_size', field['font_size']),
            'align': part.get('align', field['align']),
            'render_mode': 'text',
        })
        draw_text_field(page, f'{field_key}_{index + 1}', part_value, part_field, stats)
        wrote = True
    return wrote


def draw_boxes_field(page, field_key, value, field, stats):
    chars = list(value)
    box_count = field['box_count'] or len(chars)
    if len(chars) > box_count:
        stats.warning_fields.append(field_key)
    wrote = False
    for index in range(box_count):
        char = chars[index] if index < len(chars) else ''
        if char == '':
            continue
        x = field['start_x'] + index * (field['box_width'] + field['box_gap'])
        rect = fitz.Rect(x, field['y'], x + field['box_width'], field['y'] + field['box_height'])
        draw_box_char(page, char, rect, field)
        wrote = True
    return wrote


def draw_box_char(page, char, rect, field):
    font_size = field['font_size']
    estimated_width = font_size * (0.72 if ord(char) > 127 else 0.55)
    x = rect.x0 + max((rect.width - estimated_width) / 2, 0)
    y = rect.y0 + (rect.height - font_size) / 2 + font_size * 0.86
    page.insert_text(
        fitz.Point(x, y),
        char,
        fontsize=font_size,
        fontname=FONT_NAME,
        color=(0, 0, 0),
        overlay=True,
    )

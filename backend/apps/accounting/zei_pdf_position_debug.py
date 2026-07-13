import json
import shutil
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import fitz
from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .tax_renewal_templates import get_tax_renewal_templates


MAPPING_DIR = Path(settings.BASE_DIR) / 'assets' / 'pdf_templates' / 'zei' / 'field_mappings'
FONT_DIR = Path(settings.BASE_DIR) / 'assets' / 'fonts'
FONT_CANDIDATES = [
    FONT_DIR / 'dengxian.ttf',
    FONT_DIR / 'YuMincho.ttf',
]
DEBUG_FONT_NAME = 'ZeiDebugFont'
ALIGN_VALUES = {
    'left': fitz.TEXT_ALIGN_LEFT,
    'center': fitz.TEXT_ALIGN_CENTER,
    'right': fitz.TEXT_ALIGN_RIGHT,
}
VALIGN_VALUES = {'top', 'middle', 'bottom'}
RENDER_MODES = {'text', 'split', 'boxes'}


def template_map():
    return {template['key']: template for template in get_tax_renewal_templates()}


def mapping_path(template_key):
    return MAPPING_DIR / f'{template_key}.json'


def find_debug_font():
    for path in FONT_CANDIDATES:
        if path.exists():
            return path
    return None


def page_payloads(template):
    if not template.get('file_exists'):
        return []
    doc = fitz.open(template['file_path'])
    try:
        return [
            {
                'page': index + 1,
                'width': round(page.rect.width, 2),
                'height': round(page.rect.height, 2),
            }
            for index, page in enumerate(doc)
        ]
    finally:
        doc.close()


def default_mapping(template):
    pages = page_payloads(template)
    return {
        'template_key': template['key'],
        'template_name': template['name'],
        'filename': template.get('filename') or '',
        'page_count': len(pages),
        'fields': {},
    }


def read_mapping(template):
    MAPPING_DIR.mkdir(parents=True, exist_ok=True)
    path = mapping_path(template['key'])
    if not path.exists():
        mapping = default_mapping(template)
        write_mapping_file(path, mapping)
        return mapping
    with path.open('r', encoding='utf-8') as file:
        mapping = json.load(file)
    return normalize_mapping(template, mapping)


def write_mapping_file(path, mapping):
    with path.open('w', encoding='utf-8') as file:
        json.dump(mapping, file, ensure_ascii=False, indent=2)
        file.write('\n')


def normalize_mapping(template, mapping):
    if not isinstance(mapping, dict):
        mapping = {}
    normalized = default_mapping(template)
    fields = mapping.get('fields') if isinstance(mapping.get('fields'), dict) else {}
    normalized.update({
        'template_key': template['key'],
        'template_name': template['name'],
        'filename': template.get('filename') or '',
        'page_count': normalized['page_count'],
        'fields': {
            str(field_key): normalize_field(str(field_key), field)
            for field_key, field in fields.items()
            if isinstance(field, dict)
        },
    })
    return normalized


def float_value(value, default):
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
    font_size = float_value(field.get('font_size'), 10)
    width = float_value(field.get('width'), 150)
    height = float_value(field.get('height'), font_size * 1.5)
    test_value = field.get('test_value') if 'test_value' in field else field.get('label') or field_key
    align = str(field.get('align') or 'left')
    valign = str(field.get('valign') or 'top')
    render_mode = str(field.get('render_mode') or field.get('type') or 'text')
    field_type = str(field.get('type') or render_mode or 'text')
    if align not in ALIGN_VALUES:
        align = 'left'
    if valign not in VALIGN_VALUES:
        valign = 'top'
    if render_mode not in RENDER_MODES:
        render_mode = 'text'

    normalized = {
        'label': field.get('label') or field_key,
        'page': int_value(field.get('page'), 1),
        'x': float_value(field.get('x'), 100),
        'y': float_value(field.get('y'), 100),
        'type': field_type,
        'font_size': font_size,
        'test_value': test_value,
        'width': width,
        'height': height,
        'align': align,
        'valign': valign,
        'max_lines': int_value(field.get('max_lines'), 1),
        'letter_spacing': float_value(field.get('letter_spacing'), 0),
        'render_mode': render_mode,
        'split_pattern': field.get('split_pattern') or '-',
        'parts': field.get('parts') if isinstance(field.get('parts'), list) else [],
        'box_count': int_value(field.get('box_count'), 0),
        'start_x': float_value(field.get('start_x'), float_value(field.get('x'), 100)),
        'box_width': float_value(field.get('box_width'), 18),
        'box_gap': float_value(field.get('box_gap'), 2),
    }
    return normalized


def backup_mapping(path):
    if not path.exists():
        return ''
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    backup_path = path.with_name(f'{path.stem}.backup.{timestamp}.json')
    shutil.copy2(path, backup_path)
    return backup_path.name


def error_response(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({'detail': message}, status=code)


def get_template_or_error(template_key):
    template = template_map().get(template_key)
    if not template:
        raise ValueError('模板不存在')
    return template


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def zei_pdf_position_templates(request):
    rows = []
    for template in get_tax_renewal_templates():
        pages = page_payloads(template)
        path = mapping_path(template['key'])
        mapping_exists = path.exists()
        mapping_field_count = 0
        if mapping_exists:
            try:
                mapping = read_mapping(template)
                mapping_field_count = len(mapping.get('fields') or {})
            except (json.JSONDecodeError, OSError):
                mapping_field_count = 0
        rows.append({
            'key': template['key'],
            'name': template['name'],
            'filename': template.get('filename') or '',
            'file_exists': template['file_exists'],
            'page_count': len(pages),
            'pages': pages,
            'mapping_exists': mapping_exists,
            'mapping_field_count': mapping_field_count,
        })
    return Response(rows)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def zei_pdf_position_mapping(request):
    if request.method == 'GET':
        template_key = request.query_params.get('template_key')
        try:
            template = get_template_or_error(template_key)
        except ValueError as exc:
            return error_response(str(exc))
        return Response(read_mapping(template))

    template_key = request.data.get('template_key')
    mapping = request.data.get('mapping')
    if not isinstance(mapping, dict):
        return error_response('mapping must be an object.')
    try:
        template = get_template_or_error(template_key)
    except ValueError as exc:
        return error_response(str(exc))

    MAPPING_DIR.mkdir(parents=True, exist_ok=True)
    path = mapping_path(template['key'])
    backup_name = backup_mapping(path)
    normalized = normalize_mapping(template, mapping)
    write_mapping_file(path, normalized)
    return Response({'detail': 'saved', 'backup': backup_name, 'mapping': normalized})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def zei_pdf_position_preview(request):
    template_key = request.query_params.get('template_key')
    try:
        page_number = int(request.query_params.get('page', '1'))
        template = get_template_or_error(template_key)
    except (TypeError, ValueError) as exc:
        return error_response(str(exc) or '参数无效')
    if not template['file_exists']:
        return error_response('模板文件不存在', status.HTTP_404_NOT_FOUND)

    doc = fitz.open(template['file_path'])
    try:
        if page_number < 1 or page_number > doc.page_count:
            return error_response('页码超出范围')
        page = doc[page_number - 1]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(150 / 72, 150 / 72), alpha=False)
        return HttpResponse(pixmap.tobytes('png'), content_type='image/png')
    finally:
        doc.close()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def zei_pdf_position_test_pdf(request):
    template_key = request.data.get('template_key')
    try:
        template = get_template_or_error(template_key)
    except ValueError as exc:
        return error_response(str(exc))
    if not template['file_exists']:
        return error_response('模板文件不存在', status.HTTP_404_NOT_FOUND)

    mapping = read_mapping(template)
    fields = mapping.get('fields') or {}
    if not fields:
        return error_response('mapping 没有字段')

    font_path = find_debug_font()
    doc = fitz.open(template['file_path'])
    warnings = []
    try:
        if font_path:
            for page in doc:
                page.insert_font(fontname=DEBUG_FONT_NAME, fontfile=str(font_path))
        for field_key, field in fields.items():
            if not isinstance(field, dict):
                continue
            field = normalize_field(field_key, field)
            page_number = field['page']
            if page_number < 1 or page_number > doc.page_count:
                continue
            page = doc[page_number - 1]
            if field['render_mode'] == 'split':
                draw_split_field(page, field_key, field, font_path, warnings)
            elif field['render_mode'] == 'boxes':
                draw_boxes_field(page, field_key, field, font_path, warnings)
            else:
                draw_text_field(page, field_key, field, font_path, warnings)

        output = BytesIO()
        doc.save(output, garbage=4, deflate=True, clean=True)
        output.seek(0)
    finally:
        doc.close()

    filename = f'{template["key"]}_position_test.pdf'
    response = HttpResponse(output.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="zei_position_test.pdf"; filename*=UTF-8\'\'{quote(filename)}'
    )
    response['X-Position-Warnings'] = quote('\n'.join(warnings))
    return response


def field_value(field_key, field):
    value = field.get('test_value') or field.get('label') or field_key
    return str(value)


def font_kwargs(font_path):
    if not font_path:
        return {}
    return {'fontname': DEBUG_FONT_NAME}


def textbox_rect(field):
    return fitz.Rect(
        field['x'],
        field['y'],
        field['x'] + max(field['width'], 1),
        field['y'] + max(field['height'], 1),
    )


def split_lines(value, max_chars):
    if max_chars <= 0:
        return [value]
    lines = []
    text = value
    while text:
        lines.append(text[:max_chars])
        text = text[max_chars:]
    return lines or ['']


def estimate_max_chars(width, font_size):
    return max(int(width / max(font_size * 0.55, 1)), 1)


def draw_text_field(page, field_key, field, font_path, warnings):
    value = field_value(field_key, field)
    rect = textbox_rect(field)
    font_size = field['font_size']
    max_lines = max(field['max_lines'], 1)
    max_chars = estimate_max_chars(field['width'], font_size)
    lines = split_lines(value, max_chars)[:max_lines]
    text = '\n'.join(lines)
    if len(split_lines(value, max_chars)) > max_lines:
        warnings.append(f'字段内容超出范围：{field_key}')
    if field['letter_spacing'] and max_lines == 1:
        draw_spaced_line(page, rect, text.replace('\n', ''), field, font_path, warnings, field_key)
        return
    text_height = max(len(lines), 1) * font_size * 1.25
    if field['valign'] == 'middle' and rect.height > text_height:
        top = rect.y0 + (rect.height - text_height) / 2
        rect = fitz.Rect(rect.x0, top, rect.x1, top + text_height)
    elif field['valign'] == 'bottom' and rect.height > text_height:
        rect = fitz.Rect(rect.x0, rect.y1 - text_height, rect.x1, rect.y1)
    rc = page.insert_textbox(
        rect,
        text,
        fontsize=font_size,
        color=(0, 0, 0),
        align=ALIGN_VALUES[field['align']],
        overlay=True,
        **font_kwargs(font_path),
    )
    if rc < 0:
        warnings.append(f'字段内容超出范围：{field_key}')


def draw_spaced_line(page, rect, text, field, font_path, warnings, field_key):
    font_size = field['font_size']
    spacing = field['letter_spacing']
    char_width = font_size * 0.55
    total_width = len(text) * char_width + max(len(text) - 1, 0) * spacing
    if total_width > rect.width:
        warnings.append(f'字段内容超出范围：{field_key}')
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
            color=(0, 0, 0),
            overlay=True,
            **font_kwargs(font_path),
        )
        x += char_width + spacing


def draw_split_field(page, field_key, field, font_path, warnings):
    value = field_value(field_key, field)
    pattern = field.get('split_pattern') or '-'
    parts = field.get('parts') or []
    values = value.split(pattern) if pattern else list(value)
    if len(values) > len(parts):
        warnings.append(f'字段内容超出范围：{field_key}')
    for index, part in enumerate(parts):
        if not isinstance(part, dict):
            continue
        part_field = normalize_field(f'{field_key}_{index + 1}', {
            **field,
            **part,
            'test_value': values[index] if index < len(values) else '',
            'render_mode': 'text',
            'height': part.get('height', field['height']),
            'font_size': part.get('font_size', field['font_size']),
            'align': part.get('align', field['align']),
        })
        draw_text_field(page, f'{field_key}_{index + 1}', part_field, font_path, warnings)


def draw_boxes_field(page, field_key, field, font_path, warnings):
    value = field_value(field_key, field)
    chars = list(value)
    box_count = field['box_count'] or len(chars)
    if len(chars) > box_count:
        warnings.append(f'字段内容超出范围：{field_key}')
    for index in range(box_count):
        part_field = normalize_field(f'{field_key}_{index + 1}', {
            **field,
            'test_value': chars[index] if index < len(chars) else '',
            'x': field['start_x'] + index * (field['box_width'] + field['box_gap']),
            'y': field['y'],
            'width': field['box_width'],
            'height': field['height'],
            'align': 'center',
            'render_mode': 'text',
            'max_lines': 1,
        })
        draw_text_field(page, f'{field_key}_{index + 1}', part_field, font_path, warnings)

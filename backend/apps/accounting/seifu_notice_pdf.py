from datetime import datetime
from io import BytesIO
from pathlib import Path
import re
from urllib.parse import quote

import fitz
from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


TEMPLATE_PATH = Path(settings.BASE_DIR) / 'assets' / 'pdf_templates' / 'seifu' / '合格通知書.pdf'
FONT_DIR = Path(settings.BASE_DIR) / 'assets' / 'fonts'
FONT_CANDIDATES = [
    FONT_DIR / 'Adobe 黑体 Std R.otf',
    FONT_DIR / 'AdobeHeitiStd-Regular.otf',
    FONT_DIR / 'AdobeHeitiStd.otf',
]
FONT_ERROR = '缺少字体文件：Adobe 黑体 Std'
TEMPLATE_ERROR = '清風合格通知書模板不存在：合格通知書.pdf'
PDF_FONT_NAME = 'AdobeHeitiStd'
TEXT_FONT_SIZE = 18
TEXT_COLOR = (0x38 / 255, 0x37 / 255, 0x37 / 255)
DEFAULT_COLOR_HEX = '#383737'
DEFAULT_FONT_FAMILY = 'adobe_heiti'
DEFAULT_FONT_WEIGHT = 'normal'


def find_adobe_heiti_font():
    for path in FONT_CANDIDATES:
        if path.exists():
            return path
    return None


def template_doc():
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(TEMPLATE_ERROR)
    return fitz.open(str(TEMPLATE_PATH))


def template_payload():
    font_path = find_adobe_heiti_font()
    if not TEMPLATE_PATH.exists():
        return {
            'page_count': 0,
            'pages': [],
            'font_available': bool(font_path),
            'font_error': None if font_path else FONT_ERROR,
            'template_error': TEMPLATE_ERROR,
        }

    doc = template_doc()
    try:
        pages = [
            {
                'page': index + 1,
                'width': page.rect.width,
                'height': page.rect.height,
            }
            for index, page in enumerate(doc)
        ]
        return {
            'page_count': doc.page_count,
            'pages': pages,
            'font_available': bool(font_path),
            'font_error': None if font_path else FONT_ERROR,
        }
    finally:
        doc.close()


def error_response(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({'detail': message}, status=code)


def parse_hex_color(value):
    if not isinstance(value, str):
        value = DEFAULT_COLOR_HEX
    value = value.strip()
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        value = DEFAULT_COLOR_HEX
    return (
        int(value[1:3], 16) / 255,
        int(value[3:5], 16) / 255,
        int(value[5:7], 16) / 255,
    )


def safe_filename_part(value):
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]+', '_', str(value or '').strip())
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' .')
    return cleaned or '未命名'


def validate_items(doc, items, allow_empty_text=False, require_non_empty=True):
    if not isinstance(items, list) or not items:
        raise ValueError('请至少添加一条文字')

    normalized = []
    non_empty_count = 0
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('文字对象无效')
        text = str(item.get('text') or '').strip()
        if not text and not allow_empty_text:
            raise ValueError('文字内容不能为空')
        if text:
            non_empty_count += 1

        try:
            page_number = int(item.get('page'))
        except (TypeError, ValueError):
            raise ValueError('页码超出范围')
        if page_number < 1 or page_number > doc.page_count:
            raise ValueError('页码超出范围')

        page = doc[page_number - 1]
        try:
            x = float(item.get('x'))
            y = float(item.get('y'))
        except (TypeError, ValueError):
            raise ValueError('坐标无效')
        if x < 0 or y < 0 or x > page.rect.width or y > page.rect.height:
            raise ValueError('坐标超出页面范围')

        try:
            font_size = float(item.get('font_size') or TEXT_FONT_SIZE)
        except (TypeError, ValueError):
            font_size = TEXT_FONT_SIZE
        if font_size <= 0:
            font_size = TEXT_FONT_SIZE

        font_weight = str(item.get('font_weight') or DEFAULT_FONT_WEIGHT).strip().lower()
        if font_weight not in ('normal', 'bold'):
            font_weight = DEFAULT_FONT_WEIGHT

        color = str(item.get('color') or DEFAULT_COLOR_HEX).strip()
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            color = DEFAULT_COLOR_HEX

        font_family = str(item.get('font_family') or DEFAULT_FONT_FAMILY).strip()
        if font_family != DEFAULT_FONT_FAMILY:
            font_family = DEFAULT_FONT_FAMILY

        normalized.append({
            'id': item.get('id') or '',
            'page': page_number,
            'text': text,
            'x': x,
            'y': y,
            'font_size': font_size,
            'font_weight': font_weight,
            'color': color,
            'font_family': font_family,
        })
    if require_non_empty and non_empty_count == 0:
        raise ValueError('请至少填写一条文字')
    return normalized


def build_seifu_notice_pdf(items):
    font_path = find_adobe_heiti_font()
    if not font_path:
        raise ValueError(FONT_ERROR)

    doc = template_doc()
    try:
        normalized_items = validate_items(doc, items, allow_empty_text=True, require_non_empty=True)

        for item in normalized_items:
            if not item['text']:
                continue
            page = doc[item['page'] - 1]
            page.insert_font(fontname=PDF_FONT_NAME, fontfile=str(font_path))
            offsets = [(0, 0)]
            if item['font_weight'] == 'bold':
                offsets += [(0.35, 0), (0, 0.35)]
            for offset_x, offset_y in offsets:
                page.insert_text(
                    fitz.Point(item['x'] + offset_x, item['y'] + offset_y),
                    item['text'],
                    fontsize=item['font_size'],
                    fontname=PDF_FONT_NAME,
                    fontfile=str(font_path),
                    color=parse_hex_color(item['color']),
                    overlay=True,
                )

        output = BytesIO()
        doc.save(output, garbage=4, deflate=True, clean=True)
        output.seek(0)
        return output.getvalue()
    finally:
        doc.close()


def seifu_notice_pdf_response(items, title='添加文字'):
    pdf_bytes = build_seifu_notice_pdf(items)
    filename = f'清風合格通知書_{safe_filename_part(title)}_{datetime.now().strftime("%Y%m%d%H%M%S")}.pdf'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="seifu_notice.pdf"; filename*=UTF-8\'\'{quote(filename)}'
    )
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def seifu_notice_template(request):
    return Response(template_payload())


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def seifu_notice_preview(request):
    try:
        page_number = int(request.query_params.get('page', '1'))
    except ValueError:
        return error_response('页码超出范围')

    try:
        doc = template_doc()
    except FileNotFoundError as exc:
        return error_response(str(exc), status.HTTP_404_NOT_FOUND)

    try:
        if page_number < 1 or page_number > doc.page_count:
            return error_response('页码超出范围')
        page = doc[page_number - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        return HttpResponse(pix.tobytes('png'), content_type='image/png')
    finally:
        doc.close()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def seifu_notice_generate(request):
    try:
        return seifu_notice_pdf_response(request.data.get('items'), title='添加文字')
    except FileNotFoundError as exc:
        return error_response(str(exc), status.HTTP_404_NOT_FOUND)
    except ValueError as exc:
        return error_response(str(exc))

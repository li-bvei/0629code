from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


FONT_NAME = 'VoucherCJK'
FALLBACK_FONT_NAME = 'HeiseiKakuGo-W5'
DEFAULT_ISSUER = {
    'issuer_name': 'SUNRISE日晟鴻達株式会社',
    'issuer_postal_code': '5430043',
    'issuer_address': '大阪府大阪市天王寺区\n勝山４丁目７－３佐々木ビル２階',
    'issuer_tel': '06-7650-6385',
    'issuer_registration_number': 'T1120001256801',
}


def register_cjk_font():
    if FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return FONT_NAME

    candidates = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc',
        '/System/Library/Fonts/Hiragino Sans GB.ttc',
        '/Library/Fonts/Arial Unicode.ttf',
    ]

    for font_path in candidates:
        if Path(font_path).exists():
            try:
                pdfmetrics.registerFont(TTFont(FONT_NAME, font_path))
                return FONT_NAME
            except Exception:
                continue

    pdfmetrics.registerFont(UnicodeCIDFont(FALLBACK_FONT_NAME))
    return FALLBACK_FONT_NAME


def yen(value):
    return f'￥{int(value or 0):,}'


def plain_number(value):
    value = float(value or 0)
    if value.is_integer():
        return str(int(value))
    return f'{value:g}'


def draw_text(c, x, y, text, font_name, size=10):
    c.setFont(font_name, size)
    c.drawString(x, y, text or '')


def draw_right_text(c, x, y, text, font_name, size=10):
    c.setFont(font_name, size)
    c.drawRightString(x, y, text or '')


def draw_wrapped_lines(c, x, y, text, font_name, size=10, leading=15, max_chars=42):
    lines = []
    for raw_line in (text or '').splitlines() or ['']:
        line = raw_line.strip()
        if not line:
            lines.append('')
            continue
        while len(line) > max_chars:
            lines.append(line[:max_chars])
            line = line[max_chars:]
        lines.append(line)

    current_y = y
    for line in lines:
        draw_text(c, x, current_y, line, font_name, size)
        current_y -= leading
    return current_y


def issuer_value(voucher, field):
    value = getattr(voucher, field, '') or ''
    return str(value).strip() or DEFAULT_ISSUER[field]


def get_line_items(voucher):
    if voucher.line_items:
        return voucher.line_items

    detail_lines = [line.strip() for line in (voucher.details or voucher.title or '').splitlines() if line.strip()]
    if not detail_lines:
        detail_lines = [voucher.title or '-']
    if len(detail_lines) == 1:
        return [{
            'item_name': detail_lines[0],
            'quantity': 1,
            'unit_price': int(voucher.amount or 0),
            'line_total': int(voucher.amount or 0),
        }]

    return [
        {
            'item_name': line,
            'quantity': '',
            'unit_price': '',
            'line_total': '',
        }
        for line in detail_lines
    ]


def draw_section_label(c, x, y, label, font_name):
    c.setFillColor(colors.HexColor('#2f3a45'))
    draw_text(c, x, y, label, font_name, 10)
    c.setFillColor(colors.black)


def voucher_type_label(voucher):
    return '請求書' if voucher.voucher_type == 'invoice' else '領収書'


def clean_filename_part(value):
    for char in '/\\:*?"<>|':
        value = value.replace(char, '')
    return value.strip()


def build_voucher_pdf_filename(voucher):
    label = voucher_type_label(voucher)
    recipient_name = clean_filename_part(voucher.recipient_name or '')
    if recipient_name:
        return f'{recipient_name}様{label}.pdf'
    return f'{label}.pdf'


def build_content_disposition(filename):
    ascii_fallback = filename.encode('ascii', 'ignore').decode('ascii') or 'voucher.pdf'
    return f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{quote(filename)}'


def build_voucher_pdf(voucher):
    font_name = register_cjk_font()
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin_x = 20 * mm
    y = height - 20 * mm
    label = voucher_type_label(voucher)

    c.setTitle(label)
    c.setFillColor(colors.HexColor('#2f3a45'))
    draw_text(c, margin_x, y, label, font_name, 26)
    c.setFillColor(colors.black)
    draw_right_text(c, width - margin_x, y + 6, f'発行日：{voucher.issue_date:%Y-%m-%d}', font_name, 10)
    c.setStrokeColor(colors.HexColor('#aad4f4'))
    c.setLineWidth(1.2)
    c.line(margin_x, y - 10, width - margin_x, y - 10)

    y -= 24 * mm
    left_x = margin_x
    right_x = width - margin_x - 74 * mm
    draw_text(c, left_x, y, f'{voucher.recipient_name or ""} 御中'.strip(), font_name, 13)
    if voucher.recipient_postal_code:
        draw_text(c, left_x, y - 16, f'〒{voucher.recipient_postal_code}', font_name, 10)
    draw_wrapped_lines(c, left_x, y - 31, voucher.recipient_address, font_name, 10, max_chars=24)

    issuer_y = y + 8
    draw_text(c, right_x, issuer_y, issuer_value(voucher, 'issuer_name'), font_name, 10)
    issuer_y -= 15
    draw_text(c, right_x, issuer_y, f'〒{issuer_value(voucher, "issuer_postal_code")}', font_name, 9)
    issuer_y -= 13
    issuer_y = draw_wrapped_lines(c, right_x, issuer_y, issuer_value(voucher, 'issuer_address'), font_name, 9, max_chars=20)
    draw_text(c, right_x, issuer_y, f'TEL：{issuer_value(voucher, "issuer_tel")}', font_name, 9)
    issuer_y -= 13
    draw_text(c, right_x, issuer_y, f'登録番号：{issuer_value(voucher, "issuer_registration_number")}', font_name, 9)

    y -= 46 * mm
    amount_label = 'ご請求金額' if voucher.voucher_type == 'invoice' else '領収金額'
    c.setFillColor(colors.HexColor('#eef8ff'))
    c.roundRect(margin_x, y - 13, width - margin_x * 2, 31, 3 * mm, fill=1, stroke=0)
    c.setFillColor(colors.black)
    draw_text(c, margin_x + 10, y, amount_label, font_name, 13)
    draw_right_text(c, width - margin_x - 10, y, yen(voucher.total_amount), font_name, 21)

    y -= 19 * mm
    title_label = '件名' if voucher.voucher_type == 'invoice' else '但し書き'
    draw_section_label(c, margin_x, y, title_label, font_name)
    draw_text(c, margin_x + 34, y, voucher.title or '-', font_name, 11)

    y -= 14 * mm
    table_x = margin_x
    table_w = width - margin_x * 2
    col_item = 92 * mm
    col_qty = 22 * mm
    col_unit = 34 * mm
    col_total = table_w - col_item - col_qty - col_unit
    c.setStrokeColor(colors.HexColor('#d5e6f2'))
    c.setFillColor(colors.HexColor('#f4f9fd'))
    c.rect(table_x, y - 14, table_w, 18, fill=1, stroke=1)
    c.setFillColor(colors.black)
    draw_text(c, table_x + 7, y - 8, '項目', font_name, 10)
    draw_right_text(c, table_x + col_item + col_qty - 8, y - 8, '数量', font_name, 10)
    draw_right_text(c, table_x + col_item + col_qty + col_unit - 8, y - 8, '単価', font_name, 10)
    draw_right_text(c, table_x + table_w - 8, y - 8, '金額', font_name, 10)

    line_items = get_line_items(voucher)
    row_y = y - 32
    for item in line_items:
        if row_y < 65 * mm:
            c.showPage()
            row_y = height - 28 * mm
        c.setStrokeColor(colors.HexColor('#e4edf4'))
        c.rect(table_x, row_y - 5, table_w, 20, fill=0, stroke=1)
        draw_text(c, table_x + 7, row_y + 1, str(item.get('item_name') or '-'), font_name, 10)
        draw_right_text(c, table_x + col_item + col_qty - 8, row_y + 1, plain_number(item.get('quantity')), font_name, 10)
        draw_right_text(c, table_x + col_item + col_qty + col_unit - 8, row_y + 1, yen(item.get('unit_price')) if item.get('unit_price') != '' else '', font_name, 10)
        draw_right_text(c, table_x + table_w - 8, row_y + 1, yen(item.get('line_total')) if item.get('line_total') != '' else '', font_name, 10)
        row_y -= 20

    y = row_y - 10
    summary_label_x = table_x + table_w - 72 * mm
    summary_value_x = table_x + table_w - 8
    draw_right_text(c, summary_value_x, y, yen(voucher.amount), font_name, 10)
    draw_text(c, summary_label_x, y, '小計（税抜）', font_name, 10)
    y -= 15
    draw_right_text(c, summary_value_x, y, yen(voucher.tax_amount), font_name, 10)
    draw_text(c, summary_label_x, y, '消費税（10%）', font_name, 10)
    y -= 15
    c.setStrokeColor(colors.HexColor('#aad4f4'))
    c.line(summary_label_x, y + 10, summary_value_x, y + 10)
    draw_right_text(c, summary_value_x, y, yen(voucher.total_amount), font_name, 12)
    draw_text(c, summary_label_x, y, '合計（税込）', font_name, 11)

    y -= 24
    if voucher.voucher_type == 'invoice':
        if voucher.payment_due_date:
            draw_section_label(c, margin_x, y, '支払期限', font_name)
            draw_text(c, margin_x + 42, y, f'{voucher.payment_due_date:%Y-%m-%d}', font_name, 10)
            y -= 16
        if voucher.bank_info:
            draw_section_label(c, margin_x, y, 'お振込先', font_name)
            y -= 16
            y = draw_wrapped_lines(c, margin_x, y, voucher.bank_info, font_name, 10, max_chars=42)
    else:
        if voucher.payment_method:
            draw_section_label(c, margin_x, y, '支払方法', font_name)
            draw_text(c, margin_x + 42, y, voucher.payment_method, font_name, 10)
            y -= 16

    if voucher.note:
        y -= 10
        draw_section_label(c, margin_x, y, '備考', font_name)
        draw_wrapped_lines(c, margin_x + 34, y, voucher.note, font_name, 10, max_chars=46)

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def voucher_pdf_response(voucher):
    filename = build_voucher_pdf_filename(voucher)
    response = HttpResponse(build_voucher_pdf(voucher), content_type='application/pdf')
    response['Content-Disposition'] = build_content_disposition(filename)
    return response

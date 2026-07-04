from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


FONT_NAME = 'VoucherCJK'
MINCHO_FONT = 'YuMinchoProject'
MINCHO_BOLD_FONT = 'YuMinchoProjectBold'
FALLBACK_FONT_NAME = 'HeiseiKakuGo-W5'
FONT_DIR = Path(settings.BASE_DIR) / 'assets' / 'fonts'
YU_MINCHO = FONT_DIR / 'YuMincho.ttf'
YU_MINCHO_BOLD = FONT_DIR / 'YuMincho-Bold.ttf'
DEFAULT_ISSUER = {
    'issuer_name': 'SUNRISE日晟鴻達株式会社',
    'issuer_postal_code': '5430043',
    'issuer_address': '大阪府大阪市天王寺区勝山４丁目７－３\n佐々木ビル２階',
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


def register_mincho_font():
    registered_fonts = pdfmetrics.getRegisteredFontNames()
    if MINCHO_FONT in registered_fonts and MINCHO_BOLD_FONT in registered_fonts:
        return MINCHO_FONT

    if not YU_MINCHO.exists():
        raise FileNotFoundError(f'YuMincho.ttf is required: {YU_MINCHO}')

    if MINCHO_FONT not in registered_fonts:
        pdfmetrics.registerFont(TTFont(MINCHO_FONT, str(YU_MINCHO)))

    bold_path = YU_MINCHO_BOLD if YU_MINCHO_BOLD.exists() else YU_MINCHO
    if MINCHO_BOLD_FONT not in registered_fonts:
        pdfmetrics.registerFont(TTFont(MINCHO_BOLD_FONT, str(bold_path)))
    return MINCHO_FONT


def yen(value):
    return f'￥{int(value or 0):,}'


def japanese_date(value):
    if not value:
        return ''
    return f'{value.year}年{value.month}月{value.day}日'


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


def draw_center_text(c, x, y, text, font_name, size=10):
    c.setFont(font_name, size)
    c.drawCentredString(x, y, text or '')


def draw_bold_text(c, x, y, text, font_name, size=10):
    bold_font = MINCHO_BOLD_FONT if MINCHO_BOLD_FONT in pdfmetrics.getRegisteredFontNames() else font_name
    c.setFont(bold_font, size)
    c.drawString(x, y, text or '')


def draw_bold_right_text(c, x, y, text, font_name, size=10):
    bold_font = MINCHO_BOLD_FONT if MINCHO_BOLD_FONT in pdfmetrics.getRegisteredFontNames() else font_name
    c.setFont(bold_font, size)
    c.drawRightString(x, y, text or '')


def draw_bold_center_text(c, x, y, text, font_name, size=10):
    bold_font = MINCHO_BOLD_FONT if MINCHO_BOLD_FONT in pdfmetrics.getRegisteredFontNames() else font_name
    c.setFont(bold_font, size)
    c.drawCentredString(x, y, text or '')


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


def split_text_by_width(text, font_name, size, max_width):
    text = str(text or '')
    if not text:
        return ['']

    lines = []
    for raw_line in text.splitlines() or ['']:
        current = ''
        for char in raw_line:
            candidate = current + char
            if current and pdfmetrics.stringWidth(candidate, font_name, size) > max_width:
                lines.append(current)
                current = char
            else:
                current = candidate
        lines.append(current)
    return lines


def draw_wrapped_cell_text(c, x, y, width, height, text, font_name, size, align='left', bold=False):
    actual_font = MINCHO_BOLD_FONT if bold and MINCHO_BOLD_FONT in pdfmetrics.getRegisteredFontNames() else font_name
    lines = split_text_by_width(text, actual_font, size, max(width - 10, 8))
    leading = size + 3
    max_lines = max(1, int((height - 6) // leading) + 1)
    visible_lines = lines[:max_lines]
    start_y = y - 6 - size

    c.setFont(actual_font, size)
    for index, line in enumerate(visible_lines):
        line_y = start_y - index * leading
        if align == 'right':
            c.drawRightString(x + width - 5, line_y, line)
        elif align == 'center':
            c.drawCentredString(x + width / 2, line_y, line)
        else:
            c.drawString(x + 5, line_y, line)


def issuer_value(voucher, field):
    value = getattr(voucher, field, '') or ''
    return str(value).strip() or DEFAULT_ISSUER[field]


def issuer_lines(voucher):
    lines = [
        issuer_value(voucher, 'issuer_name'),
        f'〒{issuer_value(voucher, "issuer_postal_code")}',
    ]
    lines.extend([line for line in issuer_value(voucher, 'issuer_address').splitlines() if line])
    lines.extend([
        f'TEL：{issuer_value(voucher, "issuer_tel")}',
        f'登録番号：{issuer_value(voucher, "issuer_registration_number")}',
    ])
    return lines


def recipient_with_honorific(voucher):
    name = (voucher.recipient_name or '').strip()
    return f'{name}　　　　御中' if name else '御中'


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


def get_line_total(item):
    if item.get('line_total') not in (None, ''):
        return int(float(item.get('line_total') or 0))
    return int(float(item.get('quantity') or 0) * float(item.get('unit_price') or 0))


def get_line_item_name(item):
    return str(
        item.get('item_name')
        or item.get('name')
        or item.get('description')
        or '-'
    )


def get_line_item_note(item):
    return str(item.get('note') or item.get('remarks') or '')


def parse_bank_info(bank_info):
    lines = [line.strip() for line in (bank_info or '').splitlines() if line.strip()]
    result = {
        'bank_name': '',
        'branch_name': '',
        'account_number': '',
        'recipient_name': '',
        'recipient_address': DEFAULT_ISSUER['issuer_address'],
        'raw': '\n'.join(lines),
    }
    if not lines:
        return result

    if len(lines) >= 1:
        first_line_parts = [part.strip() for part in lines[0].replace('　', ' ').split() if part.strip()]
        if len(first_line_parts) >= 2:
            result['bank_name'] = first_line_parts[0]
            result['branch_name'] = ' '.join(first_line_parts[1:])
        else:
            result['bank_name'] = lines[0]

    if len(lines) >= 2:
        second_line_parts = [part.strip() for part in lines[1].replace('　', ' ').split() if part.strip()]
        result['account_number'] = ' '.join(second_line_parts) if second_line_parts else lines[1]

    for line in lines[2:]:
        if '口座名義' in line:
            result['recipient_name'] = line.replace('口座名義', '').strip(' ：:　')
        elif '受取人' in line:
            result['recipient_name'] = line.replace('受取人名', '').replace('受取人', '').strip(' ：:　')
        elif '住所' in line:
            result['recipient_address'] = line.replace('受取人住所', '').replace('住所', '').strip(' ：:　')

    if not any(result[key] for key in ('bank_name', 'branch_name', 'account_number', 'recipient_name')):
        result['bank_name'] = result['raw']

    return result


def draw_table(c, x, y, col_widths, row_heights, rows, font_name, font_size=10):
    current_y = y
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)

    for row_index, row in enumerate(rows):
        row_h = row_heights[row_index] if isinstance(row_heights, list) else row_heights
        current_x = x
        col_index = 0
        cell_index = 0
        while col_index < len(col_widths) and cell_index < len(row):
            cell = row[cell_index]
            span = cell.get('span', 1) if isinstance(cell, dict) else 1
            span = max(1, int(span or 1))
            col_w = sum(col_widths[col_index:col_index + span])
            fill_color = cell.get('fill') if isinstance(cell, dict) else None
            draw_border = cell.get('border', True) if isinstance(cell, dict) else True

            if fill_color:
                c.setFillColor(fill_color)
                c.rect(current_x, current_y - row_h, col_w, row_h, fill=1, stroke=0)
                c.setFillColor(colors.black)
            if draw_border:
                c.rect(current_x, current_y - row_h, col_w, row_h, fill=0, stroke=1)

            text = cell.get('text', '') if isinstance(cell, dict) else str(cell or '')
            align = cell.get('align', 'left') if isinstance(cell, dict) else 'left'
            size = cell.get('size', font_size) if isinstance(cell, dict) else font_size
            bold = cell.get('bold', False) if isinstance(cell, dict) else False

            draw_wrapped_cell_text(c, current_x, current_y, col_w, row_h, text, font_name, size, align, bold)
            current_x += col_w
            col_index += span
            cell_index += 1
        current_y -= row_h

    return current_y


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


def build_invoice_pdf(voucher):
    font_name = register_mincho_font()
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin_x = 20 * mm
    content_w = width - margin_x * 2
    top_y = height - 18 * mm

    c.setTitle('請求書')
    c.setFillColor(colors.black)

    recipient = recipient_with_honorific(voucher)
    recipient_y = top_y - 9 * mm
    draw_text(c, margin_x, recipient_y, recipient, font_name, 12)
    underline_w = min(78 * mm, max(48 * mm, pdfmetrics.stringWidth(recipient, font_name, 12) + 10))
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    c.line(margin_x, recipient_y - 4, margin_x + underline_w, recipient_y - 4)

    issuer_right_x = width - 8 * mm
    issuer_block_w = 72 * mm
    issuer_x = issuer_right_x - issuer_block_w
    issuer_y = top_y
    draw_right_text(c, issuer_right_x, issuer_y, f'発行日：{japanese_date(voucher.issue_date)}', font_name, 9)
    issuer_y -= 24
    for line in issuer_lines(voucher):
        draw_text(c, issuer_x, issuer_y, line, font_name, 9)
        issuer_y -= 12

    y = height - 58 * mm
    draw_bold_center_text(c, width / 2, y, '請　求　書', font_name, 22)

    y -= 14 * mm
    greeting = '拝啓　益々ご清祥のこととお慶び申し上げます。下記の通り、ご請求申し上げます。'
    draw_text(c, margin_x, y, greeting, font_name, 11)

    y -= 9 * mm
    draw_bold_center_text(c, width / 2, y, '記', font_name, 12)

    y -= 8 * mm
    draw_bold_text(c, margin_x, y, '【請求金額等】', font_name, 12)
    y -= 5 * mm

    payment_due = japanese_date(voucher.payment_due_date)
    amount_rows = [
        [{'text': '納付期日', 'align': 'right'}, {'text': payment_due, 'align': 'center'}],
        [{'text': '請求金額合計', 'align': 'right'}, {'text': yen(voucher.total_amount), 'align': 'center', 'bold': True}],
    ]
    y = draw_table(
        c,
        margin_x,
        y,
        [42 * mm, content_w - 42 * mm],
        8 * mm,
        amount_rows,
        font_name,
        font_size=11,
    )

    y -= 7 * mm
    draw_bold_text(c, margin_x, y, '（内訳）', font_name, 10)
    y -= 5 * mm

    line_items = get_line_items(voucher)
    item_texts = ['適用'] + [str(item.get('item_name') or '') for item in line_items]
    longest_item_width = max(
        [pdfmetrics.stringWidth(text, font_name, 10) for text in item_texts] or [0]
    )
    item_padding = pdfmetrics.stringWidth('ああああ', font_name, 10) + 10
    unit_w = 22 * mm
    qty_w = 14 * mm
    amount_w = 26 * mm
    min_note_w = 26 * mm
    max_item_w = content_w - unit_w - qty_w - amount_w - min_note_w
    item_w = min(max_item_w, max(58 * mm, longest_item_width + item_padding))
    note_w = content_w - item_w - unit_w - qty_w - amount_w
    col_widths = [item_w, unit_w, qty_w, amount_w, note_w]
    detail_rows = [[
        {'text': '適用', 'align': 'center', 'bold': True},
        {'text': '単価', 'align': 'center', 'bold': True},
        {'text': '数量', 'align': 'center', 'bold': True},
        {'text': '金額', 'align': 'center', 'bold': True},
        {'text': '備考', 'align': 'center', 'bold': True},
    ]]

    for item in line_items:
        detail_rows.append([
            {'text': str(item.get('item_name') or ''), 'align': 'left'},
            {'text': yen(item.get('unit_price')) if item.get('unit_price') not in (None, '') else '', 'align': 'right'},
            {'text': plain_number(item.get('quantity')), 'align': 'center'},
            {'text': yen(get_line_total(item)) if item.get('item_name') or item.get('line_total') not in (None, '') else '', 'align': 'right'},
            {'text': '', 'align': 'left'},
        ])

    while len(detail_rows) < 6:
        detail_rows.append([
            {'text': ''},
            {'text': ''},
            {'text': ''},
            {'text': ''},
            {'text': ''},
        ])

    detail_rows.extend([
        [
            {'text': '', 'span': 3, 'border': False},
            {'text': '小計', 'align': 'right', 'size': 8},
            {'text': yen(voucher.amount), 'align': 'right', 'size': 8},
        ],
        [
            {'text': '', 'span': 3, 'border': False},
            {'text': '消費税', 'align': 'right', 'size': 8},
            {'text': yen(voucher.tax_amount), 'align': 'right', 'size': 8},
        ],
        [
            {'text': '', 'span': 3, 'border': False},
            {'text': '合計', 'align': 'right', 'bold': True, 'size': 8},
            {'text': yen(voucher.total_amount), 'align': 'right', 'bold': True, 'size': 8},
        ],
    ])

    summary_start_index = len(detail_rows) - 3
    row_heights = [
        8 * mm if index == 0 else 6.2 * mm if index >= summary_start_index else 8.8 * mm
        for index in range(len(detail_rows))
    ]
    y = draw_table(c, margin_x, y, col_widths, row_heights, detail_rows, font_name, font_size=10)

    y -= 11 * mm
    draw_bold_text(c, margin_x, y, '【支払い銀行】', font_name, 12)
    y -= 5 * mm
    bank = parse_bank_info(voucher.bank_info)
    bank_rows = [
        [{'text': '銀行名'}, {'text': bank['bank_name'] or bank['raw']}],
        [{'text': '銀行支店名'}, {'text': bank['branch_name']}],
        [{'text': '口座番号'}, {'text': bank['account_number']}],
        [{'text': '受取人名（口座名）'}, {'text': bank['recipient_name']}],
        [{'text': '受取人住所'}, {'text': bank['recipient_address']}],
    ]
    y = draw_table(
        c,
        margin_x,
        y,
        [52 * mm, content_w - 52 * mm],
        [7.5 * mm, 7.5 * mm, 7.5 * mm, 7.5 * mm, 12 * mm],
        bank_rows,
        font_name,
        font_size=10,
    )

    y -= 7 * mm
    draw_text(c, margin_x, y, '※振込み手数料は振込み人負担とします。', font_name, 11)
    y -= 5 * mm
    draw_right_text(c, width - margin_x, y, '以上', font_name, 12)

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def build_receipt_pdf(voucher):
    font_name = register_mincho_font()
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin_x = 20 * mm
    content_w = width - margin_x * 2
    y = height - 24 * mm

    c.setTitle('領収書')
    c.setFillColor(colors.black)
    draw_bold_center_text(c, width / 2, y, '領　収　書', font_name, 20)

    y -= 18 * mm
    receipt_issuer_right_x = width - 8 * mm
    draw_right_text(c, receipt_issuer_right_x, y, f'発行日：{japanese_date(voucher.issue_date)}', font_name, 10)

    y -= 13 * mm
    recipient_text = recipient_with_honorific(voucher)
    recipient_x = margin_x
    recipient_y = y
    draw_text(c, recipient_x, recipient_y, recipient_text, font_name, 13)
    underline_w = min(78 * mm, max(48 * mm, pdfmetrics.stringWidth(recipient_text, font_name, 13) + 10))
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    c.line(recipient_x, recipient_y - 4, recipient_x + underline_w, recipient_y - 4)

    issuer_x = receipt_issuer_right_x - 72 * mm
    issuer_y = y + 8
    for line in issuer_lines(voucher):
        draw_text(c, issuer_x, issuer_y, line, font_name, 9)
        issuer_y -= 12

    y -= 36 * mm
    draw_text(c, margin_x, y, '下記、正に領収いたしました。', font_name, 11)

    header_fill = colors.HexColor('#f0f0f0')
    y -= 12 * mm
    total_box_w = content_w * 0.68
    total_box_x = margin_x
    total_rows = [[
        {'text': '合計金額', 'align': 'center', 'bold': True, 'fill': header_fill, 'size': 12},
        {'text': f'{yen(voucher.total_amount)}（税込）', 'align': 'center', 'bold': True, 'fill': header_fill, 'size': 15},
    ]]
    y = draw_table(
        c,
        total_box_x,
        y,
        [total_box_w * 0.36, total_box_w * 0.64],
        12 * mm,
        total_rows,
        font_name,
        font_size=12,
    )

    y -= 8 * mm
    receipt_rows = [[
        {'text': '品　名', 'align': 'center', 'bold': True, 'fill': header_fill},
        {'text': '金額', 'align': 'center', 'bold': True, 'fill': header_fill},
        {'text': '摘　要', 'align': 'center', 'bold': True, 'fill': header_fill},
    ]]

    line_items = get_line_items(voucher)
    for item in line_items:
        receipt_rows.append([
            {'text': get_line_item_name(item), 'align': 'left'},
            {'text': yen(get_line_total(item)), 'align': 'right'},
            {'text': get_line_item_note(item), 'align': 'left'},
        ])

    while len(receipt_rows) < 5:
        receipt_rows.append([
            {'text': ''},
            {'text': ''},
            {'text': ''},
        ])

    receipt_rows.extend([
        [
            {'text': '', 'border': False},
            {'text': '小計', 'align': 'right', 'size': 8},
            {'text': yen(voucher.amount), 'align': 'right', 'size': 8},
        ],
        [
            {'text': '', 'border': False},
            {'text': '消費税', 'align': 'right', 'size': 8},
            {'text': yen(voucher.tax_amount), 'align': 'right', 'size': 8},
        ],
        [
            {'text': '', 'border': False},
            {'text': '合計', 'align': 'right', 'bold': True, 'size': 8},
            {'text': yen(voucher.total_amount), 'align': 'right', 'bold': True, 'size': 8},
        ],
    ])

    receipt_col_widths = [content_w * 0.52, content_w * 0.22, content_w * 0.26]
    receipt_summary_start = len(receipt_rows) - 3
    receipt_row_heights = [
        9 * mm if index == 0 else 6.2 * mm if index >= receipt_summary_start else 10 * mm
        for index in range(len(receipt_rows))
    ]
    y = draw_table(c, margin_x, y, receipt_col_widths, receipt_row_heights, receipt_rows, font_name, font_size=10)

    stamp_w = 21.5 * mm
    stamp_h = 25.5 * mm
    stamp_top_y = y + sum(receipt_row_heights[receipt_summary_start:])
    stamp_y = stamp_top_y - stamp_h
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    c.rect(margin_x, stamp_y, stamp_w, stamp_h, fill=0, stroke=1)
    draw_center_text(c, margin_x + stamp_w / 2, stamp_y + stamp_h / 2 - 3, '収入印紙', font_name, 8)

    y = stamp_y - 10 * mm
    note_rows = [
        [{'text': '備考', 'align': 'center', 'bold': True, 'fill': header_fill}],
        [{'text': voucher.note or '', 'align': 'left'}],
    ]
    y = draw_table(
        c,
        margin_x,
        y,
        [content_w],
        [8 * mm, 18 * mm],
        note_rows,
        font_name,
        font_size=10,
    )

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def build_voucher_pdf(voucher):
    if voucher.voucher_type == 'invoice':
        return build_invoice_pdf(voucher)
    return build_receipt_pdf(voucher)


def voucher_pdf_response(voucher):
    filename = build_voucher_pdf_filename(voucher)
    response = HttpResponse(build_voucher_pdf(voucher), content_type='application/pdf')
    response['Content-Disposition'] = build_content_disposition(filename)
    return response

import io
import json
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

import fitz
from django.conf import settings
from django.http import HttpResponse


TEMPLATE_DIR = Path(settings.BASE_DIR) / 'assets' / 'pdf_templates' / 'visa_return'
POSITIONS_PATH = TEMPLATE_DIR / 'field_positions.json'
VISA_1_PATH = TEMPLATE_DIR / 'visa_1.pdf'
VISA_2_PATH = TEMPLATE_DIR / 'visa_2.pdf'
FONT_PATH = Path(settings.BASE_DIR) / 'assets' / 'fonts' / 'YuMincho.ttf'
FONT_NAME = 'YuMincho'


CHECKED_VALUES = {'checked', 'true', '1', 'yes', 'on'}


def load_positions():
    with POSITIONS_PATH.open('r', encoding='utf-8') as file:
        return json.load(file)


def format_date(value):
    if not value:
        return ''
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime('%d/%m/%Y')
    if isinstance(value, str):
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d'):
            try:
                return datetime.strptime(value, fmt).strftime('%d/%m/%Y')
            except ValueError:
                continue
    return str(value)


def get_form_data(application):
    return application.form_data if isinstance(application.form_data, dict) else {}


def get_snapshot(application):
    return application.guarantor_snapshot if isinstance(application.guarantor_snapshot, dict) else {}


def first_value(*values, default=''):
    for value in values:
        if value not in (None, ''):
            return value
    return default


def field_value(application, name, attr=None, default=''):
    form_data = get_form_data(application)
    if name in form_data and form_data[name] not in (None, ''):
        return form_data[name]
    if attr:
        return first_value(getattr(application, attr, ''), default=default)
    return default


def snapshot_value(application, name, *fallbacks, default=''):
    form_data = get_form_data(application)
    snapshot = get_snapshot(application)
    if name in form_data and form_data[name] not in (None, ''):
        return form_data[name]
    return first_value(*fallbacks, snapshot.get(name), default=default)


def checked_if(value):
    return 'checked' if value else ''


def is_checked(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if value is None:
        return False
    return str(value).strip().lower() in CHECKED_VALUES


def data_or_default(data, field_name, config):
    if field_name in data:
        return data[field_name]
    return config.get('default', '')


def build_visa_page1_data(application):
    form_data = get_form_data(application)
    gender = first_value(form_data.get('gender'), getattr(application, 'gender', ''))
    marital_status = first_value(form_data.get('marital_status'), getattr(application, 'marital_status', ''))

    return {
        'pinyin_name1': field_value(application, 'pinyin_name1'),
        'pinyin_name2': field_value(application, 'pinyin_name2'),
        'chinese_name1': field_value(application, 'chinese_name1'),
        'chinese_name2': field_value(application, 'chinese_name2'),
        'used_name1': field_value(application, 'used_name1'),
        'used_name2': field_value(application, 'used_name2'),
        'nationality': field_value(application, 'nationality', 'nationality'),
        'orthernationality': field_value(application, 'orthernationality', default='无'),
        'birth_date': format_date(first_value(getattr(application, 'birth_date', ''), form_data.get('birth_date'))),
        'birth_place': field_value(application, 'birth_place'),
        'xx': checked_if(gender == 'male'),
        'xy': checked_if(gender == 'female'),
        'marry1': checked_if(marital_status == 'single'),
        'marry2': checked_if(marital_status == 'married'),
        'marry3': checked_if(marital_status == 'divorced'),
        'marry4': checked_if(marital_status == 'widowed'),
        'chinese_id': field_value(application, 'chinese_id'),
        'passport_type': form_data.get('passport_type', 'checked'),
        'passport_id': field_value(application, 'passport_id', 'passport_number'),
        'passport_address': field_value(application, 'passport_address'),
        'passport_date1': format_date(first_value(form_data.get('passport_date1'), getattr(application, 'passport_issue_date', ''))),
        'passport_a': field_value(application, 'passport_a'),
        'zailiu_number': field_value(application, 'zailiu_number'),
        'zailiu_type': field_value(application, 'zailiu_type', 'residence_status'),
        'passport_date2': format_date(first_value(form_data.get('passport_date2'), getattr(application, 'passport_expiry_date', ''))),
        'entry_port': field_value(application, 'entry_port'),
        'entry_time1': field_value(application, 'entry_time1'),
        'entry_time2': field_value(application, 'entry_time2'),
        'entry_time3': field_value(application, 'entry_time3'),
        'airline': field_value(application, 'airline'),
        'home_address1': field_value(application, 'home_address1'),
        'home_address2': field_value(application, 'home_address2', 'address'),
        'home_phone': field_value(application, 'home_phone'),
        'mobile_phone': field_value(application, 'mobile_phone', 'phone'),
        'email': field_value(application, 'email', 'email'),
        'workplace_name': field_value(application, 'workplace_name'),
        'workplace_address': field_value(application, 'workplace_address'),
        'workplace_phone': field_value(application, 'workplace_phone'),
        'job_title': field_value(application, 'job_title', 'occupation'),
        'hotel': field_value(application, 'hotel'),
        'hotel_phone': field_value(application, 'hotel_phone'),
        'hotel_address': field_value(application, 'hotel_address'),
        'last': field_value(application, 'last'),
    }


def build_visa_page2_data(application):
    form_data = get_form_data(application)
    gender = form_data.get('gender2')

    data = {
        'job_title2': field_value(application, 'job_title2'),
        'guarantor_name_en': snapshot_value(application, 'guarantor_name_en'),
        'guarantor_name_jp': snapshot_value(application, 'guarantor_name_jp', getattr(application, 'guarantor_name', '')),
        'guarantor_phone': snapshot_value(application, 'guarantor_phone', getattr(application, 'guarantor_phone', '')),
        'guarantor_address_en': snapshot_value(application, 'guarantor_address_en'),
        'guarantor_address_jp': snapshot_value(application, 'guarantor_address_jp', getattr(application, 'guarantor_address', '')),
        'guarantor_birth_date': format_date(snapshot_value(application, 'guarantor_birth_date')),
        'relation_to_applicant': snapshot_value(
            application,
            'relation_to_applicant',
            getattr(application, 'guarantor_relationship', ''),
        ),
        'guarantor_job': snapshot_value(application, 'guarantor_job', getattr(application, 'guarantor_occupation', '')),
        'guarantor_nationality': snapshot_value(application, 'guarantor_nationality'),
        'same': field_value(application, 'same', default='同上'),
        'xx': checked_if(gender == 'male'),
        'xy': checked_if(gender == 'female'),
    }
    for field_name in ('x1', 'x2', 'x3', 'x4', 'x5', 'x6'):
        if field_name in form_data:
            data[field_name] = form_data[field_name]
    return data


def to_fitz_point(page, x, y):
    return fitz.Point(float(x), page.rect.height - float(y))


def draw_checkbox(page, x, y, size=7, mark='x'):
    size = float(size)
    point = to_fitz_point(page, x, y)
    x0 = point.x
    y0 = point.y - size
    x1 = point.x + size
    y1 = point.y

    if mark in ('x', 'check'):
        page.draw_line((x0, y0), (x1, y1), width=0.8, color=(0, 0, 0))
        page.draw_line((x0, y1), (x1, y0), width=0.8, color=(0, 0, 0))
    elif mark == 'circle':
        page.draw_oval(fitz.Rect(x0, y0, x1, y1), width=0.8, color=(0, 0, 0))


def insert_text(page, x, y, text, font_size=10):
    text = str(text or '')
    if not text:
        return
    page.insert_text(
        to_fitz_point(page, x, y),
        text,
        fontsize=float(font_size or 10),
        fontname=FONT_NAME,
        fontfile=str(FONT_PATH),
        color=(0, 0, 0),
    )


def fill_pdf_template(template_path, positions, data):
    if not FONT_PATH.exists():
        raise FileNotFoundError(f'YuMincho.ttf is required: {FONT_PATH}')

    doc = fitz.open(str(template_path))
    page = doc[0]
    page.insert_font(fontname=FONT_NAME, fontfile=str(FONT_PATH))

    for field_name, config in positions.items():
        field_type = config.get('type', 'text')
        value = data_or_default(data, field_name, config)
        if field_type == 'checkbox':
            if is_checked(value):
                draw_checkbox(
                    page,
                    config.get('x', 0),
                    config.get('y', 0),
                    size=config.get('size', 7),
                    mark=config.get('mark', 'x'),
                )
            continue

        insert_text(
            page,
            config.get('x', 0),
            config.get('y', 0),
            value,
            font_size=config.get('font_size', 10),
        )

    output = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return output


def merge_pdfs(visa_1_bytes, visa_2_bytes):
    combined = fitz.open()
    doc1 = fitz.open(stream=visa_1_bytes, filetype='pdf')
    doc2 = fitz.open(stream=visa_2_bytes, filetype='pdf')
    combined.insert_pdf(doc1)
    combined.insert_pdf(doc2)

    output = io.BytesIO()
    combined.save(output, garbage=4, deflate=True)

    doc1.close()
    doc2.close()
    combined.close()
    output.seek(0)
    return output.getvalue()


def generate_visa_return_pdf(application):
    positions = load_positions()
    page1_data = build_visa_page1_data(application)
    page2_data = build_visa_page2_data(application)
    visa_1_bytes = fill_pdf_template(VISA_1_PATH, positions['visa_1'], page1_data)
    visa_2_bytes = fill_pdf_template(VISA_2_PATH, positions['visa_2'], page2_data)
    return merge_pdfs(visa_1_bytes, visa_2_bytes)


def build_visa_return_pdf_filename(application):
    name = (application.applicant_name or get_form_data(application).get('pinyin_name1') or '申請人').strip()
    today = datetime.now().strftime('%Y%m%d')
    return f'返签visa表_{name}_{today}.pdf'


def visa_return_pdf_response(application):
    filename = build_visa_return_pdf_filename(application)
    response = HttpResponse(generate_visa_return_pdf(application), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="visa_return.pdf"; filename*=UTF-8\'\'{quote(filename)}'
    )
    return response

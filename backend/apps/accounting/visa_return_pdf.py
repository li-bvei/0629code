import io
import json
import logging
import re
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
VISA_FORM_TEMPLATE_PATH = TEMPLATE_DIR / 'visa_tem.pdf'
FORM_FIELD_MAPPING_PATH = TEMPLATE_DIR / 'form_field_mapping.json'
FONT_CANDIDATES = [
    Path(settings.BASE_DIR) / 'assets' / 'fonts' / 'dengxian.ttf',
    Path(settings.BASE_DIR) / 'assets' / 'fonts' / 'NotoSansCJK-Regular.ttc',
    Path(settings.BASE_DIR) / 'assets' / 'fonts' / 'SourceHanSans-Regular.otf',
    Path(settings.BASE_DIR) / 'assets' / 'fonts' / 'NotoSansCJKjp-Regular.otf',
    Path(settings.BASE_DIR) / 'assets' / 'fonts' / 'YuMincho.ttf',
]
FONT_PATH = next((path for path in FONT_CANDIDATES if path.exists()), FONT_CANDIDATES[-1])
FONT_NAME = 'VisaReturnFont'


CHECKED_VALUES = {'checked', 'true', '1', 'yes', 'on'}
logger = logging.getLogger(__name__)
PARENT_XREF_RE = re.compile(r'/Parent\s+(\d+)\s+0\s+R')

if FONT_PATH.name == 'YuMincho.ttf':
    logger.warning('Using YuMincho.ttf for visa PDF. Some simplified Chinese glyphs may be missing.')


def format_home_address(data):
    registered = str(data.get('registered_address') or '').strip()
    current = str(data.get('current_address') or data.get('home_address2') or '').strip()

    if registered and current:
        return f'户籍地址：{registered}\n现住址：{current}'
    if registered:
        return f'户籍地址：{registered}'
    if current:
        return current
    return ''


def load_positions():
    with POSITIONS_PATH.open('r', encoding='utf-8') as file:
        return json.load(file)


def load_form_field_mapping():
    with FORM_FIELD_MAPPING_PATH.open('r', encoding='utf-8') as file:
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


def get_form_application_variables(application):
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
    variables['home_address2'] = format_home_address(variables)
    guarantor_nationality = first_value(variables.get('guarantor_nationality'), default='')
    guarantor_visa_status = first_value(variables.get('guarantor_visa_status'), default='')
    if guarantor_nationality and guarantor_visa_status:
        variables['guarantor_nationality'] = f'{guarantor_nationality} / {guarantor_visa_status}'
    return variables


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


def mapped_form_value(value, config):
    if config.get('format'):
        return format_date(value)
    if isinstance(value, (datetime, date)):
        return format_date(value)
    if value is None:
        return ''
    return str(value)


def set_pdf_field_value(doc, field_name, value, update_all=False):
    found = False
    failed = False
    for page in doc:
        widgets = page.widgets()
        if not widgets:
            continue
        for widget in widgets:
            if widget.field_name != field_name:
                continue
            try:
                widget.field_value = value
                widget.update()
                found = True
            except Exception as exc:
                logger.warning('Failed to update visa PDF field %s: %s', field_name, exc)
                found = True
                failed = True
            if not update_all:
                return found and not failed
    return found and not failed


def is_choice_widget(widget):
    field_type = (widget.field_type_string or '').lower()
    return 'combo' in field_type or 'list' in field_type


def is_button_widget(widget):
    field_type = (widget.field_type_string or '').lower()
    return 'radio' in field_type or 'check' in field_type


def widget_on_values(widget):
    try:
        states = widget.button_states() or {}
    except Exception:
        return []
    values = []
    for state_values in states.values():
        if isinstance(state_values, (list, tuple, set)):
            values.extend(str(value) for value in state_values if value not in (None, 'Off'))
        elif state_values not in (None, 'Off'):
            values.append(str(state_values))
    return values


def set_pdf_radio_group_value(doc, field_name, selected_value):
    selected_value = str(selected_value)
    found = False
    parent_xrefs = set()
    for page in doc:
        widgets = page.widgets()
        if not widgets:
            continue
        for widget in widgets:
            if widget.field_name != field_name:
                continue
            found = True
            on_values = widget_on_values(widget)
            next_value = selected_value if selected_value in on_values else 'Off'
            try:
                doc.xref_set_key(widget.xref, 'AS', f'/{next_value}')
                parent_match = PARENT_XREF_RE.search(doc.xref_object(widget.xref, compressed=False))
                if parent_match:
                    parent_xrefs.add(int(parent_match.group(1)))
            except Exception as exc:
                logger.warning('Failed to update visa PDF radio field %s: %s', field_name, exc)
    for parent_xref in parent_xrefs:
        try:
            doc.xref_set_key(parent_xref, 'V', f'/{selected_value}')
        except Exception as exc:
            logger.warning('Failed to update visa PDF radio parent %s: %s', field_name, exc)
    return found


def fill_text_mapping(doc, pdf_field, value):
    return set_pdf_field_value(doc, pdf_field, value)


def fill_checkbox_mapping(doc, pdf_field, checked, checked_value='Yes', unchecked_value='Off'):
    value = checked_value if checked else (unchecked_value or 'Off')
    return set_pdf_field_value(doc, pdf_field, value)


def fill_choice_mapping(doc, field_name, selected_value):
    return set_pdf_radio_group_value(doc, field_name, selected_value)


def draw_flattened_text(page, rect, value):
    text = str(value or '')
    if not text:
        return
    font_size = max(6, min(10, rect.height * 0.72))
    point = fitz.Point(rect.x0 + 2, rect.y1 - max(2, rect.height * 0.2))
    try:
        page.insert_text(
            point,
            text,
            fontsize=font_size,
            fontname=FONT_NAME,
            fontfile=str(FONT_PATH),
            color=(0, 0, 0),
        )
    except Exception:
        page.insert_textbox(
            fitz.Rect(rect.x0 + 2, rect.y0 + 1, rect.x1 - 1, rect.y1 - 1),
            text,
            fontsize=font_size,
            fontname=FONT_NAME,
            fontfile=str(FONT_PATH),
            color=(0, 0, 0),
        )


def draw_flattened_button(page, rect):
    inset = max(1, min(rect.width, rect.height) * 0.2)
    x0 = rect.x0 + inset
    y0 = rect.y0 + inset
    x1 = rect.x1 - inset
    y1 = rect.y1 - inset
    page.draw_line((x0, y0), (x1, y1), width=0.8, color=(0, 0, 0))
    page.draw_line((x0, y1), (x1, y0), width=0.8, color=(0, 0, 0))


def draw_value_on_field(doc, field_name, value):
    text = str(value or '')
    if not text:
        return False
    for page in doc:
        widgets = page.widgets()
        if not widgets:
            continue
        for widget in widgets:
            if widget.field_name == field_name:
                draw_flattened_text(page, widget.rect, text)
                return True
    return False


def flatten_form_fields(doc):
    flattened = 0
    for page in doc:
        widgets = list(page.widgets() or [])
        if not widgets:
            continue

        for widget in widgets:
            value = widget.field_value
            try:
                widget.update()
            except Exception:
                pass

            if is_button_widget(widget):
                if value and value != 'Off':
                    draw_flattened_button(page, widget.rect)
                    flattened += 1
            elif value not in (None, ''):
                draw_flattened_text(page, widget.rect, value)
                flattened += 1

        for widget in list(page.widgets() or []):
            try:
                page.delete_widget(widget)
            except Exception as exc:
                logger.warning('Failed to remove visa PDF form field %s: %s', widget.field_name, exc)

    return flattened


def save_pdf_bytes(doc, clean=False):
    output = io.BytesIO()
    doc.save(output, garbage=4, deflate=True, clean=clean)
    output.seek(0)
    return output.getvalue()


def flatten_form_pdf_bytes(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        flattened_count = flatten_form_fields(doc)
        flattened_bytes = save_pdf_bytes(doc, clean=True)
        return flattened_bytes, flattened_count
    finally:
        doc.close()


def data_or_default(data, field_name, config):
    if field_name in data:
        return data[field_name]
    return config.get('default', '')


def build_visa_page1_data(application):
    form_data = get_form_data(application)
    gender = first_value(form_data.get('gender'), getattr(application, 'gender', ''))
    marital_status = first_value(form_data.get('marital_status'), getattr(application, 'marital_status', ''))

    data = {
        'pinyin_name1': field_value(application, 'pinyin_name1'),
        'pinyin_name2': field_value(application, 'pinyin_name2'),
        'chinese_name1': field_value(application, 'chinese_name1'),
        'chinese_name2': field_value(application, 'chinese_name2'),
        'used_name1': field_value(application, 'used_name1'),
        'used_name2': field_value(application, 'used_name2'),
        'nationality': field_value(application, 'nationality', 'nationality'),
        'othernationality': field_value(application, 'othernationality', default='无'),
        'orthernationality': field_value(application, 'othernationality', default='无'),
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
    data['registered_address'] = field_value(application, 'registered_address')
    data['current_address'] = field_value(application, 'current_address')
    data['home_address2'] = format_home_address({**form_data, **data})
    return data


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
        'guarantor_visa_status': snapshot_value(application, 'guarantor_visa_status'),
        'same': field_value(application, 'same', default='同上'),
        'xx': checked_if(gender == 'male'),
        'xy': checked_if(gender == 'female'),
    }
    for field_name in ('x1', 'x2', 'x3', 'x4', 'x5', 'x6'):
        data[field_name] = form_data.get(field_name, 'no')
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
        raise FileNotFoundError(f'Visa PDF font is required: {FONT_PATH}')

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


def generate_visa_return_pdf_by_coordinates(application):
    positions = load_positions()
    page1_data = build_visa_page1_data(application)
    page2_data = build_visa_page2_data(application)
    visa_1_bytes = fill_pdf_template(VISA_1_PATH, positions['visa_1'], page1_data)
    visa_2_bytes = fill_pdf_template(VISA_2_PATH, positions['visa_2'], page2_data)
    return merge_pdfs(visa_1_bytes, visa_2_bytes)


def fill_form_pdf(application):
    if not VISA_FORM_TEMPLATE_PATH.exists():
        raise FileNotFoundError(f'visa_tem.pdf not found: {VISA_FORM_TEMPLATE_PATH}')

    mapping = load_form_field_mapping()
    mappings = mapping.get('mappings') or {}
    if not mappings:
        raise ValueError('form_field_mapping.json has no mappings.')

    variables = get_form_application_variables(application)
    doc = fitz.open(str(VISA_FORM_TEMPLATE_PATH))
    filled_count = 0
    warning_count = 0
    try:
        for variable_name, config in mappings.items():
            config_type = config.get('type', 'text')
            if config_type == 'choice':
                value = variables.get(variable_name, config.get('default', ''))
                rule = (config.get('rules') or {}).get(str(value))
                if not rule:
                    continue
                pdf_field = rule.get('pdf_field')
                selected_value = rule.get('value', rule.get('checked_value', 'Yes'))
                if pdf_field:
                    if fill_choice_mapping(doc, pdf_field, selected_value):
                        filled_count += 1
                    else:
                        warning_count += 1
                continue

            pdf_field = config.get('pdf_field')
            if not pdf_field:
                continue

            value = variables.get(variable_name, '')
            if config_type in ('checkbox', 'radio'):
                filled = fill_checkbox_mapping(
                    doc,
                    pdf_field,
                    is_checked(value),
                    checked_value=config.get('checked_value', config.get('value', 'Yes')),
                    unchecked_value=config.get('unchecked_value', 'Off'),
                )
            else:
                mapped_value = mapped_form_value(value, config)
                filled = fill_text_mapping(doc, pdf_field, mapped_value)
                if not filled:
                    filled = draw_value_on_field(doc, pdf_field, mapped_value)
            if filled:
                filled_count += 1
            else:
                warning_count += 1

        try:
            doc.need_appearances(True)
        except Exception:
            pass
        filled_bytes = doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()

    flattened = False
    try:
        flattened_bytes, flattened_count = flatten_form_pdf_bytes(filled_bytes)
        flattened = True
        logger.info(
            'visa form filling branch used: mapped=%s filled=%s warnings=%s flattened=%s flattened_fields=%s',
            len(mappings),
            filled_count,
            warning_count,
            flattened,
            flattened_count,
        )
        return flattened_bytes
    except Exception as exc:
        logger.warning('Failed to flatten visa PDF form fields: %s', exc)
        logger.info(
            'visa form filling branch used: mapped=%s filled=%s warnings=%s flattened=%s',
            len(mappings),
            filled_count,
            warning_count,
            flattened,
        )
        return filled_bytes


def generate_visa_return_pdf_by_form(application):
    return fill_form_pdf(application)


def generate_visa_return_pdf(application):
    if VISA_FORM_TEMPLATE_PATH.exists() and FORM_FIELD_MAPPING_PATH.exists():
        try:
            return generate_visa_return_pdf_by_form(application)
        except Exception:
            pass
    return generate_visa_return_pdf_by_coordinates(application)


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

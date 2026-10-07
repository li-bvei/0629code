import hashlib
import io
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import fitz

from .pdf_fonts import FontSubsetError, subset_pdf_fonts
from django.conf import settings
from django.utils import timezone


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


class VisaPdfError(Exception):
    """PDF を作れなかった理由。code は画面・記録用の種別、fields は該当する項目。

    これまでのように例外を握りつぶして別の方式で「成功」を返すことはしない。
    """

    def __init__(self, code, message, fields=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.fields = list(fields or [])


@dataclass
class VisaPdfResult:
    content: bytes
    method: str                 # form / coordinates
    template_name: str
    template_version: str       # 使ったテンプレート一式の SHA-256（先頭 16 桁）
    stats: dict = field(default_factory=dict)


def _sha256_files(paths):
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode('utf-8'))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def form_assets_available():
    return VISA_FORM_TEMPLATE_PATH.exists() and FORM_FIELD_MAPPING_PATH.exists()


def coordinate_assets_available():
    return VISA_1_PATH.exists() and VISA_2_PATH.exists() and POSITIONS_PATH.exists()


def _open_template(path):
    try:
        doc = fitz.open(str(path))
    except Exception as exc:  # 壊れたファイル・PDF でないファイル
        raise VisaPdfError('template_broken', f'PDF テンプレート「{path.name}」を開けません（破損している可能性があります）。') from exc
    if doc.page_count < 1:
        doc.close()
        raise VisaPdfError('template_broken', f'PDF テンプレート「{path.name}」にページがありません。')
    return doc


def _verify_output(content):
    if not content or not content.startswith(b'%PDF'):
        raise VisaPdfError('output_invalid', '生成した PDF が正しい形式ではありません。')
    try:
        check = fitz.open(stream=content, filetype='pdf')
        pages = check.page_count
        check.close()
    except Exception as exc:
        raise VisaPdfError('output_invalid', '生成した PDF を読み直せませんでした。') from exc
    if pages < 1:
        raise VisaPdfError('output_invalid', '生成した PDF にページがありません。')


# --- 担保人：テンプレートの値と手入力の値をまとめる ---------------------------------------

# 担保人の項目 → (申請の列, 表単データの鍵, テンプレートスナップショットの鍵)
GUARANTOR_FIELDS = {
    'guarantor_name_jp': ('guarantor_name', 'guarantor_name_jp', 'guarantor_name'),
    'guarantor_name_en': (None, 'guarantor_name_en', 'guarantor_name_en'),
    'guarantor_phone': ('guarantor_phone', 'guarantor_phone', 'guarantor_phone'),
    'guarantor_address_jp': ('guarantor_address', 'guarantor_address_jp', 'guarantor_address'),
    'guarantor_address_en': (None, 'guarantor_address_en', 'guarantor_address_en'),
    'guarantor_birth_date': (None, 'guarantor_birth_date', 'guarantor_birth_date'),
    'guarantor_nationality': (None, 'guarantor_nationality', 'guarantor_nationality'),
    'guarantor_visa_status': (None, 'guarantor_visa_status', 'guarantor_visa_status'),
    'guarantor_job': ('guarantor_occupation', 'guarantor_job', 'guarantor_occupation'),
    'relation_to_applicant': ('guarantor_relationship', 'relation_to_applicant', 'guarantor_relationship'),
}


def _blank(value):
    return value in (None, '')


def resolve_guarantor(application):
    """担保人の各項目の値と出所を返す。{項目: (値, 'manual' | 'template' | '')}。

    手入力（申請の列・表単データ）があればそれを使い、無ければ選択した担保人テンプレートの
    スナップショットの値を使う。手入力がテンプレートと同じ値なら出所は template とする。
    """
    form_data = get_form_data(application)
    snapshot = get_snapshot(application)
    resolved = {}
    for name, (attr, form_key, snapshot_key) in GUARANTOR_FIELDS.items():
        manual = form_data.get(form_key)
        if _blank(manual) and attr:
            manual = getattr(application, attr, '')
        template_value = snapshot.get(snapshot_key)
        if not _blank(manual):
            same = not _blank(template_value) and str(manual) == str(template_value)
            resolved[name] = (manual, 'template' if same else 'manual')
        elif not _blank(template_value):
            resolved[name] = (template_value, 'template')
        else:
            resolved[name] = ('', '')
    return resolved


# 生成前に必須とする項目：(項目, 表示名, 値を取り出す関数)
def _applicant_name(app):
    return first_value(app.applicant_name, get_form_data(app).get('pinyin_name1'), get_form_data(app).get('chinese_name1'))


def _printed_name(app):
    # 様式の氏名欄に入るのは英文姓・中文姓（申請人氏名そのものは様式に印字されない）
    form_data = get_form_data(app)
    return first_value(form_data.get('pinyin_name1'), form_data.get('chinese_name1'))


REQUIRED_FIELDS = (
    ('applicant_name', '申請人氏名', _applicant_name),
    ('printed_name', 'PDF に印字する氏名（英文姓 または 中文姓）', _printed_name),
    ('birth_date', '申請人の生年月日', lambda app: first_value(app.birth_date, get_form_data(app).get('birth_date'))),
    ('nationality', '申請人の国籍', lambda app: field_value(app, 'nationality', 'nationality')),
    ('passport_number', '旅券番号', lambda app: field_value(app, 'passport_id', 'passport_number')),
    ('passport_expiry_date', '旅券の有効期限', lambda app: first_value(get_form_data(app).get('passport_date2'), app.passport_expiry_date)),
    ('guarantor_name_jp', '担保人氏名', lambda app: resolve_guarantor(app)['guarantor_name_jp'][0]),
    ('guarantor_address_jp', '担保人住所', lambda app: resolve_guarantor(app)['guarantor_address_jp'][0]),
    ('guarantor_phone', '担保人電話番号', lambda app: resolve_guarantor(app)['guarantor_phone'][0]),
)


def _is_date(value):
    if isinstance(value, (date, datetime)):
        return True
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d'):
        try:
            datetime.strptime(str(value), fmt)
            return True
        except ValueError:
            continue
    return False


DATE_REQUIRED_FIELDS = {'birth_date', 'passport_expiry_date'}


def missing_required_fields(application):
    """生成前に足りない・解釈できない必須項目（[{field, label}]）。空なら生成できる。"""
    missing = []
    for key, label, getter in REQUIRED_FIELDS:
        value = getter(application)
        if _blank(value):
            missing.append({'field': key, 'label': label})
        elif key in DATE_REQUIRED_FIELDS and not _is_date(value):
            missing.append({'field': key, 'label': f'{label}（日付の形式が正しくありません）'})
    return missing


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
    variables.update({key: value for key, value in snapshot.items() if value not in (None, '')})
    variables.update({key: value for key, value in form_data.items() if value not in (None, '')})
    # 担保人は resolve_guarantor の結果（手入力 → テンプレート）で統一する
    guarantor = {name: value for name, (value, _) in resolve_guarantor(application).items()}
    variables.update({
        'guarantor_name': guarantor['guarantor_name_jp'], 'guarantor_name_jp': guarantor['guarantor_name_jp'],
        'guarantor_name_en': guarantor['guarantor_name_en'], 'guarantor_phone': guarantor['guarantor_phone'],
        'guarantor_address': guarantor['guarantor_address_jp'], 'guarantor_address_jp': guarantor['guarantor_address_jp'],
        'guarantor_address_en': guarantor['guarantor_address_en'], 'guarantor_birth_date': guarantor['guarantor_birth_date'],
        'guarantor_nationality': guarantor['guarantor_nationality'], 'guarantor_visa_status': guarantor['guarantor_visa_status'],
        'guarantor_occupation': guarantor['guarantor_job'], 'guarantor_job': guarantor['guarantor_job'],
        'guarantor_relationship': guarantor['relation_to_applicant'], 'relation_to_applicant': guarantor['relation_to_applicant'],
    })
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
    """単一選択の項目を選ぶ。選んだ値を持つ選択肢が無い・書き込みに失敗したときは False（成功扱いにしない）。"""
    selected_value = str(selected_value)
    matched = False
    failed = False
    parent_xrefs = set()
    for page in doc:
        widgets = page.widgets()
        if not widgets:
            continue
        for widget in widgets:
            if widget.field_name != field_name:
                continue
            on_values = widget_on_values(widget)
            next_value = selected_value if selected_value in on_values else 'Off'
            try:
                doc.xref_set_key(widget.xref, 'AS', f'/{next_value}')
                parent_match = PARENT_XREF_RE.search(doc.xref_object(widget.xref, compressed=False))
                if parent_match:
                    parent_xrefs.add(int(parent_match.group(1)))
            except Exception as exc:
                logger.warning('Failed to update visa PDF radio field %s: %s', field_name, exc)
                failed = True
                continue
            matched = matched or next_value == selected_value
    for parent_xref in parent_xrefs:
        try:
            doc.xref_set_key(parent_xref, 'V', f'/{selected_value}')
        except Exception as exc:
            logger.warning('Failed to update visa PDF radio parent %s: %s', field_name, exc)
            failed = True
    return matched and not failed


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
        remaining = [widget.field_name for widget in (page.widgets() or [])]
        if remaining:
            # 入力欄が残ると、印字と入力欄の値が二重になったり後から書き換えられたりする
            raise RuntimeError(f'form fields remain after flattening: {remaining[:5]}')

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

    guarantor = {name: value for name, (value, _) in resolve_guarantor(application).items()}
    data = {
        'job_title2': field_value(application, 'job_title2'),
        # 担保人は手入力 → 選択した担保人テンプレートの順で決める（テンプレートを迂回しない）
        'guarantor_name_en': guarantor['guarantor_name_en'],
        'guarantor_name_jp': guarantor['guarantor_name_jp'],
        'guarantor_phone': guarantor['guarantor_phone'],
        'guarantor_address_en': guarantor['guarantor_address_en'],
        'guarantor_address_jp': guarantor['guarantor_address_jp'],
        'guarantor_birth_date': format_date(guarantor['guarantor_birth_date']),
        'relation_to_applicant': guarantor['relation_to_applicant'],
        'guarantor_job': guarantor['guarantor_job'],
        'guarantor_nationality': guarantor['guarantor_nationality'],
        'guarantor_visa_status': guarantor['guarantor_visa_status'],
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
        raise VisaPdfError('font_missing', f'PDF 用のフォント「{FONT_PATH.name}」がサーバーにありません。')

    doc = _open_template(template_path)
    page = doc[0]
    try:
        page.insert_font(fontname=FONT_NAME, fontfile=str(FONT_PATH))
    except Exception as exc:
        doc.close()
        raise VisaPdfError('font_missing', f'PDF 用のフォント「{FONT_PATH.name}」を読み込めません。') from exc

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


def merge_pdfs(visa_1_bytes, visa_2_bytes):  # noqa: D401（座標方式の 2 ページを結合）
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
    try:
        positions = load_positions()
    except (OSError, ValueError) as exc:
        raise VisaPdfError('template_broken', '座標設定（field_positions.json）を読み込めません。') from exc
    missing = [name for name in ('visa_1', 'visa_2') if not isinstance(positions.get(name), dict)]
    if missing:
        raise VisaPdfError('template_field_mismatch', '座標設定にページの定義がありません：' + '、'.join(missing), missing)
    page1_data = build_visa_page1_data(application)
    page2_data = build_visa_page2_data(application)
    visa_1_bytes = fill_pdf_template(VISA_1_PATH, positions['visa_1'], page1_data)
    visa_2_bytes = fill_pdf_template(VISA_2_PATH, positions['visa_2'], page2_data)
    return merge_pdfs(visa_1_bytes, visa_2_bytes)


def _template_field_names(doc):
    return {widget.field_name for page in doc for widget in (page.widgets() or [])}


def _mapping_pdf_fields(mappings):
    fields = []
    for variable_name, config in mappings.items():
        if config.get('type') == 'choice':
            fields += [(variable_name, rule.get('pdf_field')) for rule in (config.get('rules') or {}).values()
                       if rule.get('pdf_field')]
        elif config.get('pdf_field'):
            fields.append((variable_name, config['pdf_field']))
    return fields


def fill_form_pdf(application, stats=None):
    """フォーム項目付きテンプレートへ入力して平坦化する。どの段階の失敗も VisaPdfError にする（握りつぶさない）。"""
    stats = stats if stats is not None else {}
    try:
        mapping = load_form_field_mapping()
    except (OSError, ValueError) as exc:
        raise VisaPdfError('template_broken', '項目対応表（form_field_mapping.json）を読み込めません。') from exc
    mappings = mapping.get('mappings') or {}
    if not mappings:
        raise VisaPdfError('template_broken', '項目対応表（form_field_mapping.json）に項目がありません。')

    variables = get_form_application_variables(application)
    doc = _open_template(VISA_FORM_TEMPLATE_PATH)
    names = _template_field_names(doc)
    mismatched = [f'{variable}→{pdf_field}' for variable, pdf_field in _mapping_pdf_fields(mappings) if pdf_field not in names]
    if mismatched:
        doc.close()
        raise VisaPdfError(
            'template_field_mismatch',
            f'PDF テンプレートに対応表の項目がありません（{len(mismatched)} 件）。テンプレートと対応表の版を確認してください。',
            mismatched,
        )
    filled_count = 0
    warning_count = 0
    drawn = []
    failed = []
    try:
        for variable_name, config in mappings.items():
            config_type = config.get('type', 'text')
            if config_type == 'choice':
                value = variables.get(variable_name, config.get('default', ''))
                if value in (None, ''):
                    continue  # 未選択：選ぶ値が無いだけ
                rule = (config.get('rules') or {}).get(str(value))
                pdf_field = (rule or {}).get('pdf_field')
                selected_value = (rule or {}).get('value', (rule or {}).get('checked_value', 'Yes'))
                # 対応表に無い値・選択肢が選べない場合は、選択が抜けた PDF を成功として返さない
                if pdf_field and fill_choice_mapping(doc, pdf_field, selected_value):
                    filled_count += 1
                else:
                    warning_count += 1
                    failed.append(f'{config.get("label") or variable_name}（{value}）')
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
                if not filled and mapped_value:
                    # 項目は存在するが値を設定できない（選択肢の定義が壊れている等）：同じ位置に文字として描く。
                    # 描けなければ失敗として扱う（値が抜けた PDF を成功として返さない）。
                    filled = draw_value_on_field(doc, pdf_field, mapped_value)
                    if filled:
                        drawn.append(variable_name)
                elif not mapped_value:
                    filled = True  # 空欄の項目は書く値が無いだけ
            if filled:
                filled_count += 1
            else:
                warning_count += 1
                failed.append(variable_name)

        if failed:
            raise VisaPdfError('field_write_failed', 'PDF の次の項目に値を書き込めませんでした：' + '、'.join(failed), failed)
        try:
            doc.need_appearances(True)
        except Exception:
            pass  # 表示更新の指定だけ。値は平坦化で描画する
        filled_bytes = doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()

    try:
        flattened_bytes, flattened_count = flatten_form_pdf_bytes(filled_bytes)
    except Exception as exc:
        raise VisaPdfError('flatten_failed', 'PDF の入力欄を確定（平坦化）できませんでした。') from exc
    stats.update({'mapped': len(mappings), 'filled': filled_count, 'drawn_fallback': drawn,
                  'flattened_fields': flattened_count})
    logger.info('visa form filled: mapped=%s filled=%s drawn=%s flattened=%s', len(mappings), filled_count, len(drawn),
                flattened_count)
    return flattened_bytes


def generate_visa_return_pdf_by_form(application):
    return fill_form_pdf(application)


def render_visa_return_pdf(application):
    """PDF を作る。方式はテンプレート一式の有無で明示的に決め、失敗したら VisaPdfError を投げる。

    フォーム用テンプレート（visa_tem.pdf ＋ 対応表）があればフォーム方式。無い環境だけ座標方式。
    フォーム方式で失敗したときに座標方式へ黙って切り替えることはしない（失敗の原因が隠れるため）。
    想定外の例外も握りつぶさず、ログに詳細を残したうえで generation_failed として返す。
    """
    try:
        return _render_visa_return_pdf(application)
    except VisaPdfError:
        raise
    except Exception as exc:
        logger.exception('visa PDF generation failed unexpectedly (application=%s)', getattr(application, 'pk', None))
        raise VisaPdfError(
            'generation_failed', f'PDF の作成中に想定外のエラーが発生しました（{type(exc).__name__}）。管理者に連絡してください。',
        ) from exc


def _render_visa_return_pdf(application):
    stats = {}
    if form_assets_available():
        method, template_name = 'form', VISA_FORM_TEMPLATE_PATH.name
        version = _sha256_files([VISA_FORM_TEMPLATE_PATH, FORM_FIELD_MAPPING_PATH])
        content = fill_form_pdf(application, stats)
    elif coordinate_assets_available():
        method, template_name = 'coordinates', f'{VISA_1_PATH.name}+{VISA_2_PATH.name}'
        version = _sha256_files([VISA_1_PATH, VISA_2_PATH, POSITIONS_PATH])
        content = generate_visa_return_pdf_by_coordinates(application)
    else:
        raise VisaPdfError('template_missing', 'サーバーに返签 visa 表の PDF テンプレートがありません。')
    _verify_output(content)  # 壊れた出力は従来どおり output_invalid
    # P6：埋め込み字体を使用文字だけに絞る（単票・一括 ZIP・旧/新 API の共通経路。内容・座標・ページは不変）
    original_size = len(content)
    try:
        content = subset_pdf_fonts(content)
    except FontSubsetError as exc:
        logger.exception('visa PDF font subsetting failed (application=%s)', getattr(application, 'pk', None))
        raise VisaPdfError('font_subset_failed', f'PDF の字体の最適化に失敗しました（{exc}）。管理者に連絡してください。') from exc
    stats['size_before_subset'] = original_size
    stats['size_after_subset'] = len(content)
    _verify_output(content)
    return VisaPdfResult(content=content, method=method, template_name=template_name, template_version=version,
                         stats=stats)


def build_visa_return_pdf_filename(application):
    name = (application.applicant_name or get_form_data(application).get('pinyin_name1') or '申請人').strip()
    today = timezone.localdate().strftime('%Y%m%d')
    return f'返签visa表_{name}_{today}.pdf'

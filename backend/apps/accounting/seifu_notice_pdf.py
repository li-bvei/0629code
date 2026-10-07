"""P5 清風合格通知書：固定テンプレート（2 年コース）によるサーバー生成。

- 入力は宛名・許可番号・通知日の 3 項目だけ。通知書番号は許可番号から後端が派生する（derive_notice_number）。
- コース年数・在籍期間はこのテンプレートに固定（画面から変更できない）。座標・字号・字体・背景・他の文字も固定。
- 字体は認可済みの MS Mincho（SEIFU_MS_MINCHO_FONT_PATH）だけを使う。無い・壊れている・別の字体のときは
  生成を止め、代替字体で出力しない。
- 版面に収まらない入力（長すぎる宛名・許可番号、字体に無い文字）は推測で縮めすぎず、業務エラーで止める。
- 出力は一度開き直して 1 ページ・最低サイズ・印字内容を確認してから返す（保存・記録は seifu_pdf_generation）。

座標・字号・字間・擬似太字の値は、ユーザー提供の PSD（文字レイヤーの字号）と Photoshop 出力の参考 PDF 3 件を
ローカルで画素比較して合わせた（参考ファイルはリポジトリに含めない。差異は DEVELOPMENT_PLAN §5.13 を参照）。
"""
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
import unicodedata
from urllib.parse import quote

import fitz
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from apps.audit.services import record
from apps.authentication.drf import business_api_view


TEMPLATE_KEY = 'seifu_2year_2027'
TEMPLATE_NAME = '清風合格通知書（2年コース）'
TEMPLATE_PATH = Path(settings.BASE_DIR) / 'assets' / 'pdf_templates' / 'seifu' / '合格通知書.pdf'
DEFAULT_FONT_PATH = Path(settings.BASE_DIR) / 'media' / 'p5_seifu_input' / 'MSMINCHO.TTF'
GENERATION_METHOD = 'server_fixed_layout'
FONT_ERROR = 'MS Mincho の認可済みフォントファイルが見つかりません。管理者に設定を確認してください。'
FONT_MISMATCH = '設定されたフォントは MS Mincho ではありません。代替フォントでは作成しません。'
TEMPLATE_ERROR = '清風合格通知書テンプレートが見つかりません。'
PDF_FONT_NAME = 'MSMincho'
COURSE_YEARS = '2'
ENROLLMENT_PERIOD = '2027/04/01～2029/03/31'
NOTICE_NUMBER_SUFFIX = ' A'  # テンプレートの「第 … 号」の間に「許可番号 A」を印字する

# 文字色と擬似太字（PSD の文字レイヤーは FauxBold）。参考 PDF との画素比較で決めた値。
TEXT_COLOR = (0.15, 0.15, 0.15)
FAUX_BOLD_WIDTH = 0.03

RECIPIENT_NAME_MAX_LENGTH = 40
MIN_CONDENSE = 0.7  # 長体（横方向の縮小）の下限
PERMIT_PATTERN = re.compile(r'[0-9A-Z]+(?:-[0-9A-Z]+)*')
PERMIT_MIN_LENGTH, PERMIT_MAX_LENGTH = 3, 12
ISSUE_DATE_RANGE = (date(2000, 1, 1), date(2099, 12, 31))

# A4（pt）。point は文字列の基点、max_right は右端の上限（テンプレートの「号」「様」に重ならない位置）。
# min_size まで縮めても収まらない場合は生成しない。tracking は 1 文字ごとの追加字間（pt）。
FIELDS = {
    'notice_number': {'point': (452.2, 154.0), 'size': 12.31, 'min_size': 9.5, 'max_right': 511.0, 'tracking': 0.0},
    'permit_number': {'point': (134.9, 277.4), 'size': 12.31, 'min_size': 9.5, 'max_right': 300.0, 'tracking': 0.0},
    'recipient_name': {'point': (88.0, 315.8), 'size': 18.47, 'min_size': 12.0, 'max_right': 159.5, 'tracking': 0.0},
    'course_years_ja': {'point': (203.5, 434.7), 'size': 14.0, 'min_size': 14.0, 'max_right': 214.0, 'tracking': 0.0},
    'course_years_en': {'point': (389.2, 434.3), 'size': 14.0, 'min_size': 14.0, 'max_right': 400.0, 'tracking': 0.0},
    'enrollment_period': {'point': (186.9, 461.5), 'size': 12.0, 'min_size': 12.0, 'max_right': 330.0, 'tracking': 0.0},
    'issue_date': {'point': (93.1, 605.7), 'size': 14.36, 'min_size': 14.36, 'max_right': 200.0, 'tracking': 0.0,
                   # 「YYYY年MM月DD日」の各文字の基点 x（参考 PDF では年・月・日の位置が固定で、数字はその間の欄に入る）
                   'positions': (93.1, 100.03, 106.96, 113.89, 121.1, 135.0, 141.93, 148.0, 160.4, 167.33, 171.6)},
}
# 空白テンプレートに残っている通知日の仮の「年 月 日」だけを白で消す（参考 PDF ではこの位置に日付全体が入る）。
CLEAR_RECTS = (fitz.Rect(90, 590, 190, 610),)

FIELD_LABELS = {'notice_number': '通知書番号', 'permit_number': '許可番号', 'recipient_name': '宛名'}
# 字体に字形が無い・印字に使えない文字の種類（制御・書式・私用・未割当・区切り）
REJECTED_CATEGORIES = {'Cc', 'Cf', 'Cs', 'Co', 'Cn', 'Zl', 'Zp'}


class SeifuPdfError(Exception):
    """業務エラー（画面にそのまま表示できる文言）。code は API の code として返す。"""

    def __init__(self, code, message, field=''):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


@dataclass(frozen=True)
class SeifuPdfResult:
    content: bytes
    template_version: str
    font_version: str
    notice_number: str
    recipient_name: str
    permit_number: str
    issue_date: date


# --- 入力 ----------------------------------------------------------------------------------

def derive_notice_number(permit_number):
    """通知書番号の唯一の派生規則（画面表示・記録・PDF で同じ値を使う）。"""
    permit = str(permit_number or '').strip()
    return f'{permit}{NOTICE_NUMBER_SUFFIX}' if permit else ''


def normalize_recipient_name(value):
    name = unicodedata.normalize('NFC', str(value or '')).strip()
    name = re.sub(r'[ 　]{2,}', lambda m: m.group(0)[0], name)  # 連続した空白は 1 つにする
    if not name:
        raise SeifuPdfError('missing_recipient_name', '宛名を入力してください。', 'recipient_name')
    if len(name) > RECIPIENT_NAME_MAX_LENGTH:
        raise SeifuPdfError('recipient_name_too_long',
                            f'宛名は {RECIPIENT_NAME_MAX_LENGTH} 文字以内で入力してください。', 'recipient_name')
    for char in name:
        if unicodedata.category(char) in REJECTED_CATEGORIES or (char.isspace() and char not in ' 　'):
            raise SeifuPdfError('invalid_recipient_name',
                                '宛名に印字できない文字（制御文字・書式文字など）が含まれています。', 'recipient_name')
    return name


def normalize_permit_number(value):
    # 全角英数字・全角ハイフンは半角にそろえる（NFKC）。それ以外の記号は受け付けない。
    permit = unicodedata.normalize('NFKC', str(value or '')).strip().upper().replace('ー', '-').replace('−', '-')
    if not permit:
        raise SeifuPdfError('missing_permit_number', '許可番号を入力してください。', 'permit_number')
    if (not PERMIT_PATTERN.fullmatch(permit) or not (PERMIT_MIN_LENGTH <= len(permit) <= PERMIT_MAX_LENGTH)
            or not any(char.isdigit() for char in permit)):
        raise SeifuPdfError(
            'invalid_permit_number',
            f'許可番号は半角英数字（数字を含む {PERMIT_MIN_LENGTH}～{PERMIT_MAX_LENGTH} 文字、区切りのハイフン可）で入力してください。',
            'permit_number',
        )
    return permit


def normalize_issue_date(value):
    if value in (None, ''):
        raise SeifuPdfError('missing_issue_date', '通知日を入力してください。', 'issue_date')
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError as exc:
            raise SeifuPdfError('invalid_issue_date', '通知日の形式が正しくありません（YYYY-MM-DD）。', 'issue_date') from exc
    if not isinstance(value, date):
        raise SeifuPdfError('invalid_issue_date', '通知日の形式が正しくありません（YYYY-MM-DD）。', 'issue_date')
    if not (ISSUE_DATE_RANGE[0] <= value <= ISSUE_DATE_RANGE[1]):
        raise SeifuPdfError('invalid_issue_date', '通知日は 2000 年～2099 年の日付を入力してください。', 'issue_date')
    return value


def validate_values(recipient_name, permit_number, issue_date):
    return (normalize_recipient_name(recipient_name), normalize_permit_number(permit_number),
            normalize_issue_date(issue_date))


def format_issue_date(value):
    return f'{value.year}年{value.month:02d}月{value.day:02d}日'


# --- 字体・テンプレート --------------------------------------------------------------------

def _file_version(path):
    digest = sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def configured_font_path():
    configured = getattr(settings, 'SEIFU_MS_MINCHO_FONT_PATH', '')
    return Path(configured) if configured else DEFAULT_FONT_PATH


def _load_font(path):
    try:
        return fitz.Font(fontfile=str(path))
    except Exception as exc:  # noqa: BLE001 壊れた字体ファイルは業務エラーとして返す
        raise SeifuPdfError('font_broken', 'MS Mincho フォントを読み込めません（ファイルが壊れている可能性があります）。') from exc


def exact_font_path():
    path = configured_font_path()
    if not path.is_file():
        raise SeifuPdfError('font_missing', FONT_ERROR)
    name = _load_font(path).name
    if 'MS Mincho' not in name and 'MS-Mincho' not in name:
        raise SeifuPdfError('font_mismatch', FONT_MISMATCH)
    return path


def _open_template():
    if not TEMPLATE_PATH.is_file():
        raise SeifuPdfError('template_missing', TEMPLATE_ERROR)
    try:
        doc = fitz.open(str(TEMPLATE_PATH))
    except Exception as exc:  # noqa: BLE001
        raise SeifuPdfError('template_broken', '清風合格通知書テンプレートを読み込めません（ファイルが壊れています）。') from exc
    if doc.page_count != 1 or abs(doc[0].rect.width - 595.28) > 2 or abs(doc[0].rect.height - 841.89) > 2:
        doc.close()
        raise SeifuPdfError('template_mismatch', '清風テンプレートが想定の A4 1 ページではありません。')
    return doc


def template_payload():
    payload = {
        'template_key': TEMPLATE_KEY,
        'template_name': TEMPLATE_NAME,
        'course_years': COURSE_YEARS,
        'enrollment_period': ENROLLMENT_PERIOD,
        'notice_number_suffix': NOTICE_NUMBER_SUFFIX.strip(),
        'recipient_name_max_length': RECIPIENT_NAME_MAX_LENGTH,
        'page_count': 0,
        'pages': [],
        'font_available': False,
        'font_error': None,
        'template_error': None,
    }
    try:
        font_path = exact_font_path()
        payload['font_available'] = True
        payload['font_version'] = _file_version(font_path)
    except SeifuPdfError as exc:
        payload['font_error'] = exc.message
    try:
        doc = _open_template()
        try:
            payload['page_count'] = doc.page_count
            payload['pages'] = [{'page': 1, 'width': doc[0].rect.width, 'height': doc[0].rect.height}]
            payload['template_version'] = _file_version(TEMPLATE_PATH)
        finally:
            doc.close()
    except SeifuPdfError as exc:
        payload['template_error'] = exc.message
    return payload


# --- 版面 ----------------------------------------------------------------------------------

def _text_width(font, text, size, tracking):
    return sum(font.text_length(char, fontsize=size) + tracking for char in text) - (tracking if text else 0)


def _fit(font, field, text):
    """指定領域に収まる (字号, 横の縮小率)。

    規則：まず字号を min_size まで縮め、それでも収まらなければ横方向だけを MIN_CONDENSE まで縮める（長体）。
    それでも収まらない入力は業務エラー（はみ出し・重なりのまま印字しない）。
    """
    spec = FIELDS[field]
    available = spec['max_right'] - spec['point'][0]
    size = spec['size']
    width = _text_width(font, text, size, spec['tracking'])
    if width <= available:
        return size, 1.0
    size = max(spec['min_size'], size * available / width)
    width = _text_width(font, text, size, spec['tracking'])
    if width <= available + 0.05:
        return size, 1.0
    condense = available / width
    if condense >= MIN_CONDENSE:
        return size, condense
    label = FIELD_LABELS.get(field, field)
    code = 'recipient_name_too_long' if field == 'recipient_name' else 'permit_number_too_long'
    raise SeifuPdfError(code, f'{label}が長すぎるため、通知書の所定の欄に収まりません（字号と字幅を最小まで縮めても入りません）。',
                        'recipient_name' if field == 'recipient_name' else 'permit_number')


def _fit_size(font, field, text):
    return _fit(font, field, text)[0]


def _check_glyphs(font, field, text):
    for char in text:
        if char in ' 　':
            continue
        if not font.has_glyph(ord(char)):
            label = FIELD_LABELS.get(field, field)
            raise SeifuPdfError('unsupported_character', f'{label}の「{char}」は MS Mincho で印字できません。', field)


def check_layout(recipient_name, permit_number, font=None):
    """字体の字形と版面に収まるかを確認する（保存時の事前確認にも使う）。"""
    font = font or _load_font(exact_font_path())
    _check_glyphs(font, 'recipient_name', recipient_name)
    _check_glyphs(font, 'permit_number', permit_number)
    _fit_size(font, 'recipient_name', recipient_name)
    _fit_size(font, 'permit_number', permit_number)
    _fit_size(font, 'notice_number', derive_notice_number(permit_number))


def _draw(page, font, font_path, field, text):
    spec = FIELDS[field]
    positions = spec.get('positions')
    if positions is not None:
        # 固定の文字位置（通知日）。書式が合わない文字列は描かない（format_issue_date 以外は渡さない）
        if len(positions) != len(text):
            raise SeifuPdfError('generation_failed', '通知日の書式が想定と異なります。')
        size, condense = spec['size'], 1.0
    else:
        size, condense = _fit(font, field, text)
    morph = (fitz.Point(*spec['point']), fitz.Matrix(condense, 1)) if condense < 1 else None
    x, y = spec['point']
    # 1 文字ずつ置いて字間（tracking）を合わせる。擬似太字は塗り＋細い輪郭（PSD の FauxBold に相当）。
    # 長体が必要なときは起点を中心に横だけ縮める（字の位置も同じ比率で詰まる）。
    for index, char in enumerate(text):
        if positions is not None:
            x = positions[index]
        if char not in ' 　':
            page.insert_text(
                fitz.Point(x, y), char, fontsize=size, fontname=PDF_FONT_NAME, fontfile=str(font_path),
                color=TEXT_COLOR, fill=TEXT_COLOR, render_mode=2, border_width=FAUX_BOLD_WIDTH, overlay=True,
                morph=morph,
            )
        x += font.text_length(char, fontsize=size) + spec['tracking']


def _verify_output(content, expected_texts):
    """出力を開き直して確認する。壊れている・空・印字が欠けている場合は成功にしない。"""
    try:
        check = fitz.open(stream=content, filetype='pdf')
        try:
            if check.page_count != 1 or len(content) < 1000:
                raise ValueError('page count or size')
            text = check[0].get_text().replace(' ', '').replace('　', '')
        finally:
            check.close()
    except Exception as exc:  # noqa: BLE001
        raise SeifuPdfError('output_invalid', '生成した PDF を確認できませんでした。もう一度お試しください。') from exc
    missing = [value for value in expected_texts if value.replace(' ', '').replace('　', '') not in text]
    if missing:
        raise SeifuPdfError('output_invalid', '生成した PDF に印字内容が正しく入っていません。もう一度お試しください。')


def render_seifu_notice_pdf(recipient_name, permit_number, issue_date):
    """PDF を作り、検証済みのバイト列を返す（保存はしない）。失敗はすべて SeifuPdfError。"""
    name, permit, issued = validate_values(recipient_name, permit_number, issue_date)
    font_path = exact_font_path()
    font = _load_font(font_path)
    check_layout(name, permit, font)
    notice_number = derive_notice_number(permit)
    doc = _open_template()
    try:
        page = doc[0]
        page.insert_font(fontname=PDF_FONT_NAME, fontfile=str(font_path))
        for rect in CLEAR_RECTS:
            page.draw_rect(rect, color=None, fill=(1, 1, 1), overlay=True)
        _draw(page, font, font_path, 'notice_number', notice_number)
        _draw(page, font, font_path, 'permit_number', permit)
        _draw(page, font, font_path, 'recipient_name', name)
        _draw(page, font, font_path, 'course_years_ja', COURSE_YEARS)
        _draw(page, font, font_path, 'course_years_en', COURSE_YEARS)
        _draw(page, font, font_path, 'enrollment_period', ENROLLMENT_PERIOD)
        _draw(page, font, font_path, 'issue_date', format_issue_date(issued))
        output = BytesIO()
        doc.save(output, garbage=4, deflate=True, clean=True)
        content = output.getvalue()
    except SeifuPdfError:
        raise
    except Exception as exc:  # noqa: BLE001 描画・保存の失敗は業務エラーにする
        raise SeifuPdfError('generation_failed', '合格通知書 PDF の作成中にエラーが発生しました。') from exc
    finally:
        doc.close()
    _verify_output(content, [notice_number, permit, name, format_issue_date(issued)])
    return SeifuPdfResult(content, _file_version(TEMPLATE_PATH), _file_version(font_path), notice_number,
                          name, permit, issued)


def build_filename(recipient_name):
    safe = re.sub(r'[\\/:*?"<>|\r\n\t]+', '_', str(recipient_name or '').strip()).strip(' .') or '未命名'
    return f'清風合格通知書_{safe}.pdf'


def content_disposition(recipient_name, inline=False):
    kind = 'inline' if inline else 'attachment'
    return f'{kind}; filename="seifu_notice.pdf"; filename*=UTF-8\'\'{quote(build_filename(recipient_name))}'


def error_response(exc, http_status=status.HTTP_400_BAD_REQUEST):
    body = {'code': exc.code, 'detail': exc.message}
    if exc.field:
        body['field'] = exc.field
    return Response(body, status=http_status)


INPUT_ERROR_CODES = {
    'missing_recipient_name', 'missing_permit_number', 'missing_issue_date', 'invalid_recipient_name',
    'recipient_name_too_long', 'invalid_permit_number', 'permit_number_too_long', 'invalid_issue_date',
    'unsupported_character', 'invalid_request_id',
}


def http_status_for(exc):
    """入力の誤りは 400、テンプレート・字体・生成・保存の障害は 422（どちらも成功を返さない）。"""
    return status.HTTP_400_BAD_REQUEST if exc.code in INPUT_ERROR_CODES else status.HTTP_422_UNPROCESSABLE_ENTITY


@business_api_view(['GET'], 'seifu')
def seifu_notice_template(request):
    return Response(template_payload())


@business_api_view(['GET'], 'seifu')
def seifu_notice_preview(request):
    """空白テンプレートの画像（入力欄の位置確認用。文字は描かない）。"""
    try:
        doc = _open_template()
        try:
            from django.http import HttpResponse

            pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            return HttpResponse(pix.tobytes('png'), content_type='image/png')
        finally:
            doc.close()
    except SeifuPdfError as exc:
        return error_response(exc, status.HTTP_404_NOT_FOUND)


@business_api_view(['POST'], 'seifu')
def seifu_notice_generate(request):
    """旧 URL：任意文字・任意座標の生成は廃止。生成関数を呼ばず、ファイルも記録も作らない（監査だけ残す）。"""
    record(module='accounting', action='seifu_legacy_endpoint_called', request=request, result='denied',
           reason='legacy arbitrary-text endpoint')
    return Response({
        'code': 'legacy_seifu_endpoint_disabled',
        'detail': '旧版の任意文字 PDF 生成は停止しました。清風合格通知書の画面で宛名・許可番号・通知日を入力して作成してください。',
    }, status=status.HTTP_410_GONE)

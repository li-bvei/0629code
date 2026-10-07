"""P6：返签 visa 表 PDF の字体サブセット化（サイズ最適化）。合成データのみ。

最適化の前後で、ページ数・ページ寸法・文字列・描画結果（画素）が同じで、サイズが大きく減ることを確認する。
単票の generate-pdf（フォーム方式・座標方式）と一括 ZIP が同じ経路を通ることも確認する。
"""
import tempfile
from unittest import mock

import fitz
from django.test import TestCase, override_settings

from apps.accounting import visa_return_pdf
from apps.accounting.models import VisaGuarantorTemplate, VisaReturnPdfGeneration
from apps.accounting.pdf_fonts import FontSubsetError, subset_pdf_fonts
from apps.accounting.tests_vouchers import VoucherFixture
from apps.common.test_isolation import safe_rmtree

URL = '/api/accounting/visa-return-applications/'
LIMIT = 5 * 1024 * 1024


def render_pages(content, dpi=72):
    with fitz.open(stream=content, filetype='pdf') as doc:
        return [(page.rect.width, page.rect.height, page.get_text(), page.get_pixmap(dpi=dpi).samples) for page in doc]


# 生成した PDF は一時ディレクトリに保存する（tearDown で消すのはこの一時ディレクトリだけ。実際の media は触らない）
@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class VisaSizeTests(VoucherFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.template = VisaGuarantorTemplate.objects.create(
            name='合成テンプレート', guarantor_name='合成 保証人', guarantor_name_en='GOSEI HOSHO',
            guarantor_phone='06-0000-0000', guarantor_address='大阪府合成市1-1', guarantor_address_en='1-1 Gosei Osaka',
            guarantor_birth_date='1980-01-02', guarantor_nationality='日本', guarantor_visa_status='日本人',
            guarantor_occupation='会社役員', guarantor_relationship='雇用主',
        )
        self.client.force_login(self.li)
        response = self.client.post(URL, {
            'applicant_name': 'GOSEI TARO', 'birth_date': '1995-05-05', 'nationality': '中国',
            'passport_number': 'E00000000', 'passport_expiry_date': '2030-01-01', 'phone': '090-0000-0000',
            'guarantor_template': self.template.id,
            'form_data': {'pinyin_name1': 'GOSEI', 'pinyin_name2': 'TARO', 'chinese_name1': '合成', 'chinese_name2': '太郎'},
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.app_id = response.json()['id']

    def tearDown(self):
        from django.conf import settings

        safe_rmtree(settings.MEDIA_ROOT)

    def generated_bytes(self, generation_id):
        response = self.client.get(f'{URL}{self.app_id}/pdf-generations/{generation_id}/download/')
        self.assertEqual(response.status_code, 200)
        return b''.join(response.streaming_content)

    def generate_both(self, **patches):
        """最適化あり・なしで同じ申請を作り、(なし, あり) のバイト列を返す。"""
        with mock.patch.object(visa_return_pdf, 'subset_pdf_fonts', side_effect=lambda content: content):
            plain = self.client.post(f'{URL}{self.app_id}/generate-pdf/')
        optimized = self.client.post(f'{URL}{self.app_id}/generate-pdf/')
        self.assertEqual((plain.status_code, optimized.status_code), (201, 201), optimized.content)
        return self.generated_bytes(plain.json()['id']), self.generated_bytes(optimized.json()['id']), optimized.json()

    def assertSameContent(self, before, after):
        self.assertEqual(render_pages(before), render_pages(after))  # 寸法・文字列・画素が同じ

    def test_form_method_is_much_smaller_and_identical(self):
        before, after, data = self.generate_both()
        self.assertEqual(data['method'], 'form')
        self.assertGreater(len(before), 10 * 1024 * 1024)  # 最適化前は字体全体（約 20MB）
        self.assertLess(len(after), LIMIT)
        self.assertSameContent(before, after)
        generation = VisaReturnPdfGeneration.objects.get(pk=data['id'])
        self.assertEqual(generation.file_size, len(after))
        self.assertGreater(generation.details['stats']['size_before_subset'], generation.details['stats']['size_after_subset'])

    def test_coordinate_method_uses_the_same_optimization(self):
        with mock.patch.object(visa_return_pdf, 'form_assets_available', return_value=False):
            before, after, data = self.generate_both()
        self.assertEqual(data['method'], 'coordinates')
        self.assertLess(len(after), LIMIT)
        self.assertLess(len(after), len(before))
        self.assertSameContent(before, after)

    def test_batch_zip_path_uses_the_same_optimized_generation(self):
        # 一括 ZIP（visa-imports/{id}/pdf-zip/）は各申請を generate_and_record(source='batch_zip') で作り、
        # read_generated_pdf で読む。その経路の出力も最適化されていることを確認する。
        from django.test import RequestFactory

        from apps.accounting.models import VisaReturnApplication
        from apps.accounting.visa_pdf_generation import generate_and_record, read_generated_pdf

        request = RequestFactory().post('/')
        request.user = self.li
        outcome = generate_and_record(VisaReturnApplication.objects.get(pk=self.app_id), request=request, source='batch_zip')
        self.assertTrue(outcome.ok, outcome.detail)
        content = read_generated_pdf(outcome.generation)
        self.assertLess(len(content), LIMIT)
        self.assertEqual(outcome.generation.details['source'], 'batch_zip')

    def test_subset_failure_is_a_clear_error_and_no_success_record(self):
        with mock.patch.object(visa_return_pdf, 'subset_pdf_fonts', side_effect=FontSubsetError('合成エラー')):
            response = self.client.post(f'{URL}{self.app_id}/generate-pdf/')
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['code'], 'font_subset_failed')
        self.assertFalse(VisaReturnPdfGeneration.objects.filter(status='success').exists())

    def test_subset_function_rejects_broken_input(self):
        with self.assertRaises(FontSubsetError):
            subset_pdf_fonts(b'not a pdf')

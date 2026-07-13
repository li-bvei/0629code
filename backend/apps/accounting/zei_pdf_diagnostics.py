from io import BytesIO
from urllib.parse import quote

import fitz
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .tax_renewal_templates import get_tax_renewal_templates


NO_ACROFORM_MESSAGE = '该 PDF 没有 AcroForm 字段，需要坐标 mapping'


def rect_payload(rect):
    if not rect:
        return None
    return {
        'x0': round(rect.x0, 2),
        'y0': round(rect.y0, 2),
        'x1': round(rect.x1, 2),
        'y1': round(rect.y1, 2),
        'width': round(rect.width, 2),
        'height': round(rect.height, 2),
    }


def widget_options(widget):
    for attr in ('choice_values', 'field_choices'):
        value = getattr(widget, attr, None)
        if value:
            return list(value)
    return []


def inspect_template(template):
    result = {
        'template_key': template['key'],
        'template_name': template['name'],
        'filename': template['filename'],
        'file_exists': template['file_exists'],
        'page_count': 0,
        'pages': [],
        'has_acroform': False,
        'field_count': 0,
        'fields': [],
    }
    if not template['file_exists']:
        return result

    doc = fitz.open(template['file_path'])
    try:
        result['page_count'] = doc.page_count
        result['pages'] = [
            {
                'page': index + 1,
                'width': round(page.rect.width, 2),
                'height': round(page.rect.height, 2),
            }
            for index, page in enumerate(doc)
        ]
        fields = []
        for page_index, page in enumerate(doc):
            widgets = list(page.widgets() or [])
            for widget in widgets:
                fields.append({
                    'index': len(fields) + 1,
                    'field_name': widget.field_name or '',
                    'field_type': getattr(widget, 'field_type_string', '') or str(getattr(widget, 'field_type', '')),
                    'page': page_index + 1,
                    'rect': rect_payload(widget.rect),
                    'options': widget_options(widget),
                })
        result['fields'] = fields
        result['field_count'] = len(fields)
        result['has_acroform'] = bool(fields)
        return result
    finally:
        doc.close()


def diagnostics_payload():
    return [inspect_template(template) for template in get_tax_renewal_templates()]


def template_by_key(template_key):
    for template in get_tax_renewal_templates():
        if template['key'] == template_key:
            return template
    return None


def numbered_sample_pdf(template_key):
    template = template_by_key(template_key)
    if not template:
        raise ValueError('模板不存在')
    if not template['file_exists']:
        raise FileNotFoundError('模板文件不存在')

    doc = fitz.open(template['file_path'])
    try:
        fields = []
        for page_index, page in enumerate(doc):
            widgets = list(page.widgets() or [])
            for widget in widgets:
                code = f'{len(fields) + 1:03d}'
                fields.append({
                    'index': len(fields) + 1,
                    'code': code,
                    'field_name': widget.field_name or '',
                    'field_type': getattr(widget, 'field_type_string', '') or str(getattr(widget, 'field_type', '')),
                    'page': page_index + 1,
                    'options': widget_options(widget),
                })
                try:
                    widget.field_value = code
                    widget.update()
                except Exception:
                    pass
                if widget.rect:
                    point = fitz.Point(widget.rect.x0 + 1, widget.rect.y0 + min(10, max(widget.rect.height - 2, 6)))
                    page.insert_text(point, code, fontsize=8, color=(1, 0, 0), overlay=True)

        if not fields:
            raise ValueError(NO_ACROFORM_MESSAGE)

        output = BytesIO()
        doc.save(output, garbage=4, deflate=True, clean=True)
        output.seek(0)
        return output.getvalue(), fields, template
    finally:
        doc.close()


@api_view(['GET'])
def tax_renewal_pdf_diagnostics(request):
    return Response(diagnostics_payload())


@api_view(['POST'])
def tax_renewal_pdf_numbered_sample(request):
    template_key = request.data.get('template_key')
    try:
        pdf_bytes, fields, template = numbered_sample_pdf(template_key)
    except FileNotFoundError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    index_text = '\n'.join(
        f"{field['code']} = {field['field_name']} = page {field['page']} = {field['field_type']} = {field['options']}"
        for field in fields
    )
    filename = f"{template['key']}_numbered_sample.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="numbered_sample.pdf"; filename*=UTF-8\'\'{quote(filename)}'
    )
    response['X-Field-Index'] = quote(index_text)
    return response

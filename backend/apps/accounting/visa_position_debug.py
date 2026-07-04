import json
import shutil
from datetime import datetime

import fitz
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .visa_return_pdf import POSITIONS_PATH, TEMPLATE_DIR, VISA_1_PATH, VISA_2_PATH


TEMPLATE_PATHS = {
    'visa_1': VISA_1_PATH,
    'visa_2': VISA_2_PATH,
}


def read_positions():
    with POSITIONS_PATH.open('r', encoding='utf-8') as file:
        return json.load(file)


def get_page_size(template_path):
    doc = fitz.open(str(template_path))
    page = doc[0]
    size = {
        'width': round(page.rect.width, 2),
        'height': round(page.rect.height, 2),
    }
    doc.close()
    return size


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def visa_position_config(request):
    if request.method == 'GET':
        return Response({
            'positions': read_positions(),
            'page_sizes': {
                page_name: get_page_size(template_path)
                for page_name, template_path in TEMPLATE_PATHS.items()
            },
        })

    positions = request.data.get('positions')
    if not isinstance(positions, dict):
        return Response({'detail': 'positions must be an object.'}, status=400)

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    backup_path = TEMPLATE_DIR / f'field_positions.backup.{timestamp}.json'
    shutil.copy2(POSITIONS_PATH, backup_path)

    with POSITIONS_PATH.open('w', encoding='utf-8') as file:
        json.dump(positions, file, ensure_ascii=False, indent=2)
        file.write('\n')

    return Response({'detail': 'saved', 'backup': backup_path.name})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def visa_position_preview(request):
    page_name = request.query_params.get('page', 'visa_1')
    template_path = TEMPLATE_PATHS.get(page_name)
    if template_path is None:
        return Response({'detail': 'page must be visa_1 or visa_2.'}, status=400)

    doc = fitz.open(str(template_path))
    page = doc[0]
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    png_bytes = pixmap.tobytes('png')
    doc.close()
    return HttpResponse(png_bytes, content_type='image/png')

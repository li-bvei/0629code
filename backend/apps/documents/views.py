from rest_framework.viewsets import ModelViewSet

from .models import Document
from .serializers import DocumentSerializer


class DocumentViewSet(ModelViewSet):
    queryset = Document.objects.select_related('case')
    serializer_class = DocumentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        case_id = self.request.query_params.get('case')
        if case_id:
            queryset = queryset.filter(case_id=case_id)
        return queryset

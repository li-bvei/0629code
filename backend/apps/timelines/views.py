from rest_framework.viewsets import ModelViewSet

from .models import Timeline
from .serializers import TimelineSerializer


class TimelineViewSet(ModelViewSet):
    queryset = Timeline.objects.select_related('case')
    serializer_class = TimelineSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        case_id = self.request.query_params.get('case')
        if case_id:
            queryset = queryset.filter(case_id=case_id)
        return queryset

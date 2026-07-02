from rest_framework.viewsets import ModelViewSet

from .models import Reminder
from .serializers import ReminderSerializer


class ReminderViewSet(ModelViewSet):
    queryset = Reminder.objects.select_related('case')
    serializer_class = ReminderSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        case_id = self.request.query_params.get('case')
        if case_id:
            queryset = queryset.filter(case_id=case_id)
        return queryset

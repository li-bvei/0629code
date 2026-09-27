from rest_framework.viewsets import ModelViewSet

from apps.authentication.drf import BusinessScopedViewSetMixin

from .models import Task
from .serializers import TaskSerializer


class TaskViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'task'
    queryset = Task.objects.select_related('case', 'responsible_employee')
    serializer_class = TaskSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        case_id = self.request.query_params.get('case')
        if case_id:
            queryset = queryset.filter(case_id=case_id)
        return queryset

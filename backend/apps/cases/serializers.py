from rest_framework import serializers

from .models import Case


class CaseSerializer(serializers.ModelSerializer):
    case_number = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField()
    customer_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    responsible_employee_name = serializers.SerializerMethodField()

    class Meta:
        model = Case
        fields = [
            'id',
            'case_number',
            'case_type',
            'status',
            'customer',
            'customer_name',
            'company',
            'company_name',
            'responsible_employee',
            'responsible_employee_name',
            'accepted_at',
            'applied_at',
            'result_notified_at',
            'completed_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'customer_name',
            'company_name',
            'responsible_employee_name',
            'created_at',
            'updated_at',
        ]

    def get_customer_name(self, obj):
        return obj.customer.name

    def get_company_name(self, obj):
        if obj.company is None:
            return ''
        return obj.company.name

    def get_responsible_employee_name(self, obj):
        if obj.responsible_employee is None:
            return ''
        return obj.responsible_employee.name

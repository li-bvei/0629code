import calendar
from datetime import date

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cases.models import Case
from apps.companies.models import Company, CompanyStaff
from apps.customers.models import Customer, FamilyMember

from .serializers import ReceptionSerializer


class ReceptionCreateView(APIView):
    def post(self, request):
        serializer = ReceptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_201_CREATED)


class DashboardDeadlinesView(APIView):
    def get(self, request):
        today = timezone.localdate()
        items = []

        def latest_case(queryset):
            return queryset.select_related('customer', 'company').order_by('-updated_at', '-id').first()

        def case_data(case):
            if case is None:
                return {
                    'case_id': None,
                    'case_number': '-',
                    'case_type': '-',
                }
            return {
                'case_id': case.id,
                'case_number': case.case_number,
                'case_type': case.case_type,
            }

        def add_deadline(deadline_type, target_type, target_name, deadline_label, deadline_date, case):
            if not deadline_date:
                return
            days_left = (deadline_date - today).days
            if days_left > 180:
                return
            status_value = 'overdue' if days_left < 0 else 'today' if days_left == 0 else 'upcoming'
            items.append({
                'type': deadline_type,
                'target_type': target_type,
                'target_name': target_name,
                'deadline_label': deadline_label,
                'deadline_date': deadline_date.isoformat(),
                'days_left': days_left,
                'status': status_value,
                **case_data(case),
            })

        for customer in Customer.objects.all():
            case = latest_case(customer.cases)
            add_deadline(
                'residence_expiry',
                'customer',
                customer.name,
                '在留期限',
                customer.residence_expiry,
                case,
            )
            add_deadline(
                'passport_expiry',
                'customer',
                customer.name,
                'パスポート期限',
                customer.passport_expiry,
                case,
            )

        for family_member in FamilyMember.objects.select_related('customer'):
            case = latest_case(family_member.customer.cases)
            add_deadline(
                'residence_expiry',
                'family_member',
                family_member.name,
                '在留期限',
                family_member.residence_expiry,
                case,
            )
            add_deadline(
                'passport_expiry',
                'family_member',
                family_member.name,
                'パスポート期限',
                getattr(family_member, 'passport_expiry', None),
                case,
            )

        for staff_member in CompanyStaff.objects.select_related('company'):
            case = latest_case(staff_member.company.cases)
            add_deadline(
                'residence_expiry',
                'company_staff',
                staff_member.name,
                '在留期限',
                staff_member.residence_expiry,
                case,
            )
            add_deadline(
                'passport_expiry',
                'company_staff',
                staff_member.name,
                'パスポート期限',
                staff_member.passport_expiry,
                case,
            )

        for company in Company.objects.all():
            fiscal_deadline = self.get_next_fiscal_declaration_deadline(company.fiscal_month, today)
            add_deadline(
                'fiscal_declaration',
                'company',
                company.name,
                '決算申告期限',
                fiscal_deadline,
                latest_case(company.cases),
            )

        items.sort(key=lambda item: (item['days_left'], item['deadline_date'], item['target_name']))
        return Response(items)

    @staticmethod
    def get_next_fiscal_declaration_deadline(fiscal_month, today):
        if not fiscal_month:
            return None
        try:
            month = int(fiscal_month)
        except ValueError:
            return None
        if month < 1 or month > 12:
            return None

        deadline = DashboardDeadlinesView.get_fiscal_declaration_deadline(today.year, month)
        if deadline < today:
            deadline = DashboardDeadlinesView.get_fiscal_declaration_deadline(today.year + 1, month)
        return deadline

    @staticmethod
    def get_fiscal_declaration_deadline(year, fiscal_month):
        deadline_month_index = fiscal_month + 2
        deadline_year = year + (deadline_month_index - 1) // 12
        deadline_month = (deadline_month_index - 1) % 12 + 1
        deadline_day = calendar.monthrange(deadline_year, deadline_month)[1]
        return date(deadline_year, deadline_month, deadline_day)

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.customers.models import Customer

from .models import Company


class CompanyRepresentativeCustomerApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username='company-representative-test',
            password='password',
        )
        self.client.force_authenticate(self.user)
        self.customer = Customer.objects.create(
            name='代表者顧客',
            birth_date='1990-01-01',
        )

    def test_company_create_saves_representative_customer(self):
        response = self.client.post('/api/companies/', {
            'name': '代表者保存会社',
            'representative_customer': self.customer.id,
        }, format='json')

        self.assertEqual(response.status_code, 201)
        company = Company.objects.get(id=response.data['id'])
        self.assertEqual(company.representative_customer_id, self.customer.id)
        self.assertEqual(response.data['representative_customer'], self.customer.id)
        self.assertEqual(response.data['representative_customer_name'], self.customer.name)

    def test_company_update_returns_representative_customer(self):
        company = Company.objects.create(name='代表者更新会社')

        response = self.client.patch(f'/api/companies/{company.id}/', {
            'representative_customer': self.customer.id,
        }, format='json')

        self.assertEqual(response.status_code, 200)
        company.refresh_from_db()
        self.assertEqual(company.representative_customer_id, self.customer.id)
        self.assertEqual(response.data['representative_customer'], self.customer.id)
        self.assertEqual(response.data['representative_customer_name'], self.customer.name)

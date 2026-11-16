from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APITestCase

PAYLOAD = {
    'company_name': 'BARCODE TECHNOLOGIES', 'address1': 'Pallur, Mahe', 'gstin': '34AALFB2923L1ZE',
    'phone': '9847877186', 'invoice_number': 'BTM/26-27/8856', 'invoice_date': '2026-10-14',
    'entry_type': 'purchase', 'taxable_amount': '2344.00', 'igst_amount': '421.92',
    'round_off': '0.08', 'total_amount': '2766.00',
    'items': [
        {'item_name': 'TAG 80X40 YELLOW TAG(500)', 'hsn_code': '48219090', 'qty': '6', 'rate': '180', 'gst_percent': '18', 'amount': '1080'},
        {'item_name': '40MMX35MM 2UPS WITH GAP LABEL(2700)', 'hsn_code': '48219010', 'qty': '6', 'rate': '169', 'gst_percent': '18', 'amount': '1014'},
        {'item_name': '85MM X 300MTS WAX RIBBON', 'hsn_code': '96121090', 'qty': '2', 'rate': '125', 'gst_percent': '18', 'amount': '250'},
    ],
}


@override_settings(EXPORT_API_KEY='k')
class FlowTest(APITestCase):
    def test_flow(self):
        User.objects.create_user('m', password='p')
        t = self.client.post('/api/v1/auth/token/', {'username': 'm', 'password': 'p'}).data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {t}')
        r = self.client.post('/api/v1/invoices/', PAYLOAD, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['warnings'], [])
        # duplicate rejected
        self.assertEqual(self.client.post('/api/v1/invoices/', PAYLOAD, format='json').status_code, 400)
        # no items rejected
        bad = dict(PAYLOAD, invoice_number='X', items=[])
        self.assertEqual(self.client.post('/api/v1/invoices/', bad, format='json').status_code, 400)
        # external software
        self.client.credentials(HTTP_X_API_KEY='k')
        g = self.client.get('/api/v1/export/invoices/')
        self.assertEqual(g.data['count'], 1)
        self.assertEqual(len(g.data['results'][0]['details']), 3)
        self.assertEqual(self.client.post('/api/v1/export/ack/', {'ids': [1]}, format='json').data['acknowledged'], 1)
        self.assertEqual(self.client.get('/api/v1/export/invoices/').data['count'], 0)
        self.assertEqual(self.client.get('/api/v1/export/invoices/?include_exported=1').data['count'], 1)
        self.client.credentials(HTTP_X_API_KEY='wrong')
        self.assertEqual(self.client.get('/api/v1/export/invoices/').status_code, 403)
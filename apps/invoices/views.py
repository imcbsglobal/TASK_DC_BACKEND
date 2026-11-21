from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView, ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.filters import SearchFilter
from rest_framework.viewsets import ModelViewSet

from .authentication import AdminTokenAuthentication, ClientTokenAuthentication, issue_admin_token
from .models import AuthToken, ClientUser, Invoice
from .permissions import IsClientUser, IsSuperAdmin
from .serializers import (AdminLoginSerializer, ClientUserSerializer,
                          ExportInvoiceSerializer, InvoiceSerializer, LoginSerializer)
from django.utils.dateparse import parse_date
import hmac

import requests
from django.conf import settings



def _client_id(value):
    value = (value or '').strip()
    if not value:
        raise ValidationError({'client_id': 'client_id is required.'})
    return value

def _date_param(request, name):
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        d = parse_date(raw)
    except ValueError:
        d = None
    if d is None:
        raise ValidationError({name: 'Use YYYY-MM-DD.'})
    return d    


# ------------------------- mobile app -------------------------

class LoginView(APIView):
    """POST /api/auth/login/  {"client_id","username","password"}"""
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        user = ClientUser.objects.filter(
            client_id=d['client_id'].strip(), username=d['username'].strip()).first()
        if not user or not user.is_active or not user.check_password(d['password']):
            return Response({'detail': 'Invalid client ID, username or password.'}, status=401)
        token = AuthToken.issue(user)
        return Response({
            'token': token.key,
            'expires_at': token.expires_at,
            'user': {'client_id': user.client_id, 'username': user.username,
                     'full_name': user.full_name},
        })


class MobileAuthMixin:
    authentication_classes = [ClientTokenAuthentication]
    permission_classes = [IsClientUser]


class LogoutView(MobileAuthMixin, APIView):
    """POST /api/auth/logout/  - invalidates the current token"""
    def post(self, request):
        request.auth.delete()
        return Response({'detail': 'Logged out.'})


class MeView(MobileAuthMixin, APIView):
    """GET /api/auth/me/"""
    def get(self, request):
        u = request.user
        return Response({'client_id': u.client_id, 'username': u.username,
                         'full_name': u.full_name})


class UploadInvoiceView(MobileAuthMixin, CreateAPIView):
    """POST /api/upload-invoice/  (Bearer token) - header fields + items."""
    serializer_class = InvoiceSerializer


class MyInvoicesView(MobileAuthMixin, ListAPIView):
    """GET /api/my-invoices/?search=...&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
       Upload history of the logged-in client, newest first."""
    serializer_class = InvoiceSerializer
    filter_backends = [SearchFilter]
    search_fields = ['invoice_number', 'company_name', 'gstin',
                     'address1', 'address2', 'phone']

    def get_queryset(self):
        qs = (Invoice.objects.filter(client_id=self.request.user.client_id)
              .prefetch_related('items').order_by('-id'))
        date_from = _date_param(self.request, 'date_from')
        date_to = _date_param(self.request, 'date_to')
        if date_from:
            qs = qs.filter(invoice_date__gte=date_from)
        if date_to:
            qs = qs.filter(invoice_date__lte=date_to)
        return qs


# ------------------------- accounting software (no auth) -------------------------

class InvoiceListView(ListAPIView):
    """GET /api/invoices/?client_id=X            -> all invoices of that client
       GET /api/invoices/?client_id=X&since_id=N -> only invoices with id > N"""
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = ExportInvoiceSerializer

    def get_queryset(self):
        qs = (Invoice.objects
              .filter(client_id=_client_id(self.request.query_params.get('client_id')))
              .prefetch_related('items'))
        since_id = self.request.query_params.get('since_id')
        if since_id:
            if not since_id.isdigit():
                raise ValidationError({'since_id': 'since_id must be a number.'})
            qs = qs.filter(id__gt=int(since_id))
        return qs

# ------------------------- superadmin panel (React) -------------------------

def _fetch_superuser():
    """Credentials come from the central superuser service, never from the browser."""
    if not settings.SUPERUSER_ENDPOINT:
        return None
    try:
        r = requests.get(settings.SUPERUSER_ENDPOINT, timeout=8)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def _same(a, b):
    return hmac.compare_digest(str(a).encode(), str(b).encode())


class AdminLoginView(APIView):
    """POST /api/superadmin/login/  {"username","password"}"""
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        s = AdminLoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data

        su = _fetch_superuser()
        if su is None:
            return Response({'detail': 'Superuser service unavailable. Try again.'}, status=503)

        if (su.get('status') != 'active'
                or not _same(d['username'], su.get('username', ''))
                or not _same(d['password'], su.get('password', ''))):
            return Response({'detail': 'Invalid username or password.'}, status=401)

        return Response({'token': issue_admin_token(su['username']),
                         'username': su['username']})


class AdminAuthMixin:
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsSuperAdmin]


class AdminLogoutView(AdminAuthMixin, APIView):
    """POST /api/superadmin/logout/  (token is stateless; the client discards it)"""
    def post(self, request):
        return Response({'detail': 'Logged out.'})


class ClientUserViewSet(AdminAuthMixin, ModelViewSet):
    """/api/superadmin/client-users/  - list, create, retrieve, update, delete"""
    queryset = ClientUser.objects.order_by('-id')
    serializer_class = ClientUserSerializer
    filter_backends = [SearchFilter]
    search_fields = ['client_id', 'username', 'full_name']

class ClientLookupView(AdminAuthMixin, APIView):
    """GET /api/superadmin/client-lookup/?client_id=X  - details from the licensing API"""

    def get(self, request):
        cid = _client_id(request.query_params.get('client_id'))
        try:
            r = requests.get(settings.LICENSE_API_URL, timeout=10)
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError):
            return Response({'detail': 'Licensing service unavailable. Try again.'}, status=503)

        for c in data.get('customers', []):
            if str(c.get('client_id', '')).strip().upper() == cid.upper():
                validity = c.get('license_validity') or {}
                summary = c.get('license_summary') or {}
                return Response({
                    'client_id': c.get('client_id'),
                    'customer_name': c.get('customer_name', ''),
                    'package': c.get('package', ''),
                    'license_key': c.get('license_key', ''),
                    'status': c.get('status', ''),
                    'expiry_date': validity.get('expiry_date'),
                    'remaining_days': validity.get('remaining_days'),
                    'is_expired': validity.get('is_expired', False),
                    'registered_devices': summary.get('registered_devices', 0),
                    'max_devices': summary.get('max_devices', 0),
                })
        return Response({'detail': 'Client ID not found for this project.'}, status=404)    
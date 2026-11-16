from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView, ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .authentication import ClientTokenAuthentication
from .models import AuthToken, ClientUser, Invoice
from .permissions import IsClientUser
from .serializers import ExportInvoiceSerializer, InvoiceSerializer, LoginSerializer


def _client_id(value):
    value = (value or '').strip()
    if not value:
        raise ValidationError({'client_id': 'client_id is required.'})
    return value


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
    """GET /api/my-invoices/  - upload history of the logged-in client, newest first"""
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        return (Invoice.objects.filter(client_id=self.request.user.client_id)
                .prefetch_related('items').order_by('-id'))


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
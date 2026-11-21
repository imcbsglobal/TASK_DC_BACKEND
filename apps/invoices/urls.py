from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register('superadmin/client-users', views.ClientUserViewSet, basename='client-users')

urlpatterns = [
    # mobile app
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/me/', views.MeView.as_view(), name='me'),
    path('upload-invoice/', views.UploadInvoiceView.as_view(), name='upload_invoice'),
    path('my-invoices/', views.MyInvoicesView.as_view(), name='my_invoices'),
    # accounting software
    path('invoices/', views.InvoiceListView.as_view(), name='list_invoices'),
    # superadmin panel
    path('superadmin/login/', views.AdminLoginView.as_view(), name='admin_login'),
    path('superadmin/logout/', views.AdminLogoutView.as_view(), name='admin_logout'),
    path('superadmin/client-lookup/', views.ClientLookupView.as_view(), name='client_lookup'),
] + router.urls
from django.urls import path

from . import views

urlpatterns = [
    # mobile app
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/me/', views.MeView.as_view(), name='me'),
    path('upload-invoice/', views.UploadInvoiceView.as_view(), name='upload_invoice'),
    path('my-invoices/', views.MyInvoicesView.as_view(), name='my_invoices'),
    # accounting software
    path('invoices/', views.InvoiceListView.as_view(), name='list_invoices'),
]
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone
from .crypto import decrypt, encrypt

class Invoice(models.Model):
    client_id = models.CharField(max_length=50, db_index=True)

    # ---- header (DATA CAPTURE AI sheet) ----
    company_name = models.CharField(max_length=255)
    address1 = models.CharField(max_length=255, blank=True)
    address2 = models.CharField(max_length=255, blank=True)
    gstin = models.CharField(max_length=15)
    phone = models.CharField(max_length=30, blank=True)
    invoice_number = models.CharField(max_length=100)
    invoice_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    entry_type = models.CharField(max_length=20, default='purchase')
    # ---- optional extras ----
    po_number = models.CharField(max_length=100, blank=True)
    taxable_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    round_off = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    warnings = models.JSONField(default=list, blank=True)   # GST total mismatch etc. (informational)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dc_invoice'
        ordering = ['id']
        unique_together = ('client_id', 'gstin', 'invoice_number')

    def __str__(self):
        return f'{self.client_id} - {self.invoice_number}'


class InvoiceItem(models.Model):
    client_id = models.CharField(max_length=50, db_index=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    item_name = models.CharField(max_length=255)
    hsn_code = models.CharField(max_length=20, blank=True)
    qty = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    rate = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gst_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    mrp = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    barcode = models.CharField(max_length=64, blank=True)
    mfd = models.CharField(max_length=20, blank=True)
    exp = models.CharField(max_length=20, blank=True)
    company = models.CharField(max_length=255, blank=True)
    sales_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = 'dc_invoice_item'
        ordering = ['id']


class ClientUser(models.Model):
    """A mobile-app user belonging to one client (company)."""
    client_id = models.CharField(max_length=50, db_index=True)
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=128)
    password_enc = models.TextField(blank=True, default='')
    full_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dc_client_user'
        unique_together = ('client_id', 'username')

    is_authenticated = True  # DRF expects this on request.user

    def set_password(self, raw):
        self.password = make_password(raw)
        self.password_enc = encrypt(raw)

    def reveal_password(self):
        return decrypt(self.password_enc)

    def check_password(self, raw):
        return check_password(raw, self.password)

    def __str__(self):
        return f'{self.client_id}/{self.username}'


class AuthToken(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey(ClientUser, on_delete=models.CASCADE, related_name='tokens')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'dc_auth_token'

    @classmethod
    def issue(cls, user):
        days = getattr(settings, 'TOKEN_TTL_DAYS', 30)
        return cls.objects.create(
            key=secrets.token_hex(32), user=user,
            expires_at=timezone.now() + timedelta(days=days))
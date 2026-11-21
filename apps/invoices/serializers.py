from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from .models import ClientUser, Invoice, InvoiceItem

TOLERANCE = Decimal('1.00')


class CurrentClientDefault:
    """Fills client_id from the logged-in user, so the app never sends it."""
    requires_context = True

    def __call__(self, serializer_field):
        return serializer_field.context['request'].user.client_id


class LoginSerializer(serializers.Serializer):
    client_id = serializers.CharField(max_length=50)
    username = serializers.CharField(max_length=100)
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        exclude = ['invoice', 'client_id']


def gst_warnings(data, items):
    """Informational only - never blocks the POST."""
    w = []
    total = data.get('total_amount', Decimal('0'))
    if total:
        taxes = data.get('cgst_amount', 0) + data.get('sgst_amount', 0) + data.get('igst_amount', 0)
        expected = data.get('taxable_amount', 0) + taxes + data.get('round_off', 0)
        if abs(expected - total) > TOLERANCE:
            w.append(f'Taxable + taxes + round-off = {expected}, but total_amount is {total}')
    if data.get('taxable_amount'):
        line_sum = sum((i.get('amount', 0) for i in items), Decimal('0'))
        if line_sum and abs(line_sum - data['taxable_amount']) > TOLERANCE:
            w.append(f'Item amounts add up to {line_sum}, but taxable_amount is {data["taxable_amount"]}')
    return w


class InvoiceSerializer(serializers.ModelSerializer):
    """POST body from the mobile app: header fields + `items` list (client_id comes from the login token)."""
    client_id = serializers.HiddenField(default=CurrentClientDefault())
    items = InvoiceItemSerializer(many=True, allow_empty=False)

    class Meta:
        model = Invoice
        fields = '__all__'
        read_only_fields = ['id', 'warnings', 'created_at']

    def validate_gstin(self, v):
        v = v.strip().upper()
        if len(v) != 15:
            raise serializers.ValidationError('GSTIN must be 15 characters.')
        return v

    @transaction.atomic
    def create(self, validated):
        items = validated.pop('items')
        validated['warnings'] = gst_warnings(validated, items)
        invoice = Invoice.objects.create(**validated)
        InvoiceItem.objects.bulk_create(
            [InvoiceItem(invoice=invoice, client_id=invoice.client_id, **i) for i in items])
        return invoice


class ExportInvoiceSerializer(serializers.ModelSerializer):
    """What the accounting software reads."""
    header = serializers.SerializerMethodField()
    details = InvoiceItemSerializer(source='items', many=True)

    class Meta:
        model = Invoice
        fields = ['id', 'client_id', 'header', 'details', 'warnings', 'created_at']

    def get_header(self, o):
        return {
            'company_name': o.company_name, 'address1': o.address1, 'address2': o.address2,
            'gstin': o.gstin, 'phone': o.phone, 'invoice_number': o.invoice_number,
            'invoice_date': o.invoice_date, 'due_date': o.due_date, 'entry_type': o.entry_type,
            'po_number': o.po_number, 'taxable_amount': o.taxable_amount, 'cgst_amount': o.cgst_amount,
            'sgst_amount': o.sgst_amount, 'igst_amount': o.igst_amount, 'round_off': o.round_off,
            'total_amount': o.total_amount,
        }

class AdminLoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class ClientUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=6)
    password_plain = serializers.SerializerMethodField()

    class Meta:
        model = ClientUser
        fields = ['id', 'client_id', 'username', 'password', 'password_plain',
                  'full_name', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_password_plain(self, obj):
        return obj.reveal_password()

    def validate(self, attrs):
        if self.instance is None and not attrs.get('password'):
            raise serializers.ValidationError({'password': 'Password is required.'})
        return attrs

    def create(self, validated):
        raw = validated.pop('password')
        user = ClientUser(**validated)
        user.set_password(raw)          # hashed, never stored plain
        user.save()
        return user

    def update(self, instance, validated):
        raw = validated.pop('password', None)
        for k, v in validated.items():
            setattr(instance, k, v)
        if raw:                          
            instance.set_password(raw)
            instance.tokens.all().delete()   
        instance.save()
        return instance    
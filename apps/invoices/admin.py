from django.contrib import admin
from django.contrib.auth.hashers import identify_hasher

from .models import ClientUser, Invoice, InvoiceItem


class ItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'client_id', 'invoice_number', 'company_name', 'total_amount', 'created_at')
    list_filter = ('client_id',)
    search_fields = ('client_id', 'invoice_number', 'company_name', 'gstin')
    inlines = [ItemInline]


@admin.register(ClientUser)
class ClientUserAdmin(admin.ModelAdmin):
    list_display = ('client_id', 'username', 'full_name', 'is_active', 'created_at')
    list_filter = ('client_id', 'is_active')
    search_fields = ('client_id', 'username', 'full_name')

    def save_model(self, request, obj, form, change):
        try:
            identify_hasher(obj.password)      # already hashed, leave it
        except ValueError:
            obj.set_password(obj.password)     # plain text typed in admin, hash it
        super().save_model(request, obj, form, change)
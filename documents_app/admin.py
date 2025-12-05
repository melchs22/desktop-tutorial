from django.contrib import admin
from .models import Client, ClientDocument

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'passport_number', 'nin', 'district', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'passport_number', 'nin')
    readonly_fields = ('created_at',)

@admin.register(ClientDocument)
class ClientDocumentAdmin(admin.ModelAdmin):
    list_display = ('client', 'document_type', 'uploaded_at')
    list_filter = ('document_type', 'uploaded_at')
    search_fields = ('client__name', 'client__passport_number')
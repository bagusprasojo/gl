from django.contrib import admin

from companies.models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_currency', 'is_active', 'created_at')
    search_fields = ('name', 'legal_name', 'tax_number')

# Register your models here.

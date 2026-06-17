from django.contrib import admin

from modules.models import ModuleRegistry


@admin.register(ModuleRegistry)
class ModuleRegistryAdmin(admin.ModelAdmin):
    list_display = ('company', 'key', 'name', 'module_type', 'is_active')
    list_filter = ('company', 'module_type', 'is_active')
    search_fields = ('key', 'name')

# Register your models here.

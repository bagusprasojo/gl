from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import Role, User


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('company', 'key', 'name', 'is_system')
    list_filter = ('company', 'is_system')
    search_fields = ('key', 'name')


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Company access', {'fields': ('company', 'role')}),
    )
    list_display = ('username', 'email', 'company', 'role', 'is_staff', 'is_active')
    list_filter = ('company', 'role', 'is_staff', 'is_active')

# Register your models here.

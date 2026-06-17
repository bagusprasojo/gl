from django.utils import timezone

from audit.models import AuditLog
from audit.services import write_audit
from modules.models import ModuleRegistry


DEFAULT_MODULES = [
    ('core_accounting', 'Core Accounting', ModuleRegistry.CORE, True),
    ('cash_bank', 'Kas & Bank', ModuleRegistry.ADDON, False),
    ('receivables', 'Piutang', ModuleRegistry.ADDON, False),
    ('payables', 'Utang', ModuleRegistry.ADDON, False),
    ('inventory', 'Persediaan', ModuleRegistry.ADDON, False),
    ('fixed_assets', 'Aset Tetap', ModuleRegistry.ADDON, False),
]


def seed_default_modules(company):
    for key, name, module_type, is_active in DEFAULT_MODULES:
        ModuleRegistry.objects.get_or_create(
            company=company,
            key=key,
            defaults={
                'name': name,
                'module_type': module_type,
                'is_active': is_active,
                'activated_at': timezone.now() if is_active else None,
            },
        )


def set_module_status(module, is_active, user=None):
    module.is_active = is_active
    if is_active:
        module.activated_at = timezone.now()
        action = AuditLog.ACTIVATE_MODULE
    else:
        module.deactivated_at = timezone.now()
        action = AuditLog.DEACTIVATE_MODULE
    module.save(update_fields=['is_active', 'activated_at', 'deactivated_at'])
    write_audit(module.company, user, action, module, module.key)
    return module

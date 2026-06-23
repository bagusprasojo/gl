from modules.models import ModuleRegistry


def active_modules(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated or not getattr(request.user, 'company_id', None):
        return {'active_module_keys': set(), 'cash_bank_active': False}
    keys = set(
        ModuleRegistry.objects.filter(company=request.user.company, is_active=True).values_list('key', flat=True)
    )
    return {'active_module_keys': keys, 'cash_bank_active': 'cash_bank' in keys}
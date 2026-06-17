def write_audit(company, user, action, instance, message=''):
    from audit.models import AuditLog

    return AuditLog.objects.create(
        company=company,
        user=user if getattr(user, 'is_authenticated', False) else None,
        action=action,
        model_name=instance.__class__.__name__,
        object_id=str(instance.pk),
        message=message,
    )

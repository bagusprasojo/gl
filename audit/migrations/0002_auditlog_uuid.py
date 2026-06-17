import uuid

from django.db import migrations, models


def populate_uuid(apps, schema_editor):
    AuditLog = apps.get_model('audit', 'AuditLog')
    for log in AuditLog.objects.filter(uuid__isnull=True):
        log.uuid = uuid.uuid4()
        log.save(update_fields=['uuid'])


class Migration(migrations.Migration):
    dependencies = [
        ('audit', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='auditlog',
            name='uuid',
            field=models.UUIDField(db_index=True, editable=False, null=True),
        ),
        migrations.RunPython(populate_uuid, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='auditlog',
            name='uuid',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
    ]

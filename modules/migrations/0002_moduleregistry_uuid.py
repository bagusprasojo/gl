import uuid

from django.db import migrations, models


def populate_uuid(apps, schema_editor):
    ModuleRegistry = apps.get_model('modules', 'ModuleRegistry')
    for module in ModuleRegistry.objects.filter(uuid__isnull=True):
        module.uuid = uuid.uuid4()
        module.save(update_fields=['uuid'])


class Migration(migrations.Migration):
    dependencies = [
        ('modules', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='moduleregistry',
            name='uuid',
            field=models.UUIDField(db_index=True, editable=False, null=True),
        ),
        migrations.RunPython(populate_uuid, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='moduleregistry',
            name='uuid',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
    ]

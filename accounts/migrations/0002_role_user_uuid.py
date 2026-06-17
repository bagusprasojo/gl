import uuid

from django.db import migrations, models


def populate_uuid(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    User = apps.get_model('accounts', 'User')
    for model in (Role, User):
        for instance in model.objects.filter(uuid__isnull=True):
            instance.uuid = uuid.uuid4()
            instance.save(update_fields=['uuid'])


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='role',
            name='uuid',
            field=models.UUIDField(db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='uuid',
            field=models.UUIDField(db_index=True, editable=False, null=True),
        ),
        migrations.RunPython(populate_uuid, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='role',
            name='uuid',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='uuid',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
    ]

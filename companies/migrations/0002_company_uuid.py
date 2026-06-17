import uuid

from django.db import migrations, models


def populate_uuid(apps, schema_editor):
    Company = apps.get_model('companies', 'Company')
    for company in Company.objects.filter(uuid__isnull=True):
        company.uuid = uuid.uuid4()
        company.save(update_fields=['uuid'])


class Migration(migrations.Migration):
    dependencies = [
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='uuid',
            field=models.UUIDField(db_index=True, editable=False, null=True),
        ),
        migrations.RunPython(populate_uuid, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='company',
            name='uuid',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
    ]

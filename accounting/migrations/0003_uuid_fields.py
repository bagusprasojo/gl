import uuid

from django.db import migrations, models


def populate_uuid(apps, schema_editor):
    for model_name in ('Account', 'AccountingPeriod', 'JournalEntry', 'JournalLine'):
        Model = apps.get_model('accounting', model_name)
        for instance in Model.objects.filter(uuid__isnull=True):
            instance.uuid = uuid.uuid4()
            instance.save(update_fields=['uuid'])


class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='uuid',
            field=models.UUIDField(db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='accountingperiod',
            name='uuid',
            field=models.UUIDField(db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='journalentry',
            name='uuid',
            field=models.UUIDField(db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='journalline',
            name='uuid',
            field=models.UUIDField(db_index=True, editable=False, null=True),
        ),
        migrations.RunPython(populate_uuid, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='account',
            name='uuid',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='accountingperiod',
            name='uuid',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='journalentry',
            name='uuid',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='journalline',
            name='uuid',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
    ]

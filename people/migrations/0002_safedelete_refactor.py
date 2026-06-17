from django.db import migrations, models
from django.utils import timezone


def copy_soft_delete_flags(apps, schema_editor):
    Person = apps.get_model('people', 'Person')
    HistoricalPerson = apps.get_model('people', 'HistoricalPerson')
    deleted_at = timezone.now()

    Person.objects.filter(is_deleted=True).update(deleted=deleted_at)
    HistoricalPerson.objects.filter(is_deleted=True).update(deleted=deleted_at)


class Migration(migrations.Migration):

    dependencies = [
        ('people', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='person',
            name='deleted',
            field=models.DateTimeField(db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='person',
            name='deleted_by_cascade',
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddField(
            model_name='historicalperson',
            name='deleted',
            field=models.DateTimeField(db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='historicalperson',
            name='deleted_by_cascade',
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.RunPython(copy_soft_delete_flags, migrations.RunPython.noop),
        migrations.RemoveIndex(
            model_name='person',
            name='people_pers_is_dele_5172e5_idx',
        ),
        migrations.RemoveField(
            model_name='person',
            name='is_deleted',
        ),
        migrations.RemoveField(
            model_name='historicalperson',
            name='is_deleted',
        ),
        migrations.AddIndex(
            model_name='person',
            index=models.Index(fields=['deleted'], name='people_pers_deleted_4b6f7d_idx'),
        ),
    ]

from django.db import migrations, models
from django.utils import timezone


MODEL_NAMES = [
    'Event',
    'EventSchema',
    'Path',
    'Checkpoint',
    'PersonEventMetadata',
    'CheckpointSchema',
]


def copy_soft_delete_flags(apps, schema_editor):
    deleted_at = timezone.now()
    for model_name in MODEL_NAMES:
        model = apps.get_model('events', model_name)
        model.objects.filter(is_deleted=True).update(deleted=deleted_at)


def deduplicate_checkpoint_schemas(apps, schema_editor):
    checkpoint_schema = apps.get_model('events', 'CheckpointSchema')

    duplicates = (
        checkpoint_schema.objects.values('checkpoint_id', 'event_schema_id')
        .annotate(row_count=models.Count('id'))
        .filter(row_count__gt=1)
    )

    for duplicate in duplicates:
        rows = list(
            checkpoint_schema.objects.filter(
                checkpoint_id=duplicate['checkpoint_id'],
                event_schema_id=duplicate['event_schema_id'],
            ).order_by('-is_deleted', '-id')
        )
        active_rows = [row for row in rows if not row.is_deleted]
        keep = active_rows[0] if active_rows else rows[0]
        checkpoint_schema.objects.filter(
            checkpoint_id=duplicate['checkpoint_id'],
            event_schema_id=duplicate['event_schema_id'],
        ).exclude(id=keep.id).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0002_alter_eventschema_data_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='deleted',
            field=models.DateTimeField(db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='event',
            name='deleted_by_cascade',
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddField(
            model_name='eventschema',
            name='deleted',
            field=models.DateTimeField(db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='eventschema',
            name='deleted_by_cascade',
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddField(
            model_name='path',
            name='deleted',
            field=models.DateTimeField(db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='path',
            name='deleted_by_cascade',
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddField(
            model_name='checkpoint',
            name='deleted',
            field=models.DateTimeField(db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='checkpoint',
            name='deleted_by_cascade',
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddField(
            model_name='personeventmetadata',
            name='deleted',
            field=models.DateTimeField(db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='personeventmetadata',
            name='deleted_by_cascade',
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddField(
            model_name='checkpointschema',
            name='deleted',
            field=models.DateTimeField(db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='checkpointschema',
            name='deleted_by_cascade',
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.RunPython(copy_soft_delete_flags, migrations.RunPython.noop),
        migrations.RunPython(deduplicate_checkpoint_schemas, migrations.RunPython.noop),
        migrations.RemoveIndex(
            model_name='event',
            name='events_even_is_dele_59021f_idx',
        ),
        migrations.RemoveIndex(
            model_name='personeventmetadata',
            name='events_pers_is_dele_c0da06_idx',
        ),
        migrations.RemoveConstraint(
            model_name='checkpointschema',
            name='unique_checkpoint_schema_when_not_deleted',
        ),
        migrations.RemoveField(
            model_name='event',
            name='is_deleted',
        ),
        migrations.RemoveField(
            model_name='eventschema',
            name='is_deleted',
        ),
        migrations.RemoveField(
            model_name='path',
            name='is_deleted',
        ),
        migrations.RemoveField(
            model_name='checkpoint',
            name='is_deleted',
        ),
        migrations.RemoveField(
            model_name='personeventmetadata',
            name='is_deleted',
        ),
        migrations.RemoveField(
            model_name='checkpointschema',
            name='is_deleted',
        ),
        migrations.AddConstraint(
            model_name='checkpointschema',
            constraint=models.UniqueConstraint(
                fields=('checkpoint', 'event_schema'),
                name='unique_checkpoint_schema',
            ),
        ),
    ]

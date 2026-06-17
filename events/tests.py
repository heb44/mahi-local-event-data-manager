from django.core.exceptions import ValidationError
from django.test import TestCase

from events.models import Checkpoint, Event, Path


class RestoreGuardTests(TestCase):
    def test_child_cannot_restore_before_parent(self):
        event = Event.objects.create(name="Event A")
        path = Path.objects.create(name="Path A", event=event, path_description="desc")

        path.delete()
        event.delete()

        with self.assertRaises(ValidationError):
            path.undelete()

    def test_save_does_not_implicitly_restore_deleted_object(self):
        event = Event.objects.create(name="Event A")
        path = Path.objects.create(name="Path A", event=event, path_description="desc")

        path.delete()
        original_deleted = path.deleted

        path.name = "Path B"
        path.save()
        path.refresh_from_db()

        self.assertEqual(path.name, "Path B")
        self.assertEqual(path.deleted, original_deleted)

    def test_queryset_update_restore_is_blocked(self):
        event = Event.objects.create(name="Event A")
        path = Path.objects.create(name="Path A", event=event, path_description="desc")
        checkpoint = Checkpoint.objects.create(name="CP", path=path)

        checkpoint.delete()

        with self.assertRaises(ValidationError):
            Checkpoint.all_objects.filter(pk=checkpoint.pk).update(deleted=None)

from events.forms import EventSchemaPermissionsForm, EventStatusForm
from accounts.models import User
from events.models import EventSchema


class EventFormsTests(TestCase):
    def test_event_status_form_validates_expected_payload(self):
        form = EventStatusForm({'event_id': 1, 'action': 'play'})
        self.assertTrue(form.is_valid())

    def test_event_schema_permissions_form_syncs_checkpoint_permissions(self):
        user = User.objects.create(username='tester')
        event = Event.objects.create(name='Event B')
        path = Path.objects.create(name='Path B', event=event, path_description='desc')
        checkpoint = Checkpoint.objects.create(name='CP B', path=path, user=user)
        schema = EventSchema.objects.create(event=event, column_name='age', data_type='number')

        form = EventSchemaPermissionsForm(
            {
                'checkpoint_id': [checkpoint.id],
                'view': [checkpoint.id],
                'edit': [],
                'entry': [checkpoint.id],
            },
            event=event,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save(schema)

        cp_schema = schema.cp_schemas.get(checkpoint=checkpoint)
        self.assertTrue(cp_schema.can_view)
        self.assertFalse(cp_schema.can_edit)
        self.assertTrue(cp_schema.can_fill)

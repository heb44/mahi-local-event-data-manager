import json
from typing import Any

import magic
from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from people.forms import PersonForm
from people.models import Person

from .models import Checkpoint, CheckpointSchema, Event, EventSchema, Path
from .utils import validate_and_cast_value

User = get_user_model()


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'name',
            'last_start_time',
            'last_stop_time',
            'description',
            'is_active',
        ]

    def clean_last_start_time(self) -> Any:
        last_start_time = self.cleaned_data.get('last_start_time')
        if last_start_time and last_start_time > timezone.now():
            raise forms.ValidationError('زمان شروع رویداد نمی‌تواند در آینده باشد.')
        return last_start_time

    def clean_last_stop_time(self) -> Any:
        last_stop_time = self.cleaned_data.get('last_stop_time')
        last_start_time = self.cleaned_data.get('last_start_time')
        if last_stop_time and last_start_time and last_stop_time < last_start_time:
            raise forms.ValidationError('زمان توقف رویداد نمی‌تواند قبل از زمان شروع آن باشد.')
        return last_stop_time


class EventStatusForm(forms.Form):
    event_id = forms.IntegerField(min_value=1)
    action = forms.ChoiceField(choices=[('pause', 'Pause'), ('play', 'Play')])


class EventSchemaForm(forms.ModelForm):
    class Meta:
        model = EventSchema
        fields = [
            'event',
            'column_name',
            'data_type',
            'is_required',
            'default_value',
            'is_active',
            'metadata_source',
            'metadata_key',
        ]

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        metadata_source = cleaned_data.get('metadata_source')
        metadata_key = cleaned_data.get('metadata_key')
        data_type = cleaned_data.get('data_type')
        default_value = cleaned_data.get('default_value')

        if metadata_source and not metadata_key:
            self.add_error('metadata_key', 'کلید متادیتا نمی‌تواند خالی باشد.')

        if data_type and default_value:
            is_valid, _ = validate_and_cast_value(data_type, default_value)
            if not is_valid:
                self.add_error(
                    'default_value',
                    f"مقدار پیش‌فرض '{default_value}' با نوع داده '{data_type}' سازگار نیست.",
                )

        return cleaned_data


class EventSchemaStatusForm(forms.Form):
    id = forms.IntegerField(min_value=1)
    active = forms.TypedChoiceField(
        choices=[('true', True), ('false', False)],
        coerce=lambda value: value if isinstance(value, bool) else value == 'true',
    )


class EventSchemaPermissionsForm(forms.Form):
    checkpoint_id = forms.ModelMultipleChoiceField(queryset=Checkpoint.objects.none(), required=False)
    view = forms.ModelMultipleChoiceField(queryset=Checkpoint.objects.none(), required=False)
    edit = forms.ModelMultipleChoiceField(queryset=Checkpoint.objects.none(), required=False)
    entry = forms.ModelMultipleChoiceField(queryset=Checkpoint.objects.none(), required=False)

    def __init__(self, *args: Any, event: Event, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        checkpoints = Checkpoint.objects.filter(path__event=event)
        for field_name in ['checkpoint_id', 'view', 'edit', 'entry']:
            self.fields[field_name].queryset = checkpoints

    def save(self, event_schema: EventSchema) -> None:
        selected_checkpoints = self.cleaned_data['checkpoint_id']
        selected_checkpoint_ids = {checkpoint.id for checkpoint in selected_checkpoints}
        existing_checkpoint_ids = set(
            CheckpointSchema.objects.filter(event_schema=event_schema).values_list('checkpoint_id', flat=True)
        )
        view_permissions = {checkpoint.id for checkpoint in self.cleaned_data['view']}
        edit_permissions = {checkpoint.id for checkpoint in self.cleaned_data['edit']}
        fill_permissions = {checkpoint.id for checkpoint in self.cleaned_data['entry']}

        for checkpoint in selected_checkpoints:
            CheckpointSchema.objects.update_or_create(
                checkpoint=checkpoint,
                event_schema=event_schema,
                defaults={
                    'can_view': checkpoint.id in view_permissions,
                    'can_edit': checkpoint.id in edit_permissions,
                    'can_fill': checkpoint.id in fill_permissions,
                },
            )

        checkpoint_ids_to_remove = existing_checkpoint_ids - selected_checkpoint_ids
        if checkpoint_ids_to_remove:
            CheckpointSchema.objects.filter(
                event_schema=event_schema,
                checkpoint_id__in=checkpoint_ids_to_remove,
            ).delete()


class PathForm(forms.ModelForm):
    class Meta:
        model = Path
        fields = [
            'name',
            'event',
            'path_description',
            'allow_duplicate_checkin',
            'enforce_checkpoint_order',
            'is_active',
        ]


class PathStatusForm(forms.Form):
    path_id = forms.IntegerField(min_value=1)
    action = forms.ChoiceField(choices=[('pause', 'Pause'), ('play', 'Play')])


class CheckpointForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        to_field_name='username',
    )

    class Meta:
        model = Checkpoint
        fields = [
            'name',
            'color',
            'path',
            'user',
            'order',
            'location_description',
            'is_mandatory',
            'is_active',
            'allow_duplicate_checkin',
            'latitude',
            'longitude',
        ]


class CheckpointStatusForm(forms.Form):
    id = forms.IntegerField(min_value=1)
    active = forms.TypedChoiceField(
        choices=[('true', True), ('false', False)],
        coerce=lambda value: value if isinstance(value, bool) else value == 'true',
    ) 
    origin = forms.CharField(required=False)


class CheckPointSchemaForm(forms.ModelForm):
    class Meta:
        model = CheckpointSchema
        fields = ['checkpoint', 'can_view', 'can_edit', 'can_fill']

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.event_schema = kwargs.pop('event_schema', None)
        super().__init__(*args, **kwargs)

    def save(self, commit: bool = True) -> CheckpointSchema:
        checkpoint = self.cleaned_data['checkpoint']
        instance, _ = CheckpointSchema.objects.update_or_create(
            checkpoint=checkpoint,
            event_schema=self.event_schema,
            defaults={
                'can_view': self.cleaned_data.get('can_view', False),
                'can_edit': self.cleaned_data.get('can_edit', False),
                'can_fill': self.cleaned_data.get('can_fill', False),
            },
        )
        return instance


class ParticipantForm(PersonForm):
    pem = forms.CharField(required=False)

    def clean_pem(self) -> dict[str, Any]:
        pem = self.cleaned_data.get('pem', '').strip()
        if not pem:
            return {}
        try:
            parsed_pem = json.loads(pem)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError('Invalid participant metadata JSON.') from exc
        if not isinstance(parsed_pem, dict):
            raise forms.ValidationError('Participant metadata must be a JSON object.')
        return parsed_pem


class ParticipantBulkActionForm(forms.Form):
    action = forms.ChoiceField(choices=[('delete', 'Delete'), ('add', 'Add')])
    participant_ids = forms.ModelMultipleChoiceField(queryset=Person.objects.all())


class ParticipantImportForm(forms.Form):
    FILE_TYPES = {
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
    }

    excel_file = forms.FileField()
    name_column = forms.CharField(required=False)
    last_name_column = forms.CharField(required=False)
    phone_number_column = forms.CharField(required=False)
    birth_date_column = forms.CharField(required=False)
    matching_fields = forms.MultipleChoiceField(
        choices=[
            ('name', 'Name'),
            ('last_name', 'Last Name'),
            ('phone_number', 'Phone Number'),
            ('birth_date', 'Birth Date'),
        ]
    )
    metadata_storage = forms.ChoiceField(choices=[('person', 'Person'), ('person_event', 'Person Event')])

    def __init__(self, *args: Any, max_file_size: int, **kwargs: Any) -> None:
        self.max_file_size = max_file_size
        super().__init__(*args, **kwargs)

    def clean_excel_file(self) -> Any:
        excel_file = self.cleaned_data['excel_file']
        mime = magic.Magic(mime=True)
        file_type = mime.from_buffer(excel_file.read(2048))
        excel_file.seek(0)

        if file_type not in self.FILE_TYPES:
            raise forms.ValidationError('Invalid file format.')

        if excel_file.size > self.max_file_size:
            raise forms.ValidationError('File too large.')

        return excel_file

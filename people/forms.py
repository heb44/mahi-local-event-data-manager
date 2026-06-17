import json

import magic
from django import forms

from core.utils import convert_jalali_to_gregorian

from .models import Person


class PersonForm(forms.ModelForm):
    phone = forms.CharField(required=False)
    birth_date = forms.CharField(required=False)
    metadata = forms.CharField(required=False)

    class Meta:
        model = Person
        fields = ['name', 'last_name']

    def clean_birth_date(self):
        birth_date = self.cleaned_data.get('birth_date', '').strip()
        if not birth_date:
            return None
        return convert_jalali_to_gregorian(birth_date)

    def clean_metadata(self):
        metadata = self.cleaned_data.get('metadata', '').strip()
        if not metadata:
            return {}

        try:
            parsed_metadata = json.loads(metadata)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError('Invalid metadata JSON.') from exc

        if not isinstance(parsed_metadata, dict):
            raise forms.ValidationError('Metadata must be a JSON object.')

        return parsed_metadata

    def save(self, commit=True):
        person = super().save(commit=False)
        person.phone_number = self.cleaned_data.get('phone', '').strip()
        person.birth_date = self.cleaned_data.get('birth_date')
        person.metadata = self.cleaned_data.get('metadata', {})
        if commit:
            person.save()
        return person


class PersonBulkActionForm(forms.Form):
    action = forms.ChoiceField(choices=[('delete', 'Delete')])
    person_ids = forms.ModelMultipleChoiceField(
        queryset=Person.objects.all(),
    )


class PersonImportForm(forms.Form):
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
        ],
    )

    def __init__(self, *args, max_file_size, **kwargs):
        self.max_file_size = max_file_size
        super().__init__(*args, **kwargs)

    def clean_excel_file(self):
        excel_file = self.cleaned_data['excel_file']

        mime = magic.Magic(mime=True)
        file_type = mime.from_buffer(excel_file.read(2048))
        excel_file.seek(0)

        if file_type not in self.FILE_TYPES:
            raise forms.ValidationError('Invalid file format.')

        if excel_file.size > self.max_file_size:
            raise forms.ValidationError('File too large.')

        return excel_file

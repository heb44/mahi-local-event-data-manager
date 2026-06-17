from django import forms

from events.models import EventSchema

from core.utils import convert_jalali_to_gregorian

from .models import CheckIn


class CheckInSearchForm(forms.Form):
    id = forms.IntegerField(min_value=1)
    cp_id = forms.IntegerField(min_value=1)


class CheckInPerformForm(forms.Form):
    ci = forms.IntegerField(min_value=1)
    action = forms.ChoiceField(choices=[('approve', 'Approve'), ('reject', 'Reject')])
    description = forms.CharField(required=False)

    def __init__(self, *args, event=None, user=None, **kwargs):
        self.event = event
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        schema_values = {}

        if not self.event or not self.user:
            cleaned_data['schema_values'] = schema_values
            return cleaned_data

        schemas = {
            str(schema.id): schema
            for schema in EventSchema.objects.with_user_permissions(self.event, self.user)
        }

        for key in self.data:
            if not key.startswith('field_'):
                continue

            schema_id = key.split('_', 1)[1]
            schema = schemas.get(schema_id)
            if not schema:
                continue

            try:
                schema_values[schema_id] = self._clean_schema_value(schema, key)
            except forms.ValidationError as exc:
                self.add_error(None, exc)

        cleaned_data['schema_values'] = schema_values
        return cleaned_data

    def _clean_schema_value(self, schema, key):
        raw_value = self.data.get(key, '')

        if schema.data_type == 'boolean':
            return raw_value == 'True'

        raw_value = raw_value.strip()
        if raw_value == '':
            return None

        if schema.data_type == 'text':
            return raw_value
        if schema.data_type == 'number':
            try:
                return float(raw_value)
            except (TypeError, ValueError) as exc:
                raise forms.ValidationError(f'Invalid value for {schema.column_name}.') from exc
        if schema.data_type == 'date':
            try:
                return convert_jalali_to_gregorian(raw_value)
            except Exception as exc:
                raise forms.ValidationError(f'Invalid value for {schema.column_name}.') from exc

        return raw_value


class CheckInBulkActionForm(forms.Form):
    action = forms.ChoiceField(choices=[('delete', 'Delete')])
    selected_ids = forms.ModelMultipleChoiceField(
        queryset=CheckIn.objects.all(),
    )

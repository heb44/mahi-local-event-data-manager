from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password

from .models import UserSettings

User = get_user_model()


class UserCreateForm(forms.ModelForm):
    password = forms.CharField()

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']

    def clean_password(self):
        password = self.cleaned_data['password']
        validate_password(password)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class UserUpdateForm(forms.ModelForm):
    password = forms.CharField(required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            validate_password(password, self.instance)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


class UserChangePasswordForm(forms.Form):
    new_password = forms.CharField()
    confirm_password = forms.CharField()

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')

        if new_password and confirm_password and new_password != confirm_password:
            self.add_error('confirm_password', 'Passwords do not match.')

        if new_password:
            validate_password(new_password, self.user)

        return cleaned_data

    def save(self):
        self.user.set_password(self.cleaned_data['new_password'])
        self.user.save(update_fields=['password'])
        return self.user


class UserAssignRoleForm(forms.Form):
    roles = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
    )


class RoleForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name']


class RolePermissionsForm(forms.Form):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.none(),
        required=False,
    )

    def __init__(self, *args, allowed_permissions=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['permissions'].queryset = (
            allowed_permissions if allowed_permissions is not None else Permission.objects.none()
        )


class GeneralSettingsForm(forms.Form):
    digits_type = forms.ChoiceField(
        choices=[('en', 'English'), ('fa', 'Persian')],
        required=False,
    )

    def clean_digits_type(self):
        return self.cleaned_data.get('digits_type') or 'en'


class CheckInSettingsForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = [
            'ci_auto_submit',
            'ci_auto_submit_delay',
            'ci_auto_submit_char_num',
            'enable_barcode_scanner',
            'enable_audio_feedback',
        ]

from .models import GlobalSettings
from accounts.models import UserSettings

def global_settings(request):
    use_persian_digits = False
    if request.user.is_authenticated:
        try:
            user_settings, _ = UserSettings.objects.get_or_create(user=request.user)
            use_persian_digits = user_settings.use_persian_digits
        except Exception:
            pass

    return {
        'global_settings': GlobalSettings.get_solo(),
        'use_persian_digits': use_persian_digits,
    }
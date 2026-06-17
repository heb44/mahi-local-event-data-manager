from .models import GlobalSettings

def global_settings(request):

    return {
        'global_settings': GlobalSettings.get_solo()
    }
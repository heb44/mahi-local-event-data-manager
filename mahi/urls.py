from django.contrib import admin
from django.urls import path, include
from operations.views import dashboard 
from django.conf import settings 

urlpatterns = [
    path('admin/', admin.site.urls),
    
    path('', dashboard, name='root_dashboard'),

    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('people/', include('people.urls', namespace='people')),
    path('events/', include('events.urls', namespace='events')),
    path('ops/', include('operations.urls', namespace='operations')),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]
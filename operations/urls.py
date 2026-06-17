from django.urls import path
from . import views

app_name = 'operations'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),

    path('checkins/checkin/', views.checkin, name='checkin'),
    path('checkins/search/', views.checkin_search, name='checkin_search'),
    path('checkins/perform/', views.checkin_perform, name='checkin_perform'),

    path('checkins/', views.checkins_list, name='checkins'),
    path('checkins/delete/<int:checkin_id>/', views.checkin_delete, name='checkin_delete'),
    path('checkins/bulk-action/', views.checkin_bulk_action, name='checkin_bulk_action'),

    path('history/<int:person_id>/', views.person_checkin_history, name='person_history'),
]
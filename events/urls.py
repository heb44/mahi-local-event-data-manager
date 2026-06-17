from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('', views.events_list, name='list'),
    path('create/', views.event_create, name='create'),
    path('toggle/', views.toggle_event_status, name='toggle_status'),
    path('<int:event_id>/', views.event_detail, name='detail'),
    path('edit/<int:event_id>/', views.event_edit, name='edit'),
    path('delete/<int:event_id>/', views.event_delete, name='delete'),

    path('<int:event_id>/schema/', views.event_schema, name='schema'),
    path('<int:event_id>/schema/toggle/', views.toggle_event_schema_status, name='schema_toggle_status'),
    path('<int:event_id>/schema/create/', views.event_schema_create, name='schema_create'),
    path('<int:event_id>/schema/edit/<int:schema_id>/', views.event_schema_edit, name='schema_edit'),
    path('<int:event_id>/schema/delete/<int:schema_id>/', views.event_schema_delete, name='schema_delete'),
    
    path('schema/', views.schema_redirect, name='schema_redirect'),

    path('paths/', views.paths_list, name='paths'),
    path('paths/toggle/', views.toggle_path_status, name='path_toggle_status'),
    path('paths/create/', views.path_create, name='path_create'),
    path('paths/delete/<int:path_id>/', views.path_delete, name='path_delete'),
    path('paths/edit/<int:path_id>/', views.path_edit, name='path_edit'),
    path('paths/<int:path_id>/', views.path_detail, name='path_detail'),

    path('checkpoints/', views.checkpoints_list, name='checkpoints'),
    path('checkpoints/create/', views.checkpoint_create, name='checkpoint_create'),
    path('checkpoints/delete/<int:cp_id>/', views.checkpoint_delete, name='checkpoint_delete'),
    path('checkpoints/edit/<int:cp_id>/', views.checkpoint_edit, name='checkpoint_edit'),
    path('checkpoints/toggle/', views.toggle_checkpoint_status, name='checkpoint_toggle_status'),

    path('<int:event_id>/parts/', views.participants_list, name='participants'),
    path('<int:event_id>/parts/add/', views.participant_add, name='participant_add'),
    path('<int:event_id>/parts/create/', views.participant_create, name='participant_create'),
    path('<int:event_id>/parts/bulk-action/', views.participant_bulk_action, name='participant_bulk_action'),
    path('<int:event_id>/parts/delete/<int:participant_id>/', views.participant_delete, name='participant_delete'),
    path('<int:event_id>/parts/edit/<int:participant_id>/', views.participant_edit, name='participant_edit'),
    path('<int:event_id>/import/', views.import_persons_to_event, name='participant_import'),

    path('participants/', views.participants_redirect, name='participants_redirect'),
]
from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('users/', views.users_list, name='users'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/edit/<int:user_id>/', views.user_edit, name='user_edit'),
    path('users/toggle/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'),
    path('users/assign-role/<int:user_id>/', views.user_assign_role_view, name='user_assign_role'),
    path('users/change-password/', views.user_change_password, name='user_change_password'),
    
    path('user-autocomplete/', views.user_autocomplete, name='user_autocomplete'),

    path('roles/', views.role_list_view, name='role_list'),
    path('roles/create/', views.role_create_view, name='role_create'),
    path('roles/<int:pk>/update/', views.role_update_view, name='role_update'),
    path('roles/<int:pk>/delete/', views.role_delete_view, name='role_delete'),
    path('roles/<int:pk>/permissions/', views.role_permissions_update_view, name='role_permissions_update'),

    path('settings/general/', views.settings_general, name='settings_general'),
    path('settings/check_in/', views.settings_checkin, name='settings_checkin'),
]
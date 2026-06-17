from django.urls import path
from . import views

app_name = 'people'

urlpatterns = [
    path('', views.persons_list, name='list'),
    path('create/', views.person_create, name='create'),
    path('import/', views.import_persons_general, name='import_general'),
    path('delete/<int:person_id>/', views.person_delete, name='delete'),
    path('edit/<int:person_id>/', views.person_edit, name='edit'),
    path('bulk-action/', views.person_bulk_action, name='bulk_action'),
]
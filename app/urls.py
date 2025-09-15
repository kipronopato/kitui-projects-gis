from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('projects/', views.ProjectListView.as_view(), name='project_list'),
    path('projects/map/', views.project_map_view, name='project_map'),
    path('projects/<int:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('projects/<int:project_id>/report/', views.submit_report, name='submit_report'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
]
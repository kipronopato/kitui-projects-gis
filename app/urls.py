from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect

urlpatterns = [
    # Home & Informational Pages
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    #path('debug-data/', views.debug_data, name='debug_data'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # GeoJSON API Endpoints
    path('api/counties/geojson/', views.counties_geojson, name='counties_geojson'),
    path('api/subcounties/geojson/', views.subcounties_geojson, name='subcounties_geojson'),
    path('api/wards/geojson/', views.wards_geojson, name='wards_geojson'),
    path('api/projects/geojson/', views.projects_geojson, name='projects_geojson'),
    
    # Analytics
    path('spatial-statistics/', views.spatial_statistics, name='spatial_statistics'),

    # Project Management
    path('projects/', views.ProjectListView.as_view(), name='project_list'),
    path('projects/map/', views.project_map_view, name='project_map'),
    path('projects/download-project-report/', views.download_project_report, name='download_project_report'),
    path('projects/<int:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('projects/<int:project_id>/report/', views.submit_report, name='submit_report'),
    
    # Chartboard and Timeline
    path('project/<int:project_id>/chartboard/', views.project_chartboard, name='project_chartboard'),
    path('project/<int:project_id>/chat/send/', views.send_chat_message, name='send_chat_message'),
    path('project/<int:project_id>/chat/messages/', views.get_chat_messages, name='get_chat_messages'),
    path('project/<int:project_id>/chat/mark-read/', views.mark_messages_as_read, name='mark_messages_read'),
    
    # Authentication
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
]
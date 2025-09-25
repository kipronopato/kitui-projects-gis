from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('counties-geojson/', views.counties_geojson, name='counties_geojson'),
    path('subcounties-geojson/', views.subcounties_geojson, name='subcounties_geojson'),
    path('wards-geojson/', views.wards_geojson, name='wards_geojson'),
    path('project-locations-geojson/', views.project_locations_geojson, name='project_locations_geojson'),
    path('spatial-statistics/', views.spatial_statistics, name='spatial_statistics'),
    path('counties-geojson/', views.counties_geojson, name='counties_geojson'),
    path('subcounties-geojson/', views.subcounties_geojson, name='subcounties_geojson'),
    path('wards-geojson/', views.wards_geojson, name='wards_geojson'),
    #path('admin-geojson/', views.get_admin_geojson, name='get_admin_geojson'),
    path('dashboard/', views.dashboard, name='dashboard'),
    #path("get-admin-geojson/", views.get_admin_geojson, name="get_admin_geojson"),
    path('projects/', views.ProjectListView.as_view(), name='project_list'),
    path('projects/map/', views.project_map_view, name='project_map'),
    path('projects/<int:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('projects/<int:project_id>/report/', views.submit_report, name='submit_report'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
]
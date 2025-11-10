from django.shortcuts import render, get_object_or_404
from django.contrib.gis.geos import Point
from django.http import JsonResponse
from django.views.generic import ListView, DetailView
from django.db.models import Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils.timezone import now
from .models import Project, ProjectUpdate, CitizenReport
from .forms import CitizenReportForm
from django.db.models import Q
from django.db.models import Sum, Value, DecimalField, Count, Q
from django.core.serializers import serialize
import json
from decimal import Decimal
from django.db.models import Sum, Count, Avg, Q
from collections import Counter
from django.db.models import Q, Count, Sum, Avg, F, ExpressionWrapper, FloatField
from django.db.models.functions import TruncMonth, ExtractYear
from django.contrib.postgres.aggregates import StringAgg
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q, Sum, Count, Avg, Max, Min, F, ExpressionWrapper, DurationField
from django.db.models.functions import ExtractYear, TruncMonth
from django.db.models import Avg, Sum, Count, Min, Max, StdDev
from datetime import timedelta
from django.contrib.gis.db.models.functions import Transform
from .models import Project, ProjectUpdate, CitizenReport, KenyaCounty, KenyaSubCounty, Kenyawards
from django.contrib.gis.db.models.functions import AsGeoJSON
import json
from decimal import Decimal
from datetime import timedelta
from django.db.models import Q, Count, Sum, Avg, Min, Max
from django.db.models.functions import TruncMonth, TruncYear, ExtractYear
from django.db.models.expressions import ExpressionWrapper, F, Value, Case, When
from django.db.models.fields import FloatField, DurationField
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.contrib.gis.db.models import Union
from .models import Project, ProjectUpdate, CitizenReport, KenyaCounty, KenyaSubCounty, Kenyawards

# views.py
from django.db.models import Q, Sum, Avg, Min, Max, Count, Case, When, F
from django.db.models.functions import ExtractYear, TruncMonth
from django.db.models import DurationField, ExpressionWrapper, FloatField
from django.contrib.gis.db.models import Union
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import json
from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from app.models import Project, KenyaCounty, KenyaSubCounty, Kenyawards, ProjectUpdate, CitizenReport

def _clean_get(request, name):
    """Return single GET param; treat 'None' or empty as None."""
    v = request.GET.get(name)
    return None if (v is None or v == "None" or v == "") else v

def _clean_getlist(request, name):
    """Return list cleaned of empty/'None' entries."""
    return [v for v in request.GET.getlist(name) if v and v != "None"]

def _decimal_to_float(obj):
    """Recursively convert Decimal objects to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_decimal_to_float(v) for v in obj]
    else:
        return obj

def debug_data(request):
    """Debug view to check what data exists"""
    projects = Project.objects.all()
    
    debug_info = {
        'total_projects': projects.count(),
        'projects_sample': list(projects.values('id', 'name', 'county', 'status', 'sector', 'budget', 'start_date', 'end_date')[:10]),
        'counties': list(projects.values_list('county', flat=True).distinct()),
        'sectors': list(projects.values_list('sector', flat=True).distinct()),
        'statuses': list(projects.values_list('status', flat=True).distinct()),
        'fiscal_years': list(projects.dates("start_date", "year").order_by("-start_date").values_list('start_date__year', flat=True).distinct()),
    }
    
    return JsonResponse(debug_info)

def home(request):
    """Optimized dashboard view with efficient queries for large datasets"""
    try:
        print("=== DASHBOARD LOADING ===")
        
        # Start with basic project query
        projects = Project.objects.all()
        print(f"Total projects in database: {projects.count()}")

        # ---------------- Basic Filters ----------------
        selected_county = _clean_get(request, "county")
        selected_year = _clean_get(request, "year")
        selected_statuses = _clean_getlist(request, "status")
        selected_sectors = _clean_getlist(request, "sector")
        search_query = _clean_get(request, "search")

        print(f"Filters - County: {selected_county}, Year: {selected_year}")
        print(f"Statuses: {selected_statuses}, Sectors: {selected_sectors}")

        # Apply basic filters
        if selected_county:
            projects = projects.filter(county__icontains=selected_county)
            print(f"After county filter: {projects.count()}")
        
        if selected_year:
            try:
                projects = projects.filter(start_date__year=int(selected_year))
                print(f"After year filter: {projects.count()}")
            except (ValueError, TypeError):
                pass
        
        if selected_statuses:
            projects = projects.filter(status__in=selected_statuses)
            print(f"After status filter: {projects.count()}")
        
        if selected_sectors:
            projects = projects.filter(sector__in=selected_sectors)
            print(f"After sector filter: {projects.count()}")

        # Search functionality
        if search_query:
            projects = projects.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(sector__icontains=search_query) |
                Q(county__icontains=search_query)
            )
            print(f"After search filter: {projects.count()}")

        # ---------------- Core Metrics with Efficient Queries ----------------
        current_date = timezone.now().date()
        
        # Use aggregation to get multiple metrics in single query
        metrics = projects.aggregate(
            total_projects=Count('id'),
            total_budget=Sum('budget'),
            completed_projects=Count('id', filter=Q(status='completed')),
            ongoing_projects=Count('id', filter=Q(status='ongoing')),
            planned_projects=Count('id', filter=Q(status='planned')),
            delayed_projects=Count('id', filter=Q(status='delayed'))
        )
        
        total_projects = metrics['total_projects'] or 0
        total_budget = float(metrics['total_budget'] or 0)  # Convert Decimal to float
        completed_projects = metrics['completed_projects'] or 0
        ongoing_projects = metrics['ongoing_projects'] or 0
        planned_projects = metrics['planned_projects'] or 0
        delayed_projects = metrics['delayed_projects'] or 0

        print(f"Metrics - Total: {total_projects}, Budget: {total_budget}")

        # Calculate overdue projects
        overdue_projects = projects.filter(
            Q(status="ongoing") | Q(status="planned"),
            end_date__lt=current_date
        ).count()

        # Calculate rates
        completion_rate = round((completed_projects / total_projects * 100), 1) if total_projects else 0
        ongoing_rate = round((ongoing_projects / total_projects * 100), 1) if total_projects else 0

        # Upcoming deadlines (next 30 days)
        upcoming_deadlines = projects.filter(
            Q(status="ongoing") | Q(status="planned"),
            end_date__gte=current_date,
            end_date__lte=current_date + timedelta(days=30),
        ).count()

        # Enhanced budget analytics
        budget_stats = projects.aggregate(
            avg_budget=Avg("budget"),
            min_budget=Min("budget"),
            max_budget=Max("budget"),
            total_budget=Sum("budget")
        )
        
        # Convert Decimal values to float in budget_stats
        budget_stats = _decimal_to_float(budget_stats)

        # Status analytics
        status_counts_chart = {}
        status_distribution = projects.values("status").annotate(
            count=Count("id")
        ).order_by("status")
        
        for item in status_distribution:
            status_counts_chart[item["status"]] = item["count"]

        # Ensure all statuses are represented
        for status in ['planned', 'ongoing', 'completed', 'delayed']:
            if status not in status_counts_chart:
                status_counts_chart[status] = 0

        # Sector analytics
        sector_data_chart = []
        sector_analytics = projects.values("sector").annotate(
            count=Count("id")
        ).order_by("-count")[:10]

        for item in sector_analytics:
            sector_data_chart.append({
                "sector": item["sector"] or "Not Specified",
                "count": item["count"]
            })

        # County analytics - FIX: Convert Decimal to float for JSON serialization
        county_stats = []
        county_analytics = projects.values("county").annotate(
            count=Count("id"),
            total_budget=Sum("budget")
        ).order_by("-count")[:15]

        for item in county_analytics:
            county_stats.append({
                "county": item["county"],
                "count": item["count"],
                "total_budget": float(item["total_budget"] or 0)  # Convert Decimal to float
            })

        # Recent projects with limit
        recent_projects = projects.order_by("-start_date")[:5]
        highest_budget_projects = projects.order_by("-budget")[:5]

        # Recent activity
        recent_updates = ProjectUpdate.objects.select_related("project").order_by("-created_at")[:5]

        # ---------------- Dropdown Data ----------------
        fiscal_years = list(Project.objects.dates("start_date", "year").order_by("-start_date").values_list('start_date__year', flat=True).distinct())
        status_choices = [choice[0] for choice in Project.STATUS_CHOICES]
        status_labels = dict(Project.STATUS_CHOICES)

        # Get sectors and counties from Project data (more reliable)
        sectors = list(Project.objects.exclude(sector__isnull=True).exclude(sector="")
                    .values_list("sector", flat=True).distinct().order_by("sector"))
        
        counties_from_projects = list(Project.objects.exclude(county__isnull=True).exclude(county="")
                    .values_list("county", flat=True).distinct().order_by("county"))
        
        # Try to get counties from KenyaCounty model, fallback to projects
        try:
            counties_from_model = list(KenyaCounty.objects.exclude(county__isnull=True)
                        .values_list("county", flat=True).distinct().order_by("county"))
            counties = counties_from_model if counties_from_model else counties_from_projects
        except Exception as e:
            print(f"Error loading counties from model: {e}")
            counties = counties_from_projects

        print(f"Available counties: {len(counties)}")
        print(f"Available sectors: {len(sectors)}")

        # ---------------- GeoJSON Generation ----------------
        map_projects = projects.filter(
            Q(location__isnull=False) | 
            Q(latitude__isnull=False, longitude__isnull=False)
        )[:500]  # Increased limit
        
        features = []
        for project in map_projects:
            point_geom = None
            
            # Try multiple location sources
            if project.location and hasattr(project.location, 'x') and hasattr(project.location, 'y'):
                point_geom = {
                    "type": "Point",
                    "coordinates": [float(project.location.x), float(project.location.y)]
                }
            elif project.latitude and project.longitude:
                try:
                    point_geom = {
                        "type": "Point",
                        "coordinates": [float(project.longitude), float(project.latitude)]
                    }
                except (TypeError, ValueError):
                    continue
            
            if point_geom:
                features.append({
                    "type": "Feature",
                    "geometry": point_geom,
                    "properties": {
                        "id": project.id,
                        "name": project.name,
                        "county": project.county or "",
                        "status": project.status,
                        "sector": project.sector or "",
                        "budget": float(project.budget) if project.budget else 0,  # Convert Decimal to float
                    },
                })

        geojson = {
            "type": "FeatureCollection", 
            "features": features,
            "metadata": {
                "total_projects": len(features),
                "total_available": total_projects
            }
        }

        print(f"Generated {len(features)} map features")

        # ---------------- Context for Template ----------------
        context = {
            # Core metrics
            "total_projects": total_projects,
            "total_budget": total_budget,
            "completion_rate": completion_rate,
            "ongoing_rate": ongoing_rate,
            "overdue_projects": overdue_projects,
            "upcoming_deadlines": upcoming_deadlines,
            "current_date": current_date,
            
            # Analytics
            "budget_stats": budget_stats,
            "recent_projects": recent_projects,
            "highest_budget_projects": highest_budget_projects,
            "recent_updates": recent_updates,
            
            # Filter options
            "fiscal_years": fiscal_years,
            "status_choices": status_choices,
            "status_labels": status_labels,
            "sectors": sectors,
            "counties": counties,
            "selected_county": selected_county or "",
            
            # JSON data for JavaScript
            "geojson": json.dumps(geojson),
            
            # CHART DATA
            "status_counts_json": json.dumps(status_counts_chart),
            "sector_data_json": json.dumps(sector_data_chart),
            "county_stats_json": json.dumps(county_stats),  # Now safe to serialize
            
            # Current filter values
            "selected_year": selected_year or "",
            "selected_statuses": selected_statuses,
            "selected_sectors": selected_sectors,
            "search_query": search_query or "",
        }
        
        print("=== DASHBOARD LOADED SUCCESSFULLY ===")
        return render(request, "app/home.html", context)
        
    except Exception as e:
        print(f"Critical error in home view: {e}")
        import traceback
        traceback.print_exc()
        
        return render(request, "app/home.html", {
            "total_projects": 0,
            "total_budget": 0,
            "completion_rate": 0,
            "overdue_projects": 0,
            "upcoming_deadlines": 0,
            "counties": [],
            "sectors": [],
            "status_choices": [],
            "status_labels": {},
            "fiscal_years": [],
            "error": f"An error occurred while loading the dashboard: {str(e)}"
        })

# Enhanced API endpoints with error handling and CORS support
@csrf_exempt
def counties_geojson(request):
    """Enhanced counties GeoJSON with project statistics"""
    try:
        print("Loading counties GeoJSON...")
        
        # Check if KenyaCounty model has data
        if not KenyaCounty.objects.exists():
            return JsonResponse({
                "type": "FeatureCollection",
                "features": []
            })
            
        counties = KenyaCounty.objects.all()
        selected_counties = _clean_getlist(request, "county")
        
        if selected_counties:
            counties = counties.filter(county__in=selected_counties)
        
        features = []
        current_date = timezone.now().date()
        
        for county in counties:
            # Get projects for this county
            projects_in_county = Project.objects.filter(county__icontains=county.county)
            project_count = projects_in_county.count()
            
            # Get comprehensive stats
            stats = projects_in_county.aggregate(
                total_budget=Sum('budget'),
                completed=Count('id', filter=Q(status='completed')),
                ongoing=Count('id', filter=Q(status='ongoing')),
                delayed=Count('id', filter=Q(status='delayed'))
            )
            
            # Convert geometry safely
            geometry_data = None
            if county.geom:
                try:
                    geometry_data = json.loads(county.geom.geojson)
                except Exception as e:
                    print(f"Error parsing geometry for county {county.county}: {e}")
                    continue
            
            feature = {
                "type": "Feature",
                "geometry": geometry_data,
                "properties": {
                    "id": county.id,
                    "county": county.county,
                    "pop_2009": county.pop_2009,
                    "project_count": project_count,
                    "total_budget": float(stats['total_budget'] or 0),  # Convert Decimal to float
                    "completed_projects": stats['completed'] or 0,
                    "ongoing_projects": stats['ongoing'] or 0,
                    "delayed_projects": stats['delayed'] or 0,
                    "completion_rate": round((stats['completed'] / project_count * 100), 1) if project_count else 0,
                }
            }
            features.append(feature)
        
        response_data = {
            "type": "FeatureCollection",
            "features": features
        }
        
        print(f"Returning {len(features)} county features")
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"Error in counties_geojson: {e}")
        return JsonResponse({
            "type": "FeatureCollection", 
            "features": [],
            "error": str(e)
        }, status=500)

@csrf_exempt
def subcounties_geojson(request):
    """Enhanced subcounties GeoJSON"""
    try:
        print("Loading subcounties GeoJSON...")
        
        # Check if KenyaSubCounty model has data
        if not KenyaSubCounty.objects.exists():
            return JsonResponse({
                "type": "FeatureCollection",
                "features": []
            })
            
        subcounties = KenyaSubCounty.objects.all()
        selected_counties = _clean_getlist(request, "county")
        
        if selected_counties:
            subcounties = subcounties.filter(county__in=selected_counties)
        
        features = []
        
        for subcounty in subcounties:
            projects_in_subcounty = Project.objects.filter(county__icontains=subcounty.county)
            project_count = projects_in_subcounty.count()
            
            stats = projects_in_subcounty.aggregate(
                total_budget=Sum('budget'),
                completed=Count('id', filter=Q(status='completed'))
            )
            
            # Convert geometry safely
            geometry_data = None
            if subcounty.geom:
                try:
                    geometry_data = json.loads(subcounty.geom.geojson)
                except Exception as e:
                    print(f"Error parsing geometry for subcounty {subcounty.subcounty}: {e}")
                    continue
            
            feature = {
                "type": "Feature",
                "geometry": geometry_data,
                "properties": {
                    "id": subcounty.id,
                    "subcounty": subcounty.subcounty,
                    "county": subcounty.county,
                    "project_count": project_count,
                    "total_budget": float(stats['total_budget'] or 0),  # Convert Decimal to float
                    "completed_projects": stats['completed'] or 0,
                }
            }
            features.append(feature)
        
        response_data = {
            "type": "FeatureCollection",
            "features": features
        }
        
        print(f"Returning {len(features)} subcounty features")
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"Error in subcounties_geojson: {e}")
        return JsonResponse({
            "type": "FeatureCollection", 
            "features": [],
            "error": str(e)
        }, status=500)

@csrf_exempt
def wards_geojson(request):
    """Enhanced wards GeoJSON"""
    try:
        print("Loading wards GeoJSON...")
        
        # Check if Kenyawards model has data
        if not Kenyawards.objects.exists():
            return JsonResponse({
                "type": "FeatureCollection",
                "features": []
            })
            
        wards = Kenyawards.objects.all()
        selected_counties = _clean_getlist(request, "county")
        
        if selected_counties:
            wards = wards.filter(county__in=selected_counties)
        
        features = []
        
        for ward in wards:
            projects_in_ward = Project.objects.filter(county__icontains=ward.county)
            project_count = projects_in_ward.count()
            
            # Convert geometry safely
            geometry_data = None
            if ward.geom:
                try:
                    geometry_data = json.loads(ward.geom.geojson)
                except Exception as e:
                    print(f"Error parsing geometry for ward {ward.ward}: {e}")
                    continue
            
            feature = {
                "type": "Feature",
                "geometry": geometry_data,
                "properties": {
                    "id": ward.id,
                    "ward": ward.ward,
                    "subcounty": ward.subcounty,
                    "county": ward.county,
                    "project_count": project_count,
                }
            }
            features.append(feature)
        
        response_data = {
            "type": "FeatureCollection",
            "features": features
        }
        
        print(f"Returning {len(features)} ward features")
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"Error in wards_geojson: {e}")
        return JsonResponse({
            "type": "FeatureCollection", 
            "features": [],
            "error": str(e)
        }, status=500)

@csrf_exempt
def projects_geojson(request):
    """API endpoint for project locations with enhanced filtering"""
    try:
        print("Loading projects GeoJSON...")
        
        projects = Project.objects.all()
        
        # Apply filters
        selected_county = _clean_get(request, "county")
        selected_statuses = _clean_getlist(request, "status")
        selected_sectors = _clean_getlist(request, "sector")
        selected_year = _clean_get(request, "year")
        
        if selected_county:
            projects = projects.filter(county__icontains=selected_county)
        if selected_statuses:
            projects = projects.filter(status__in=selected_statuses)
        if selected_sectors:
            projects = projects.filter(sector__in=selected_sectors)
        if selected_year:
            projects = projects.filter(start_date__year=selected_year)
        
        # Get projects with coordinates
        projects_with_coords = projects.filter(
            Q(location__isnull=False) | 
            Q(latitude__isnull=False, longitude__isnull=False)
        )
        
        features = []
        
        for project in projects_with_coords:
            point_geom = None
            
            if project.location and hasattr(project.location, 'x') and hasattr(project.location, 'y'):
                point_geom = {
                    "type": "Point",
                    "coordinates": [float(project.location.x), float(project.location.y)]
                }
            elif project.latitude and project.longitude:
                try:
                    point_geom = {
                        "type": "Point",
                        "coordinates": [float(project.longitude), float(project.latitude)]
                    }
                except (TypeError, ValueError):
                    continue
            
            if point_geom:
                # Calculate if project is overdue
                current_date = timezone.now().date()
                is_overdue = project.status in ['ongoing', 'planned'] and project.end_date and project.end_date < current_date
                
                features.append({
                    "type": "Feature",
                    "geometry": point_geom,
                    "properties": {
                        "id": project.id,
                        "name": project.name,
                        "status": project.status,
                        "county": project.county or "",
                        "sector": project.sector or "",
                        "budget": float(project.budget) if project.budget else 0,  # Convert Decimal to float
                        "start_date": project.start_date.isoformat() if project.start_date else None,
                        "end_date": project.end_date.isoformat() if project.end_date else None,
                        "is_overdue": is_overdue,
                        "description": project.description or "",
                    }
                })
        
        response_data = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "total_projects": len(features),
                "filters_applied": {
                    "county": selected_county,
                    "year": selected_year,
                    "statuses": selected_statuses,
                    "sectors": selected_sectors
                }
            }
        }
        
        print(f"Returning {len(features)} project features")
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"Error in projects_geojson: {e}")
        return JsonResponse({
            "type": "FeatureCollection", 
            "features": [],
            "error": str(e)
        }, status=500)

@csrf_exempt
def spatial_statistics(request):
    """Comprehensive project analytics"""
    try:
        projects = Project.objects.all()
        
        # Apply filters if any
        selected_counties = _clean_getlist(request, "county")
        selected_sectors = _clean_getlist(request, "sector")
        
        if selected_counties:
            projects = projects.filter(county__in=selected_counties)
        if selected_sectors:
            projects = projects.filter(sector__in=selected_sectors)
        
        # Performance metrics
        performance_metrics = projects.aggregate(
            total_projects=Count('id'),
            total_budget=Sum('budget'),
            avg_budget=Avg('budget'),
            completion_rate=Avg(Case(When(status='completed', then=1), default=0, output_field=FloatField())),
        )
        
        # Convert Decimal values to float
        performance_metrics = _decimal_to_float(performance_metrics)
        
        # Risk analysis
        current_date = timezone.now().date()
        risk_analysis = {
            'overdue_projects': projects.filter(
                Q(status='ongoing') | Q(status='planned'),
                end_date__lt=current_date
            ).count(),
            'delayed_projects': projects.filter(status='delayed').count()
        }
        
        # Sector analysis
        sector_analysis = list(projects.values('sector').annotate(
            count=Count('id'),
            total_budget=Sum('budget'),
            avg_budget=Avg('budget')
        ).order_by('-total_budget')[:10])
        
        # Convert Decimal values to float in sector_analysis
        sector_analysis = _decimal_to_float(sector_analysis)
        
        # County analysis
        county_analysis = list(projects.values('county').annotate(
            count=Count('id'),
            total_budget=Sum('budget')
        ).order_by('-count')[:10])
        
        # Convert Decimal values to float in county_analysis
        county_analysis = _decimal_to_float(county_analysis)
        
        return JsonResponse({
            'performance_metrics': performance_metrics,
            'risk_analysis': risk_analysis,
            'sector_analysis': sector_analysis,
            'county_analysis': county_analysis,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        print(f"Error in spatial_statistics: {e}")
        return JsonResponse({"error": str(e)}, status=500)

# Fallback API endpoints for when spatial data is not available
@csrf_exempt
def fallback_counties_data(request):
    """Fallback endpoint that returns basic county data from Project model"""
    try:
        county_data = Project.objects.exclude(county__isnull=True).exclude(county="").values('county').annotate(
            project_count=Count('id'),
            total_budget=Sum('budget'),
            completed_projects=Count('id', filter=Q(status='completed'))
        ).order_by('county')
        
        data = list(county_data)
        data = _decimal_to_float(data)
        
        return JsonResponse({
            "counties": data,
            "source": "project_data_fallback"
        })
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

# Health check endpoint
@csrf_exempt
def health_check(request):
    """Health check endpoint for monitoring"""
    try:
        # Check database connectivity
        project_count = Project.objects.count()
        county_count = KenyaCounty.objects.count()
        
        return JsonResponse({
            "status": "healthy",
            "database": "connected",
            "projects_count": project_count,
            "counties_count": county_count,
            "timestamp": timezone.now().isoformat()
        })
    except Exception as e:
        return JsonResponse({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": timezone.now().isoformat()
        }, status=500)

# ---------------- Dashboard View ---------------- #
# ---------------- Dashboard View ---------------- #
import json
from decimal import Decimal
from datetime import timedelta
from django.db.models import Q, Count, Sum, Avg, Min, Max, F, ExpressionWrapper, FloatField
from django.db.models.functions import TruncMonth, ExtractYear, ExtractWeek
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.contrib.gis.db.models import Union
from django.contrib.gis.geos import Point
from .models import Project, ProjectUpdate, CitizenReport, KenyaCounty, KenyaSubCounty, Kenyawards

def dashboard(request):
    # Start with all projects
    projects = Project.objects.all().select_related().prefetch_related('updates', 'citizen_reports')

    # Initialize filter variables with default values
    selected_statuses = request.GET.getlist('status', [])
    selected_counties = request.GET.getlist('county', [])
    selected_sectors = request.GET.getlist('sector', [])
    selected_subcounties = request.GET.getlist('subcounty', [])
    selected_wards = request.GET.getlist('ward', [])
    min_budget = request.GET.get('min_budget', '')
    max_budget = request.GET.get('max_budget', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    search_query = request.GET.get('search', '')
    risk_level = request.GET.get('risk_level', '')
    implementing_agency = request.GET.get('implementing_agency', '')

    # Build filter conditions
    filters = Q()
    
    # Status filter - FIXED: Map your actual statuses to the filter choices
    if selected_statuses:
        # Map filter statuses to actual database statuses
        status_mapping = {
            'planned': ['design', 'planned', 'proposed'],
            'ongoing': ['ongoing', 'implementation', 'in_progress'],
            'completed': ['completed', 'finished', 'done'],
            'delayed': ['delayed', 'stalled', 'behind_schedule']
        }
        
        status_filters = Q()
        for selected_status in selected_statuses:
            if selected_status in status_mapping:
                actual_statuses = status_mapping[selected_status]
                status_filters |= Q(status__in=actual_statuses)
        
        if status_filters:
            filters &= status_filters
    
    # County filter
    if selected_counties:
        filters &= Q(county__in=selected_counties)
    
    # Sector filter
    if selected_sectors:
        filters &= Q(sector__in=selected_sectors)
    
    # Subcounty filter - simplified approach
    if selected_subcounties:
        # Get subcounties and their counties
        subcounty_mapping = {}
        subcounty_objects = KenyaSubCounty.objects.filter(subcounty__in=selected_subcounties)
        
        for sc in subcounty_objects:
            subcounty_mapping[sc.subcounty] = sc.county
        
        # Build OR condition for subcounties
        subcounty_filters = Q()
        for subcounty in selected_subcounties:
            if subcounty in subcounty_mapping:
                county_name = subcounty_mapping[subcounty]
                subcounty_filters |= Q(county=county_name)
        
        if subcounty_filters:
            filters &= subcounty_filters
    
    # Ward filter - simplified approach
    if selected_wards:
        # Get wards and their counties
        ward_mapping = {}
        ward_objects = Kenyawards.objects.filter(ward__in=selected_wards)
        
        for ward in ward_objects:
            ward_mapping[ward.ward] = ward.county
        
        # Build OR condition for wards
        ward_filters = Q()
        for ward in selected_wards:
            if ward in ward_mapping:
                county_name = ward_mapping[ward]
                ward_filters |= Q(county=county_name)
        
        if ward_filters:
            filters &= ward_filters

    # Budget filters
    if min_budget:
        try:
            filters &= Q(budget__gte=Decimal(min_budget))
        except (ValueError, TypeError):
            pass

    if max_budget:
        try:
            filters &= Q(budget__lte=Decimal(max_budget))
        except (ValueError, TypeError):
            pass

    # Date range filters - FIXED: Handle empty dates
    if start_date:
        try:
            filters &= Q(start_date__gte=start_date)
        except (ValueError, TypeError):
            pass

    if end_date:
        try:
            filters &= Q(end_date__lte=end_date)
        except (ValueError, TypeError):
            pass

    # Risk level filter - SIMPLIFIED
    if risk_level:
        current_date = timezone.now().date()
        if risk_level == 'high':
            # High risk: delayed projects or projects that are very behind schedule
            filters &= Q(status__in=['delayed', 'stalled', 'behind_schedule'])
        elif risk_level == 'medium':
            # Medium risk: ongoing projects with some risk factors
            filters &= Q(status__in=['ongoing', 'implementation', 'in_progress'])
        elif risk_level == 'low':
            # Low risk: completed or well-performing ongoing projects
            filters &= Q(status__in=['completed', 'finished'])

    # Implementing agency filter
    if implementing_agency:
        filters &= Q(implementing_agency__icontains=implementing_agency)

    # Search functionality
    if search_query:
        search_filters = (
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(sector__icontains=search_query) |
            Q(project_manager__icontains=search_query) |
            Q(county__icontains=search_query) |
            Q(implementing_agency__icontains=search_query)
        )
        filters &= search_filters

    # Apply all filters
    filtered_projects = projects.filter(filters)

    # Current date for calculations
    current_date = timezone.now().date()

    # Core Metrics
    total_projects = filtered_projects.count()
    total_budget = filtered_projects.aggregate(total=Sum("budget"))["total"] or 0

    # Completion metrics - FIXED: Use actual status mapping
    completed_projects = filtered_projects.filter(status__in=['completed', 'finished', 'done']).count()
    completion_rate = round((completed_projects / total_projects) * 100, 1) if total_projects > 0 else 0

    # Time-based metrics
    behind_schedule = filtered_projects.filter(
        status__in=['delayed', 'stalled', 'behind_schedule']
    ).count()

    upcoming_deadlines = filtered_projects.filter(
        status__in=['ongoing', 'implementation', 'in_progress']
    ).count()

    # Risk analysis - FIXED: Use actual status mapping
    high_risk_projects = filtered_projects.filter(status__in=['delayed', 'stalled', 'behind_schedule']).count()
    medium_risk_projects = filtered_projects.filter(status__in=['ongoing', 'implementation', 'in_progress']).count()

    # Enhanced Status Distribution - FIXED: Map to display categories
    status_categories = {
        'planned': ['design', 'planned', 'proposed'],
        'ongoing': ['ongoing', 'implementation', 'in_progress'],
        'completed': ['completed', 'finished', 'done'],
        'delayed': ['delayed', 'stalled', 'behind_schedule']
    }
    
    status_data = {category: 0 for category in status_categories.keys()}
    status_budget_data = {category: 0 for category in status_categories.keys()}
    
    for category, status_list in status_categories.items():
        category_projects = filtered_projects.filter(status__in=status_list)
        status_data[category] = category_projects.count()
        status_budget_data[category] = float(category_projects.aggregate(total=Sum('budget'))['total'] or 0)

    # Sector Analysis
    sector_analysis = filtered_projects.values('sector').annotate(
        count=Count('id'),
        total_budget=Sum('budget'),
        completed=Count('id', filter=Q(status__in=['completed', 'finished', 'done']))
    ).order_by('-total_budget')[:10]

    # County Analysis
    county_analysis = filtered_projects.values('county').annotate(
        count=Count('id'),
        total_budget=Sum('budget'),
        completed=Count('id', filter=Q(status__in=['completed', 'finished', 'done'])),
        completion_rate=ExpressionWrapper(
            Count('id', filter=Q(status__in=['completed', 'finished', 'done'])) * 100.0 / Count('id'),
            output_field=FloatField()
        )
    ).order_by('-count')[:15]

    # Timeline Analysis
    monthly_timeline = (
        filtered_projects.annotate(month=TruncMonth('start_date'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    # Performance Metrics - SIMPLIFIED for now
    performance_metrics = {
        'efficiency_score': 75,  # Placeholder
        'budget_utilization': 65,  # Placeholder
        'timeline_adherence': 70,  # Placeholder
        'geographic_coverage': 85,  # Placeholder
        'citizen_engagement': 60,  # Placeholder
    }

    # Recent Activity
    recent_updates = ProjectUpdate.objects.select_related('project').filter(project__in=filtered_projects).order_by('-created_at')[:10]

    # Manager Performance
    manager_performance = filtered_projects.values('project_manager').annotate(
        count=Count('id'),
        completed=Count('id', filter=Q(status__in=['completed', 'finished', 'done'])),
        total_budget=Sum('budget')
    ).exclude(project_manager='').order_by('-count')[:10]

    # Risk Analysis Detailed
    risk_analysis = {
        'financial_risk': high_risk_projects,
        'schedule_risk': behind_schedule,
        'performance_risk': high_risk_projects,
        'geographic_risk': 25  # Placeholder
    }

    # GeoJSON for Map - using filtered projects
    features = []
    for project in filtered_projects:
        point_geom = None
        
        if project.location and hasattr(project.location, 'x') and hasattr(project.location, 'y'):
            point_geom = {
                "type": "Point",
                "coordinates": [float(project.location.x), float(project.location.y)]
            }
        elif project.longitude and project.latitude:
            try:
                point_geom = {
                    "type": "Point",
                    "coordinates": [float(project.longitude), float(project.latitude)]
                }
            except (TypeError, ValueError):
                continue
        
        if point_geom:
            # Map status to display category
            display_status = 'planned'
            if project.status in ['completed', 'finished', 'done']:
                display_status = 'completed'
            elif project.status in ['ongoing', 'implementation', 'in_progress']:
                display_status = 'ongoing'
            elif project.status in ['delayed', 'stalled', 'behind_schedule']:
                display_status = 'delayed'
            
            health_score = calculate_project_health(project, current_date)
            calculated_risk = calculate_risk_level(project, current_date)
            
            features.append({
                "type": "Feature",
                "geometry": point_geom,
                "properties": {
                    "id": project.id,
                    "name": project.name,
                    "county": project.county,
                    "status": display_status,  # Use mapped status
                    "sector": project.sector or "",
                    "budget": float(project.budget) if project.budget else 0,
                    "start_date": project.start_date.strftime("%Y-%m-%d") if project.start_date else "",
                    "end_date": project.end_date.strftime("%Y-%m-%d") if project.end_date else "",
                    "project_manager": project.project_manager or "",
                    "implementing_agency": project.implementing_agency or "",
                    "health_score": health_score,
                    "risk_level": calculated_risk,
                    "days_remaining": (project.end_date - current_date).days if project.end_date and project.status in ['ongoing', 'implementation', 'in_progress'] else None
                }
            })

    geojson = {"type": "FeatureCollection", "features": features}

    # Filter options - FIXED: Get actual unique values
    status_choices = [
        ("planned", "Planned"),
        ("ongoing", "Ongoing"), 
        ("completed", "Completed"),
        ("delayed", "Delayed")
    ]
    
    counties = Project.objects.values_list("county", flat=True).distinct().order_by("county")
    sectors = Project.objects.values_list("sector", flat=True).distinct().order_by("sector")
    subcounties = KenyaSubCounty.objects.values_list("subcounty", flat=True).distinct().order_by("subcounty")
    wards = Kenyawards.objects.values_list("ward", flat=True).distinct().order_by("ward")
    implementing_agencies = Project.objects.exclude(implementing_agency='').values_list("implementing_agency", flat=True).distinct().order_by("implementing_agency")

    context = {
        # Core metrics
        "total_projects": total_projects,
        "total_budget": total_budget,
        "completion_rate": completion_rate,
        "behind_schedule": behind_schedule,
        "upcoming_deadlines": upcoming_deadlines,
        "high_risk_projects": high_risk_projects,
        "medium_risk_projects": medium_risk_projects,
        
        # Analytics data
        "status_data": status_data,
        "status_budget_data": status_budget_data,
        "sector_analysis": list(sector_analysis),
        "county_analysis": list(county_analysis),
        "monthly_timeline": list(monthly_timeline),
        "performance_metrics": performance_metrics,
        "risk_analysis": risk_analysis,
        
        # Recent activity
        "recent_updates": recent_updates,
        "manager_performance": list(manager_performance),
        
        # Filter options
        "status_choices": status_choices,
        "counties": counties,
        "sectors": sectors,
        "subcounties": subcounties,
        "wards": wards,
        "implementing_agencies": implementing_agencies,
        
        # Selected filters
        "selected_statuses": selected_statuses,
        "selected_counties": selected_counties,
        "selected_sectors": selected_sectors,
        "selected_subcounties": selected_subcounties,
        "selected_wards": selected_wards,
        "min_budget": min_budget,
        "max_budget": max_budget,
        "start_date": start_date,
        "end_date": end_date,
        "search_query": search_query,
        "risk_level": risk_level,
        "implementing_agency": implementing_agency,
        
        # GeoJSON
        "geojson": json.dumps(geojson),
        
        # Additional data for charts
        "sector_labels": json.dumps([item['sector'] or 'Unknown' for item in sector_analysis]),
        "sector_counts": json.dumps([item['count'] for item in sector_analysis]),
        "sector_budgets": json.dumps([float(item['total_budget'] or 0) for item in sector_analysis]),
        "county_labels": json.dumps([item['county'] for item in county_analysis]),
        "county_counts": json.dumps([item['count'] for item in county_analysis]),
        "county_completion": json.dumps([float(item['completion_rate'] or 0) for item in county_analysis]),
        "timeline_labels": json.dumps([item['month'].strftime('%b %Y') for item in monthly_timeline]),
        "timeline_counts": json.dumps([item['count'] for item in monthly_timeline]),
        
        # Pass filtered projects for table
        "projects": filtered_projects[:50],
    }
    
    return render(request, "app/dashboard.html", context)

# Keep your utility functions but update risk calculation
def calculate_project_health(project, current_date):
    """Calculate project health score (0-100)"""
    score = 50
    
    # Status-based scoring
    status_scores = {
        'completed': 30, 'finished': 30, 'done': 30,
        'ongoing': 20, 'implementation': 20, 'in_progress': 20,
        'design': 10, 'planned': 10, 'proposed': 10,
        'delayed': -20, 'stalled': -20, 'behind_schedule': -20
    }
    score += status_scores.get(project.status, 0)
    
    return max(0, min(100, round(score)))

def calculate_risk_level(project, current_date):
    """Calculate project risk level"""
    risk_score = 0
    
    if project.status in ['delayed', 'stalled', 'behind_schedule']:
        risk_score += 3
    
    if project.end_date and project.status in ['ongoing', 'implementation', 'in_progress']:
        days_remaining = (project.end_date - current_date).days
        if days_remaining < 0:
            risk_score += 3
        elif days_remaining < 30:
            risk_score += 2
        elif days_remaining < 90:
            risk_score += 1
    
    if risk_score >= 5:
        return "high"
    elif risk_score >= 3:
        return "medium"
    else:
        return "low"

def calculate_efficiency_score(projects, current_date):
    """Calculate overall efficiency score"""
    if projects.count() == 0:
        return 0
    
    completed = projects.filter(status='completed')
    if completed.count() == 0:
        return 0
    
    on_time = completed.filter(
        end_date__lte=F('start_date') + timedelta(days=365)
    ).count()
    
    return round((on_time / completed.count() * 100), 1)

def calculate_budget_utilization(projects):
    """Calculate budget utilization efficiency"""
    if projects.count() == 0:
        return 0
    
    total_budget = projects.aggregate(Sum('budget'))['budget__sum'] or 0
    completed_budget = projects.filter(status='completed').aggregate(Sum('budget'))['budget__sum'] or 0
    
    utilization = (completed_budget / total_budget * 100) if total_budget > 0 else 0
    return round(utilization, 1)

def calculate_timeline_adherence(projects, current_date):
    """Calculate timeline adherence score"""
    if projects.count() == 0:
        return 0
    
    completed_projects = projects.filter(status='completed')
    if completed_projects.count() == 0:
        return 0
    
    completed_on_time = completed_projects.filter(
        end_date__isnull=False
    ).count()
    
    return round((completed_on_time / completed_projects.count() * 100), 1)

def calculate_geographic_coverage(projects):
    """Calculate geographic coverage score"""
    if projects.count() == 0:
        return 0
    
    unique_counties = projects.values('county').distinct().count()
    total_counties = 47  # Kenya has 47 counties
    
    return round((unique_counties / total_counties * 100), 1)

def calculate_citizen_engagement(projects):
    """Calculate citizen engagement score"""
    if projects.count() == 0:
        return 0
    
    projects_with_reports = projects.filter(citizen_reports__isnull=False).distinct().count()
    return round((projects_with_reports / projects.count() * 100), 1)

def calculate_geographic_risk(projects):
    """Calculate geographic risk (projects concentrated in few areas)"""
    if projects.count() == 0:
        return 0
    
    county_distribution = projects.values('county').annotate(count=Count('id'))
    if not county_distribution:
        return 0
    
    max_projects = max([item['count'] for item in county_distribution])
    total_projects = sum([item['count'] for item in county_distribution])
    
    concentration = (max_projects / total_projects * 100) if total_projects > 0 else 0
    return round(concentration, 1)


# ---------------- Other views remain the same ---------------- #
class ProjectListView(ListView):
    model = Project
    template_name = 'app/project_list.html'
    context_object_name = 'projects'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Apply filters from GET parameters
        county = self.request.GET.get('county')
        if county:
            queryset = queryset.filter(county__icontains=county)
            
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
            
        sector = self.request.GET.get('sector')
        if sector:
            queryset = queryset.filter(sector__icontains=sector)
            
        agency = self.request.GET.get('agency')
        if agency:
            queryset = queryset.filter(implementing_agency__icontains=agency)
            
        # Budget range filter
        min_budget = self.request.GET.get('min_budget')
        max_budget = self.request.GET.get('max_budget')
        if min_budget:
            try:
                queryset = queryset.filter(budget__gte=Decimal(min_budget))
            except (ValueError, TypeError):
                pass
        if max_budget:
            try:
                queryset = queryset.filter(budget__lte=Decimal(max_budget))
            except (ValueError, TypeError):
                pass
                
        # Date range filter
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date:
            try:
                queryset = queryset.filter(start_date__gte=start_date)
            except (ValueError):
                pass
        if end_date:
            try:
                queryset = queryset.filter(end_date__lte=end_date)
            except (ValueError):
                pass
                
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all filter options from database
        counties = Project.objects.exclude(county__isnull=True).exclude(county='').values_list('county', flat=True).distinct().order_by('county')
        sectors = Project.objects.exclude(sector__isnull=True).exclude(sector='').values_list('sector', flat=True).distinct().order_by('sector')
        agencies = Project.objects.exclude(implementing_agency__isnull=True).exclude(implementing_agency='').values_list('implementing_agency', flat=True).distinct().order_by('implementing_agency')
        
        # Get current filter values
        selected_county = self.request.GET.get('county', '')
        selected_status = self.request.GET.get('status', '')
        selected_sector = self.request.GET.get('sector', '')
        selected_agency = self.request.GET.get('agency', '')
        selected_min_budget = self.request.GET.get('min_budget', '')
        selected_max_budget = self.request.GET.get('max_budget', '')
        selected_start_date = self.request.GET.get('start_date', '')
        selected_end_date = self.request.GET.get('end_date', '')
        
        # Get filtered projects for statistics
        filtered_projects = self.get_queryset()
        
        # Calculate statistics
        total_projects = filtered_projects.count()
        total_budget = filtered_projects.aggregate(total=Sum('budget'))['total'] or 0
        avg_budget = filtered_projects.aggregate(avg=Avg('budget'))['avg'] or 0
        
        # Status distribution
        status_counts = filtered_projects.values('status').annotate(count=Count('id'))
        status_data = {item['status']: item['count'] for item in status_counts}
        
        # County distribution (top 5)
        county_stats = filtered_projects.values('county').annotate(
            count=Count('id'),
            total_budget=Sum('budget')
        ).order_by('-count')[:5]
        
        # Sector distribution (top 5)
        sector_stats = filtered_projects.values('sector').annotate(
            count=Count('id')
        ).exclude(sector__isnull=True).exclude(sector='').order_by('-count')[:5]
        
        # Recent updates
        recent_updates = ProjectUpdate.objects.select_related('project').order_by('-created_at')[:3]
        
        # High budget projects
        high_budget_projects = filtered_projects.order_by('-budget')[:3]
        
        context.update({
            'counties': counties,
            'sectors': sectors,
            'agencies': agencies,
            'status_choices': [choice[0] for choice in Project.STATUS_CHOICES],
            'status_labels': dict(Project.STATUS_CHOICES),
            'selected_county': selected_county,
            'selected_status': selected_status,
            'selected_sector': selected_sector,
            'selected_agency': selected_agency,
            'selected_min_budget': selected_min_budget,
            'selected_max_budget': selected_max_budget,
            'selected_start_date': selected_start_date,
            'selected_end_date': selected_end_date,
            'total_projects': total_projects,
            'total_budget': total_budget,
            'avg_budget': avg_budget,
            'status_counts': status_data,
            'county_stats': county_stats,
            'sector_stats': sector_stats,
            'recent_updates': recent_updates,
            'high_budget_projects': high_budget_projects,
        })
        
        return context


class ProjectDetailView(DetailView):
    model = Project
    template_name = 'app/project_detail.html'
    context_object_name = 'project'


def project_map_view(request):
    # Start with all projects that have location data
    projects = Project.objects.filter(location__isnull=False)
    
    # Filters
    status_filter = request.GET.getlist('status')
    if status_filter:
        projects = projects.filter(status__in=status_filter)
    
    county_filter = request.GET.getlist('county')
    if county_filter:
        projects = projects.filter(county__in=county_filter)
    
    sector_filter = request.GET.getlist('sector')
    if sector_filter:
        projects = projects.filter(sector__in=sector_filter)
    
    # Get filter options
    status_choices = [choice[0] for choice in Project.STATUS_CHOICES]
    status_labels = dict(Project.STATUS_CHOICES)
    counties = Project.objects.values_list('county', flat=True).distinct().order_by('county')
    sectors = (
        Project.objects
        .exclude(sector__isnull=True)
        .exclude(sector='')
        .values_list('sector', flat=True)
        .distinct()
        .order_by('sector')
    )
    
    # Deep Insights Calculations
    total_projects = projects.count()
    total_budget = projects.aggregate(total=Sum('budget'))['total'] or Decimal(0)
    
    # Geographical Distribution Insights
    county_distribution = (
        projects.values('county')
        .annotate(
            count=Count('id'),
            total_budget=Sum('budget'),
            avg_budget=Avg('budget')
        )
        .order_by('-count')[:10]
    )
    
    # Status Distribution
    status_distribution = projects.values('status').annotate(
        count=Count('id'),
        total_budget=Sum('budget')
    )
    
    # Sector Analysis
    sector_analysis = (
        projects.values('sector')
        .annotate(
            count=Count('id'),
            total_budget=Sum('budget'),
            avg_budget=Avg('budget')
        )
        .exclude(sector__isnull=True)
        .order_by('-total_budget')[:5]
    )
    
    # Budget Analysis
    budget_stats = projects.aggregate(
        avg_budget=Avg('budget'),
        min_budget=Min('budget'),
        max_budget=Max('budget'),
        budget_stddev=StdDev('budget')
    )
    
    # Spatial Clustering Analysis
    county_density = []
    for county in county_distribution:
        county_density.append({
            'county': county['county'],
            'project_density': county['count'],
            'budget_density': county['total_budget'] or 0
        })
    
    # Recent Projects
    recent_projects = projects.order_by('-created_at')[:3]
    
    # High Impact Projects (top 5 by budget)
    high_impact_projects = projects.order_by('-budget')[:5]
    
    # Create GeoJSON
    features = []
    for project in projects:
        budget = project.budget or Decimal(0)
        budget_percentage = (budget / total_budget * Decimal(100)) if total_budget and budget else Decimal(0)

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [project.location.x, project.location.y],
            },
            "properties": {
                "id": project.id,
                "name": project.name,
                "status": project.status,
                "county": project.county,
                "sector": project.sector or "",
                "budget": float(budget),  # safe for JSON
                "start_date": project.start_date.strftime("%Y-%m-%d") if project.start_date else "",
                "end_date": project.end_date.strftime("%Y-%m-%d") if project.end_date else "",
                "description": project.description or "",
                "implementing_agency": project.implementing_agency or "",
                "project_manager": project.project_manager or "",
                "budget_percentage": float(budget_percentage)  # convert Decimal to float for JSON
            }
        })
    
    geojson = {"type": "FeatureCollection", "features": features}
    
    context = {
        "geojson": json.dumps(geojson),
        "status_choices": status_choices,
        "status_labels": status_labels,
        "counties": counties,
        "sectors": sectors,
        "selected_statuses": status_filter,
        "selected_counties": county_filter,
        "selected_sectors": sector_filter,
        "total_projects": total_projects,
        "total_budget": total_budget,
        "county_distribution": county_distribution,
        "status_distribution": status_distribution,
        "sector_analysis": sector_analysis,
        "budget_stats": budget_stats,
        "county_density": county_density,
        "recent_projects": recent_projects,
        "high_impact_projects": high_impact_projects,
    }
    
    return render(request, 'app/project_map.html', context)


def submit_report(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if request.method == 'POST':
        form = CitizenReportForm(request.POST, request.FILES)
        if form.is_valid():
            report = form.save(commit=False)
            report.project = project
            if request.user.is_authenticated:
                report.reported_by = request.user
            report.save()
            return render(request, 'app/report_success.html', {'project': project})
    else:
        form = CitizenReportForm()
    context = {"form": form, "project": project}
    return render(request, 'app/submit_report.html', context)


def about(request):
    return render(request, 'app/about.html')


def contact(request):
    return render(request, 'app/contact.html')


def project_timeline(request, project_id):
    """Real-time project timeline view"""
    project = get_object_or_404(Project, id=project_id)
    
    # Get initial timeline data
    updates = ProjectUpdate.objects.filter(project=project).select_related('reported_by').order_by('-created_at')
    reports = CitizenReport.objects.filter(project=project).select_related('reported_by').order_by('-created_at')
    
    # Combine timeline items
    timeline_items = []
    
    for update in updates:
        timeline_items.append({
            'type': 'update',
            'id': update.id,
            'title': update.title,
            'description': update.description,
            'progress_percentage': update.progress_percentage,
            'photo': update.photo.url if update.photo else None,
            'created_at': update.created_at,
            'created_by': update.reported_by,
            'is_update': True
        })
    
    for report in reports:
        timeline_items.append({
            'type': 'report',
            'id': report.id,
            'report_type': report.report_type,
            'description': report.description,
            'photo': report.photo.url if report.photo else None,
            'created_at': report.created_at,
            'created_by': report.reported_by,
            'is_approved': report.is_approved,
            'is_update': False
        })
    
    # Sort by creation date (newest first)
    timeline_items.sort(key=lambda x: x['created_at'], reverse=True)
    
    context = {
        'project': project,
        'timeline_items': timeline_items,
        'websocket_url': f"ws://{request.get_host()}/ws/project/{project.id}/timeline/"
    }
    
    return render(request, 'app/project_timeline.html', context)





from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json

@csrf_exempt
def api_project_update(request, project_id):
    """API endpoint for project updates with file upload"""
    if request.method == 'POST':
        try:
            project = Project.objects.get(id=project_id)
            user = request.user if request.user.is_authenticated else None
            
            update = ProjectUpdate.objects.create(
                project=project,
                title=request.POST.get('title', 'Update'),
                description=request.POST.get('description', ''),
                progress_percentage=request.POST.get('progress_percentage', 0),
                reported_by=user
            )
            
            # Handle file upload
            if 'photo' in request.FILES:
                update.photo = request.FILES['photo']
                update.save()
            
            return JsonResponse({'success': True, 'update_id': update.id})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})

@csrf_exempt
def api_citizen_report(request, project_id):
    """API endpoint for citizen reports with file upload"""
    if request.method == 'POST':
        try:
            project = Project.objects.get(id=project_id)
            user = request.user if request.user.is_authenticated else None
            
            report = CitizenReport.objects.create(
                project=project,
                report_type=request.POST.get('report_type', 'progress'),
                description=request.POST.get('description', ''),
                reported_by=user
            )
            
            # Handle file upload
            if 'photo' in request.FILES:
                report.photo = request.FILES['photo']
                report.save()
            
            return JsonResponse({'success': True, 'report_id': report.id})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})


from .models import ProjectChatMessage

def project_chartboard(request, project_id):
    """Project-specific chartboard with detailed analytics and chat"""
    project = get_object_or_404(Project, id=project_id)
    
    # Get project updates and reports
    updates = ProjectUpdate.objects.filter(project=project).order_by('created_at')
    reports = CitizenReport.objects.filter(project=project).order_by('created_at')
    
    # Calculate project progress
    latest_update = updates.last()
    current_progress = latest_update.progress_percentage if latest_update else 0
    
    # Budget utilization
    total_budget = float(project.budget) if project.budget else 0.0
    spent_budget = total_budget * (current_progress / 100) if current_progress > 0 else 0.0
    
    # Timeline analysis
    today = timezone.now().date()
    total_duration = (project.end_date - project.start_date).days
    elapsed_days = (today - project.start_date).days
    remaining_days = max(0, (project.end_date - today).days)
    
    # Progress timeline data
    progress_timeline = []
    progress_dates = []
    progress_values = []
    
    for update in updates:
        progress_timeline.append({
            'date': update.created_at.strftime('%Y-%m-%d'),
            'progress': update.progress_percentage,
            'title': update.title
        })
        progress_dates.append(update.created_at.strftime('%b %d'))
        progress_values.append(update.progress_percentage)
    
    # Report type distribution
    report_types = reports.values('report_type').annotate(count=Count('id'))
    report_type_data = {item['report_type']: item['count'] for item in report_types}
    
    # Monthly activity
    monthly_activity = updates.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')
    
    monthly_labels = []
    monthly_data = []
    
    for activity in monthly_activity:
        monthly_labels.append(activity['month'].strftime('%b %Y'))
        monthly_data.append(activity['count'])
    
    # Get chat messages
    chat_messages = ProjectChatMessage.objects.filter(project=project).select_related('user', 'reply_to')[:100]
    
    context = {
        'project': project,
        'current_progress': current_progress,
        'total_budget': total_budget,
        'spent_budget': spent_budget,
        'remaining_budget': total_budget - spent_budget,
        'total_duration': total_duration,
        'elapsed_days': elapsed_days,
        'remaining_days': remaining_days,
        'updates_count': updates.count(),
        'reports_count': reports.count(),
        'progress_timeline': progress_timeline,
        'progress_dates': progress_dates,
        'progress_values': progress_values,
        'report_type_data': report_type_data,
        'monthly_activity': list(monthly_activity),
        'monthly_labels': monthly_labels,
        'monthly_data': monthly_data,
        'updates': updates.order_by('-created_at')[:10],
        'reports': reports.order_by('-created_at')[:10],
        'chat_messages': chat_messages,
    }
    
    return render(request, 'app/project_chartboard.html', context)



@csrf_exempt
def send_chat_message(request, project_id):
    """Send a chat message - allow both authenticated and guest users"""
    if request.method == 'POST':
        try:
            project = Project.objects.get(id=project_id)
            
            # Allow both authenticated and unauthenticated users
            user = request.user if request.user.is_authenticated else None
            
            message_text = request.POST.get('message', '').strip()
            image = request.FILES.get('image')
            file = request.FILES.get('file')
            reply_to_id = request.POST.get('reply_to')
            guest_name = request.POST.get('guest_name', 'Anonymous User').strip()
            
            if not message_text and not image and not file:
                return JsonResponse({'success': False, 'error': 'Message cannot be empty'})
            
            # Validate guest name
            if not user and not guest_name:
                guest_name = 'Anonymous User'
            
            # Create message
            chat_message = ProjectChatMessage(
                project=project,
                user=user,
                guest_name=guest_name if not user else None,  # Only store guest name for unauthenticated users
                message=message_text,
                message_type='image' if image else 'file' if file else 'text'
            )
            
            if image:
                chat_message.image = image
            if file:
                chat_message.file = file
            
            if reply_to_id:
                try:
                    reply_to_msg = ProjectChatMessage.objects.get(id=reply_to_id, project=project)
                    chat_message.reply_to = reply_to_msg
                except ProjectChatMessage.DoesNotExist:
                    pass
            
            chat_message.save()
            
            # Return message data
            message_data = {
                'id': chat_message.id,
                'user': chat_message.display_name,
                'user_id': chat_message.user.id if chat_message.user else None,
                'message': chat_message.message,
                'message_type': chat_message.message_type,
                'image_url': chat_message.image.url if chat_message.image else None,
                'file_url': chat_message.file.url if chat_message.file else None,
                'file_name': chat_message.file.name if chat_message.file else None,
                'timestamp': chat_message.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'display_time': chat_message.timestamp.strftime('%I:%M %p'),
                'is_own_message': True,  # Since they just sent it
                'is_authenticated': chat_message.user is not None,
                'is_guest': chat_message.is_guest,
                'reply_to': {
                    'id': chat_message.reply_to.id,
                    'user': chat_message.reply_to.display_name,
                    'message': chat_message.reply_to.message[:50] + '...' if len(chat_message.reply_to.message) > 50 else chat_message.reply_to.message,
                    'message_type': chat_message.reply_to.message_type,
                } if chat_message.reply_to else None
            }
            
            return JsonResponse({'success': True, 'message': message_data})
            
        except Project.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Project not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})

def get_chat_messages(request, project_id):
    """Get chat messages for a project"""
    try:
        project = Project.objects.get(id=project_id)
        last_message_id = request.GET.get('last_message_id', 0)
        
        messages = ProjectChatMessage.objects.filter(
            project=project, 
            id__gt=last_message_id
        ).select_related('user', 'reply_to').order_by('timestamp')[:50]
        
        messages_data = []
        for msg in messages:
            # Determine if this is the current user's message
            if request.user.is_authenticated:
                is_own_message = msg.user == request.user
            else:
                # For guests, check if the guest name matches (this is a simple approach)
                # You might want to use session-based identification for better accuracy
                is_own_message = msg.is_guest  # Simple approach for demo
            
            messages_data.append({
                'id': msg.id,
                'user': msg.display_name,
                'user_id': msg.user.id if msg.user else None,
                'message': msg.message,
                'message_type': msg.message_type,
                'image_url': msg.image.url if msg.image else None,
                'file_url': msg.file.url if msg.file else None,
                'file_name': msg.file.name if msg.file else None,
                'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'display_time': msg.timestamp.strftime('%I:%M %p'),
                'is_own_message': is_own_message,
                'is_authenticated': msg.user is not None,
                'is_guest': msg.is_guest,
                'reply_to': {
                    'id': msg.reply_to.id,
                    'user': msg.reply_to.display_name,
                    'message': msg.reply_to.message[:50] + '...' if len(msg.reply_to.message) > 50 else msg.reply_to.message,
                    'message_type': msg.reply_to.message_type,
                } if msg.reply_to else None
            })
        
        return JsonResponse({'success': True, 'messages': messages_data})
        
    except Project.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Project not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    


@csrf_exempt
def mark_messages_as_read(request, project_id):
    """Mark messages as read"""
    if request.method == 'POST' and request.user.is_authenticated:
        try:
            data = json.loads(request.body)
            message_ids = data.get('message_ids', [])
            
            messages = ProjectChatMessage.objects.filter(
                id__in=message_ids,
                project_id=project_id
            )
            
            for message in messages:
                message.mark_as_read(request.user)
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})
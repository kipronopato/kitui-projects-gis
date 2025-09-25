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


def _clean_get(request, name):
    """Return single GET param; treat 'None' or empty as None."""
    v = request.GET.get(name)
    return None if (v is None or v == "None" or v == "") else v

def _clean_getlist(request, name):
    """Return list cleaned of empty/'None' entries."""
    return [v for v in request.GET.getlist(name) if v and v != "None"]

def home(request):
    # Start with all projects
    projects = Project.objects.all()

    # ---------------- Enhanced Filters ----------------
    selected_year = _clean_get(request, "year")
    selected_statuses = _clean_getlist(request, "status")
    selected_sectors = _clean_getlist(request, "sector")
    selected_counties = _clean_getlist(request, "county")
    selected_subcounties = _clean_getlist(request, "subcounty")
    selected_wards = _clean_getlist(request, "ward")
    min_budget = _clean_get(request, "min_budget")
    max_budget = _clean_get(request, "max_budget")
    start_date = _clean_get(request, "start_date")
    end_date = _clean_get(request, "end_date")

    # Apply filters
    if selected_year:
        projects = projects.filter(start_date__year=selected_year)
    if selected_statuses:
        projects = projects.filter(status__in=selected_statuses)
    if selected_sectors:
        projects = projects.filter(sector__in=selected_sectors)
    if selected_counties:
        projects = projects.filter(county__in=selected_counties)

    # Enhanced spatial filtering
    if selected_subcounties:
        subcounty_geoms = KenyaSubCounty.objects.filter(subcounty__in=selected_subcounties)
        if subcounty_geoms.exists():
            combined_geom = subcounty_geoms.aggregate(union=Union('geom'))['union']
            if combined_geom:
                projects = projects.filter(location__within=combined_geom)

    if selected_wards:
        ward_geoms = Kenyawards.objects.filter(ward__in=selected_wards)
        if ward_geoms.exists():
            combined_geom = ward_geoms.aggregate(union=Union('geom'))['union']
            if combined_geom:
                projects = projects.filter(location__within=combined_geom)

    # Budget filters
    if min_budget:
        try:
            projects = projects.filter(budget__gte=Decimal(min_budget))
        except (ValueError, TypeError):
            pass

    if max_budget:
        try:
            projects = projects.filter(budget__lte=Decimal(max_budget))
        except (ValueError, TypeError):
            pass

    # Date filters
    if start_date:
        try:
            projects = projects.filter(start_date__gte=start_date)
        except (ValueError, TypeError):
            pass

    if end_date:
        try:
            projects = projects.filter(end_date__lte=end_date)
        except (ValueError, TypeError):
            pass

    # ---------------- Enhanced Metrics ----------------
    total_projects = projects.count()
    total_budget = projects.aggregate(total=Sum("budget"))["total"] or 0
    county_count = projects.values("county").distinct().count()

    # Enhanced budget statistics
    budget_stats = projects.aggregate(
        avg_budget=Avg("budget"),
        min_budget=Min("budget"),
        max_budget=Max("budget"),
        total_budget=Sum("budget"),
        median_budget=Avg("budget")  # Simplified median
    )

    # Project lists with enhanced data
    highest_budget_projects = projects.order_by("-budget")[:10]
    lowest_budget_projects = projects.order_by("budget")[:10]
    recent_projects = projects.order_by("-start_date")[:5]

    # Enhanced status statistics
    status_counts_dict = {}
    status_percentages_dict = {}
    status_data = projects.values("status").annotate(
        count=Count("id"),
        total_budget=Sum("budget"),
        avg_budget=Avg("budget")
    )
    
    for item in status_data:
        status_counts_dict[item["status"]] = {
            'count': item["count"],
            'total_budget': item["total_budget"] or 0,
            'avg_budget': item["avg_budget"] or 0
        }
    
    total_with_status = sum(item['count'] for item in status_counts_dict.values())
    for status, data in status_counts_dict.items():
        status_percentages_dict[status] = round((data['count'] / total_with_status * 100), 1) if total_with_status else 0

    # Enhanced date calculations
    current_date = timezone.now().date()
    overdue_projects = projects.filter(
        Q(status="ongoing") & Q(end_date__lt=current_date)
    ).count()
    
    upcoming_deadlines = projects.filter(
        Q(status="ongoing"),
        end_date__gte=current_date,
        end_date__lte=current_date + timedelta(days=30),
    ).count()

    completed_projects = projects.filter(status="completed").count()
    completion_rate = round((completed_projects / total_projects * 100), 1) if total_projects else 0

    # Enhanced sector statistics
    sector_stats = projects.values("sector").annotate(
        count=Count("id"), 
        total_budget=Sum("budget"), 
        avg_budget=Avg("budget"),
        completed=Count("id", filter=Q(status="completed")),
        ongoing=Count("id", filter=Q(status="ongoing"))
    ).order_by("-count")

    sector_data = []
    for item in sector_stats:
        percentage = round((item["count"] / total_projects * 100), 1) if total_projects else 0
        completion_rate_sector = round((item["completed"] / item["count"] * 100), 1) if item["count"] else 0
        sector_data.append({
            "sector": item["sector"] or "Not Specified",
            "count": item["count"],
            "total_budget": item["total_budget"] or 0,
            "avg_budget": item["avg_budget"] or 0,
            "percentage": percentage,
            "completion_rate": completion_rate_sector,
            "completed": item["completed"],
            "ongoing": item["ongoing"]
        })

    # Enhanced county statistics with spatial data
    county_stats = []
    counties = KenyaCounty.objects.all()
    for county in counties:
        county_projects = projects.filter(location__within=county.geom)
        project_count = county_projects.count()
        total_budget_county = county_projects.aggregate(Sum('budget'))['budget__sum'] or 0
        
        if project_count > 0:
            county_stats.append({
                "county": county.county,
                "count": project_count,
                "total_budget": total_budget_county,
                "avg_budget": total_budget_county / project_count,
                "population": county.pop_2009 or 0,
                "budget_per_capita": total_budget_county / (county.pop_2009 or 1)
            })
    
    county_stats = sorted(county_stats, key=lambda x: x['count'], reverse=True)[:10]

    # Enhanced timeline data
    monthly_timeline = (
        projects.annotate(month=TruncMonth("start_date"))
        .values("month")
        .annotate(
            count=Count("id"),
            total_budget=Sum("budget")
        )
        .order_by("month")
    )

    # Recent activity with enhanced data
    recent_updates = ProjectUpdate.objects.select_related("project").order_by("-created_at")[:10]

    # Enhanced citizen engagement
    report_stats = CitizenReport.objects.values("report_type").annotate(
        count=Count("id"),
        approved=Count("id", filter=Q(is_approved=True)),
        recent=Count("id", filter=Q(created_at__gte=current_date - timedelta(days=30)))
    )
    
    report_counts_dict = {}
    for item in report_stats:
        report_counts_dict[item["report_type"]] = {
            'total': item["count"],
            'approved': item["approved"],
            'recent': item["recent"],
            'approval_rate': round((item["approved"] / item["count"] * 100), 1) if item["count"] else 0
        }
    
    approved_reports = CitizenReport.objects.filter(is_approved=True).count()
    total_reports = CitizenReport.objects.count()
    approval_rate = round((approved_reports / total_reports * 100), 1) if total_reports else 0

    # Budget by status for charts
    budget_by_status = (
        projects.values("status")
        .annotate(total_budget=Sum("budget"))
        .order_by("status")
    )

    # Enhanced manager statistics
    manager_stats = (
        projects.values("project_manager")
        .annotate(
            count=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
            total_budget=Sum("budget"),
            avg_completion_time=Avg(
                ExpressionWrapper(F('end_date') - F('start_date'), output_field=DurationField())
            )
        )
        .exclude(project_manager="")
        .order_by("-count")[:5]
    )
    
    # First compute total budget
    total_budget_all = projects.aggregate(total=Sum("budget"))["total"] or 1

    # New Analytics: Performance Metrics
    
    # Annotate utilization
    projects = projects.annotate(
        budget_utilization=ExpressionWrapper(
            F("budget") / Value(total_budget_all, output_field=FloatField()),
            output_field=FloatField()
        )
    )

    budget_utilization = projects.aggregate(
        total_allocated=Sum('budget'),
        avg_utilization=Avg('budget_utilization')
    )

    # Risk analysis
    high_risk_projects = projects.filter(
        Q(status='delayed') | 
        Q(end_date__lt=current_date + timedelta(days=30)) |
        Q(budget_utilization__gt=100)  # Over-budget
    ).count()

    # Spatial analytics
    projects_by_region = projects.values('county').annotate(
        count=Count('id'),
        budget=Sum('budget'),
        completed=Count('id', filter=Q(status='completed'))
    ).order_by('-count')

    # ---------------- Enhanced Dropdown Data ----------------
    fiscal_years_qs = Project.objects.dates("start_date", "year").order_by("-start_date")
    fiscal_years = sorted({year.year for year in fiscal_years_qs}, reverse=True)

    status_choices = [choice[0] for choice in Project.STATUS_CHOICES]
    status_labels = dict(Project.STATUS_CHOICES)

    sectors = (
        Project.objects.exclude(sector__isnull=True)
        .exclude(sector="")
        .values_list("sector", flat=True)
        .distinct()
        .order_by("sector")
    )

    counties = list(
        KenyaCounty.objects.exclude(county__isnull=True)
        .exclude(county="")
        .values_list("county", flat=True)
        .distinct()
        .order_by("county")
    )
    
    # Enhanced hierarchical data
    county_subcounties = {}
    for sc in KenyaSubCounty.objects.all().order_by("county", "subcounty"):
        if sc.county and sc.subcounty:
            county_subcounties.setdefault(sc.county, []).append(sc.subcounty)

    subcounty_wards = {}
    for w in Kenyawards.objects.all().order_by("subcounty", "ward"):
        if w.subcounty and w.ward:
            subcounty_wards.setdefault(w.subcounty, []).append(w.ward)

    # Get subcounties and wards based on selected counties
    filtered_subcounties = list(
        KenyaSubCounty.objects.filter(county__in=selected_counties if selected_counties else counties)
        .exclude(subcounty__isnull=True)
        .values_list("subcounty", flat=True)
        .distinct()
        .order_by("subcounty")
    )
    
    filtered_wards = list(
        Kenyawards.objects.filter(county__in=selected_counties if selected_counties else counties)
        .exclude(ward__isnull=True)
        .values_list("ward", flat=True)
        .distinct()
        .order_by("ward")
    )

    # ---------------- Enhanced GeoJSON for Projects ----------------
    features = []
    valid_projects = 0
    
    for project in projects:
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
            # Calculate project health score
            health_score = calculate_project_health(project, current_date)
            
            features.append({
                "type": "Feature",
                "geometry": point_geom,
                "properties": {
                    "id": project.id,
                    "name": project.name,
                    "status": project.status,
                    "county": project.county,
                    "subcounty": get_subcounty_from_location(project.location) if project.location else "",
                    "ward": get_ward_from_location(project.location) if project.location else "",
                    "sector": project.sector or "",
                    "budget": float(project.budget) if project.budget else 0,
                    "start_date": project.start_date.strftime("%Y-%m-%d") if project.start_date else "",
                    "end_date": project.end_date.strftime("%Y-%m-%d") if project.end_date else "",
                    "description": project.description or "",
                    "implementing_agency": project.implementing_agency or "",
                    "contractor": project.contractor or "",
                    "project_manager": project.project_manager or "",
                    "health_score": health_score,
                    "is_delayed": project.end_date < current_date if project.end_date and project.status == 'ongoing' else False,
                    "days_remaining": (project.end_date - current_date).days if project.end_date and project.status == 'ongoing' else None,
                },
            })
            valid_projects += 1

    geojson = {
        "type": "FeatureCollection", 
        "features": features,
        "properties": {
            "total_projects": valid_projects,
            "filtered_projects": projects.count(),
            "spatial_coverage": round((valid_projects / total_projects * 100), 1) if total_projects else 0
        }
    }

    # ---------------- Enhanced Context ----------------
    context = {
        # Core metrics
        "total_projects": total_projects,
        "total_budget": total_budget,
        "county_count": county_count,
        "completion_rate": completion_rate,
        "overdue_projects": overdue_projects,
        "upcoming_deadlines": upcoming_deadlines,
        "high_risk_projects": high_risk_projects,
        
        # Enhanced statistics
        "budget_stats": budget_stats,
        "highest_budget_projects": highest_budget_projects,
        "lowest_budget_projects": lowest_budget_projects,
        "recent_projects": recent_projects,
        "status_counts": status_counts_dict,
        "status_percentages": status_percentages_dict,
        "status_labels": status_labels,
        "sector_data": sector_data,
        "county_stats": county_stats,
        "monthly_timeline": list(monthly_timeline),
        "recent_updates": recent_updates,
        "report_counts": report_counts_dict,
        "approval_rate": approval_rate,
        "budget_by_status": list(budget_by_status),
        "manager_stats": list(manager_stats),
        "projects_by_region": list(projects_by_region),
        "budget_utilization": budget_utilization,
        
        # Filter options
        "fiscal_years": fiscal_years,
        "status_choices": status_choices,
        "sectors": sectors,
        "counties": counties,
        "subcounties": filtered_subcounties,
        "wards": filtered_wards,
        
        # JSON data for JavaScript
        "county_subcounties_json": json.dumps(county_subcounties),
        "subcounty_wards_json": json.dumps(subcounty_wards),
        "geojson": json.dumps(geojson),
        
        # Current filter values
        "selected_year": selected_year or "",
        "selected_statuses": selected_statuses,
        "selected_sectors": selected_sectors,
        "selected_counties": selected_counties,
        "selected_subcounties": selected_subcounties,
        "selected_wards": selected_wards,
        "selected_counties_json": json.dumps(selected_counties),
        "selected_subcounties_json": json.dumps(selected_subcounties),
        "selected_wards_json": json.dumps(selected_wards),
        "min_budget": min_budget or "",
        "max_budget": max_budget or "",
        "start_date": start_date or "",
        "end_date": end_date or "",
        
    }
    
    return render(request, "app/home.html", context)


def calculate_project_health(project, current_date):
    """Calculate a health score for the project (0-100)"""
    score = 50  # Base score
    
    # Status-based scoring
    if project.status == 'completed':
        score += 30
    elif project.status == 'ongoing':
        score += 20
        # Check if on schedule
        if project.end_date and project.start_date:
            total_days = (project.end_date - project.start_date).days
            elapsed_days = (current_date - project.start_date).days
            if total_days > 0:
                expected_progress = elapsed_days / total_days
                # Adjust score based on progress vs time
                if expected_progress <= 1.0:
                    score += 20
                else:
                    score -= 30  # Behind schedule
    
    # Budget health
    if hasattr(project, 'budget_utilization'):
        if project.budget_utilization <= 100:
            score += 10
        else:
            score -= 20
    
    return max(0, min(100, score))


def get_subcounty_from_location(location):
    """Get subcounty name from location using spatial query"""
    if location:
        try:
            subcounty = KenyaSubCounty.objects.filter(geom__contains=location).first()
            return subcounty.subcounty if subcounty else ""
        except:
            return ""
    return ""


def get_ward_from_location(location):
    """Get ward name from location using spatial query"""
    if location:
        try:
            ward = Kenyawards.objects.filter(geom__contains=location).first()
            return ward.ward if ward else ""
        except:
            return ""
    return ""


# ---------------- Enhanced API Endpoints ----------------

def counties_geojson(request):
    """Return counties GeoJSON with enhanced statistics"""
    try:
        counties = KenyaCounty.objects.all()
        selected_counties = _clean_getlist(request, "county")
        
        if selected_counties:
            counties = counties.filter(county__in=selected_counties)
        
        features = []
        for county in counties:
            # Enhanced spatial queries
            projects_in_county = Project.objects.filter(location__within=county.geom)
            project_count = projects_in_county.count()
            total_budget = projects_in_county.aggregate(Sum('budget'))['budget__sum'] or 0
            completed_projects = projects_in_county.filter(status='completed').count()
            
            feature = {
                "type": "Feature",
                "geometry": json.loads(county.geom.geojson),
                "properties": {
                    "id": county.id,
                    "county": county.county,
                    "pop_2009": county.pop_2009,
                    "project_count": project_count,
                    "total_budget": total_budget,
                    "completed_projects": completed_projects,
                    "completion_rate": round((completed_projects / project_count * 100), 1) if project_count else 0,
                    "budget_per_capita": round(total_budget / (county.pop_2009 or 1), 2),
                    "area_sqkm": round(county.geom.area * 10000, 2)
                }
            }
            features.append(feature)
        
        return JsonResponse({
            "type": "FeatureCollection",
            "features": features
        })
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def subcounties_geojson(request):
    """Return subcounties GeoJSON with enhanced filtering"""
    try:
        county_filter = request.GET.get('county')
        selected_subcounties = _clean_getlist(request, "subcounty")
        
        if county_filter:
            subcounties = KenyaSubCounty.objects.filter(county=county_filter)
        else:
            subcounties = KenyaSubCounty.objects.all()
        
        if selected_subcounties:
            subcounties = subcounties.filter(subcounty__in=selected_subcounties)
        
        features = []
        for subcounty in subcounties:
            projects_in_subcounty = Project.objects.filter(location__within=subcounty.geom)
            project_count = projects_in_subcounty.count()
            total_budget = projects_in_subcounty.aggregate(Sum('budget'))['budget__sum'] or 0
            
            feature = {
                "type": "Feature",
                "geometry": json.loads(subcounty.geom.geojson),
                "properties": {
                    "id": subcounty.id,
                    "subcounty": subcounty.subcounty,
                    "county": subcounty.county,
                    "province": subcounty.province,
                    "project_count": project_count,
                    "total_budget": total_budget,
                    "avg_budget": round(total_budget / project_count, 2) if project_count else 0
                }
            }
            features.append(feature)
        
        return JsonResponse({
            "type": "FeatureCollection",
            "features": features
        })
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def wards_geojson(request):
    """Return wards GeoJSON with project statistics"""
    try:
        county_filter = request.GET.get('county')
        subcounty_filter = request.GET.get('subcounty')
        selected_wards = _clean_getlist(request, "ward")
        
        wards = Kenyawards.objects.all()
        
        if county_filter:
            wards = wards.filter(county=county_filter)
        if subcounty_filter:
            wards = wards.filter(subcounty=subcounty_filter)
        if selected_wards:
            wards = wards.filter(ward__in=selected_wards)
        
        features = []
        for ward in wards:
            projects_in_ward = Project.objects.filter(location__within=ward.geom)
            project_count = projects_in_ward.count()
            total_budget = projects_in_ward.aggregate(Sum('budget'))['budget__sum'] or 0
            
            feature = {
                "type": "Feature",
                "geometry": json.loads(ward.geom.geojson),
                "properties": {
                    "id": ward.id,
                    "ward": ward.ward,
                    "subcounty": ward.subcounty,
                    "county": ward.county,
                    "project_count": project_count,
                    "total_budget": total_budget,
                    "project_density": round(project_count / (ward.geom.area * 10000), 4) if ward.geom.area else 0
                }
            }
            features.append(feature)
        
        return JsonResponse({
            "type": "FeatureCollection",
            "features": features
        })
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def project_locations_geojson(request):
    """API endpoint for filtered project locations"""
    try:
        # Apply the same filters as the main view
        projects = Project.objects.all()
        
        # Apply filters from request
        selected_year = _clean_get(request, "year")
        selected_statuses = _clean_getlist(request, "status")
        selected_sectors = _clean_getlist(request, "sector")
        selected_counties = _clean_getlist(request, "county")
        
        if selected_year:
            projects = projects.filter(start_date__year=selected_year)
        if selected_statuses:
            projects = projects.filter(status__in=selected_statuses)
        if selected_sectors:
            projects = projects.filter(sector__in=selected_sectors)
        if selected_counties:
            projects = projects.filter(county__in=selected_counties)
        
        # Build GeoJSON
        features = []
        for project in projects:
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
                features.append({
                    "type": "Feature",
                    "geometry": point_geom,
                    "properties": {
                        "id": project.id,
                        "name": project.name,
                        "status": project.status,
                        "county": project.county,
                        "sector": project.sector or "",
                        "budget": float(project.budget) if project.budget else 0,
                    }
                })
        
        return JsonResponse({
            "type": "FeatureCollection",
            "features": features
        })
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
    

def spatial_statistics(request):
    """Enhanced spatial analytics endpoint"""
    try:
        # Regional analysis
        counties = KenyaCounty.objects.all()
        regional_stats = []
        
        for county in counties:
            projects_in_county = Project.objects.filter(location__within=county.geom)
            project_count = projects_in_county.count()
            
            if project_count > 0:
                stats = projects_in_county.aggregate(
                    total_budget=Sum('budget'),
                    avg_budget=Avg('budget'),
                    completed=Count('id', filter=Q(status='completed')),
                    delayed=Count('id', filter=Q(status='delayed')),
                    high_budget=Count('id', filter=Q(budget__gt=Avg('budget')))
                )
                
                regional_stats.append({
                    'county': county.county,
                    'project_count': project_count,
                    'total_budget': stats['total_budget'] or 0,
                    'completion_rate': round((stats['completed'] / project_count * 100), 1),
                    'delay_rate': round((stats['delayed'] / project_count * 100), 1),
                    'high_budget_projects': stats['high_budget'] or 0,
                    'budget_per_capita': round((stats['total_budget'] or 0) / (county.pop_2009 or 1), 2)
                })
        
        # Spatial distribution analysis
        spatial_distribution = {
            'urban_counties': regional_stats[:5],  # Top 5 by project count
            'rural_counties': regional_stats[-5:],  # Bottom 5 by project count
            'total_regions': len(regional_stats),
            'avg_projects_per_county': round(sum(s['project_count'] for s in regional_stats) / len(regional_stats), 1)
        }
        
        return JsonResponse({
            'regional_stats': regional_stats,
            'spatial_distribution': spatial_distribution,
            'summary': {
                'total_counties_covered': len([s for s in regional_stats if s['project_count'] > 0]),
                'total_budget_allocation': sum(s['total_budget'] for s in regional_stats),
                'avg_completion_rate': round(sum(s['completion_rate'] for s in regional_stats) / len(regional_stats), 1)
            }
        })
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


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
            avg_duration=Avg(ExpressionWrapper(F('end_date') - F('start_date'), output_field=DurationField()))
        )
        
        # Risk analysis
        current_date = timezone.now().date()
        risk_analysis = {
            'overdue_projects': projects.filter(status='ongoing', end_date__lt=current_date).count(),
            'high_budget_risk': projects.filter(budget__gt=performance_metrics['avg_budget'] * 2).count(),
            'delayed_projects': projects.filter(status='delayed').count(),
            'low_progress_projects': projects.filter(progress__lt=25).count()  # Assuming progress field
        }
        
        # Sector analysis
        sector_analysis = list(projects.values('sector').annotate(
            count=Count('id'),
            total_budget=Sum('budget'),
            completed=Count('id', filter=Q(status='completed')),
            avg_completion_time=Avg(ExpressionWrapper(F('end_date') - F('start_date'), output_field=DurationField()))
        ).order_by('-total_budget'))
        
        return JsonResponse({
            'performance_metrics': performance_metrics,
            'risk_analysis': risk_analysis,
            'sector_analysis': sector_analysis,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)






# ---------------- Dashboard View ---------------- #
def dashboard(request):
    # Apply filters if any
    filters = Q()

    # Status filter
    status_filter = request.GET.getlist('status')
    if status_filter:
        filters &= Q(status__in=status_filter)

    # County filter
    county_filter = request.GET.getlist('county')
    if county_filter:
        filters &= Q(county__in=county_filter)

    # Sector filter
    sector_filter = request.GET.getlist('sector')
    if sector_filter:
        filters &= Q(sector__in=sector_filter)

    # Budget range filter
    min_budget = request.GET.get('min_budget')
    max_budget = request.GET.get('max_budget')
    if min_budget and min_budget != '':
        try:
            filters &= Q(budget__gte=Decimal(min_budget))
        except Exception:
            pass
    if max_budget and max_budget != '':
        try:
            filters &= Q(budget__lte=Decimal(max_budget))
        except Exception:
            pass

    # Date range filter
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date and start_date != '':
        filters &= Q(start_date__gte=start_date)
    if end_date and end_date != '':
        filters &= Q(end_date__lte=end_date)

    # Apply filters to projects
    projects = Project.objects.filter(filters)

    # Key Metrics
    total_projects = projects.count()
    total_budget = projects.aggregate(
        total=Sum("budget")
    )["total"] or 0

    # Calculate completion rate
    completed_projects = projects.filter(status='completed').count()
    completion_rate = round((completed_projects / total_projects) * 100, 1) if total_projects > 0 else 0

    # Calculate average budget
    avg_budget = projects.aggregate(avg=Avg('budget'))['avg'] or 0

    # Calculate time metrics
    now = timezone.now().date()
    
    # Projects behind schedule (past end date but not completed)
    behind_schedule = projects.filter(
        end_date__lt=now
    ).exclude(status='completed').count()
    
    # Projects ahead of schedule (completed before end date)
    ahead_of_schedule = projects.filter(
        status='completed',
        end_date__gt=F('actual_completion_date')
    ).count() if hasattr(Project, 'actual_completion_date') else 0

    # Status Distribution
    status_distribution = projects.values('status').annotate(count=Count('id'))
    status_data = {status[0]: 0 for status in Project.STATUS_CHOICES}
    for item in status_distribution:
        status_data[item['status']] = item['count']

    # Budget by Sector
    sector_budget = (
        projects.values('sector')
        .annotate(total_budget=Sum('budget'))
        .order_by('-total_budget')[:10]
    )
    sector_labels = [item['sector'] or 'Unknown' for item in sector_budget]
    sector_values = [float(item['total_budget'] or 0) for item in sector_budget]

    # Projects by County
    county_counts = (
        projects.values('county')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    county_labels = [item['county'] for item in county_counts]
    county_values = [item['count'] for item in county_counts]

    # Monthly Project Timeline
    monthly_timeline = (
        projects.annotate(month=TruncMonth('start_date'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    timeline_labels = [item['month'].strftime('%b %Y') for item in monthly_timeline]
    timeline_values = [item['count'] for item in monthly_timeline]

    # Budget Utilization by Status
    budget_by_status = (
        projects.values('status')
        .annotate(total_budget=Sum('budget'))
        .order_by('status')
    )
    budget_status_labels = [dict(Project.STATUS_CHOICES).get(item['status'], item['status']) for item in budget_by_status]
    budget_status_values = [float(item['total_budget'] or 0) for item in budget_by_status]

    # Top Performing Counties by Completion Rate
    county_performance = []
    for county in projects.values_list('county', flat=True).distinct():
        county_projects = projects.filter(county=county)
        total = county_projects.count()
        completed = county_projects.filter(status='completed').count()
        rate = round((completed / total) * 100, 1) if total > 0 else 0
        county_performance.append({
            'county': county,
            'completion_rate': rate,
            'total_projects': total
        })
    
    # Sort by completion rate and take top 5
    county_performance = sorted(county_performance, key=lambda x: x['completion_rate'], reverse=True)[:5]
    performance_labels = [item['county'] for item in county_performance]
    performance_values = [item['completion_rate'] for item in county_performance]

    # Recent Updates
    recent_updates = ProjectUpdate.objects.select_related('project').order_by('-created_at')[:5]

    # Citizen Reports Summary
    report_summary = CitizenReport.objects.values('report_type').annotate(
        count=Count('id'),
        approved=Count('id', filter=Q(is_approved=True))
    ).order_by('report_type')

    # Status Choices
    status_choices = Project.STATUS_CHOICES

    # Counties
    counties = Project.objects.values_list("county", flat=True).distinct().order_by("county")

    # Sectors
    sectors = Project.objects.values_list("sector", flat=True).distinct().order_by("sector")

    # GeoJSON for Map
    features = []
    for project in projects:
        if project.location:
            lng, lat = project.location.x, project.location.y
        elif project.longitude and project.latitude:
            lng, lat = float(project.longitude), float(project.latitude)
        else:
            continue

        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lng, lat],
                },
                "properties": {
                    "id": project.id,
                    "project_id": project.project_id,
                    "name": project.name,
                    "status": project.status,
                    "county": project.county,
                    "sector": project.sector,
                    "budget": float(project.budget) if project.budget else None,
                    "start_date": project.start_date.strftime("%Y-%m-%d") if project.start_date else None,
                    "end_date": project.end_date.strftime("%Y-%m-%d") if project.end_date else None,
                    "description": project.description or "",
                    "implementing_agency": project.implementing_agency or "",
                    "contractor": project.contractor or "",
                },
            }
        )
    geojson = {"type": "FeatureCollection", "features": features}

    # Context
    context = {
        "total_projects": total_projects,
        "total_budget": total_budget,
        "completion_rate": completion_rate,
        "avg_budget": avg_budget,
        "behind_schedule": behind_schedule,
        "ahead_of_schedule": ahead_of_schedule,
        "status_choices": status_choices,
        "counties": counties,
        "sectors": sectors,
        "projects": projects,
        "geojson": json.dumps(geojson),
        "status_data": status_data,
        "sector_labels": json.dumps(sector_labels),
        "sector_values": json.dumps(sector_values),
        "county_labels": json.dumps(county_labels),
        "county_values": json.dumps(county_values),
        "timeline_labels": json.dumps(timeline_labels),
        "timeline_values": json.dumps(timeline_values),
        "budget_status_labels": json.dumps(budget_status_labels),
        "budget_status_values": json.dumps(budget_status_values),
        "performance_labels": json.dumps(performance_labels),
        "performance_values": json.dumps(performance_values),
        "recent_updates": recent_updates,
        "report_summary": report_summary,
        # selected filters for dropdowns
        "selected_statuses": status_filter,
        "selected_counties": county_filter,
        "selected_sectors": sector_filter,
    }

    return render(request, "app/dashboard.html", context)

# ---------------- Other views remain the same ---------------- #
# ... (home, ProjectListView, ProjectDetailView, project_map_view, submit_report, about, contact)


# ---------------- List + Detail ---------------- #
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
            except (ValueError, InvalidOperation):
                pass
        if max_budget:
            try:
                queryset = queryset.filter(budget__lte=Decimal(max_budget))
            except (ValueError, InvalidOperation):
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


# ---------------- Project Map ---------------- #
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

# ---------------- Citizen Report ---------------- #
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


# ---------------- Static Pages ---------------- #
def about(request):
    return render(request, 'app/about.html')


def contact(request):
    return render(request, 'app/contact.html')

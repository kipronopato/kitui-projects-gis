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







def _clean_get(request, name):
    """Return single GET param; treat 'None' or empty as None."""
    v = request.GET.get(name)
    return None if (v is None or v == "None" or v == "") else v

def _clean_getlist(request, name):
    """Return list cleaned of empty/'None' entries."""
    return [v for v in request.GET.getlist(name) if v and v != "None"]

def home(request):
    """Enhanced dashboard view with comprehensive analytics and filtering"""
    try:
        # Start with all projects across all counties
        projects = Project.objects.all().select_related().prefetch_related('updates', 'citizen_reports')

        # ---------------- Enhanced Filters ----------------
        selected_county = _clean_get(request, "county")
        selected_year = _clean_get(request, "year")
        selected_statuses = _clean_getlist(request, "status")
        selected_sectors = _clean_getlist(request, "sector")
        selected_subcounties = _clean_getlist(request, "subcounty")
        selected_wards = _clean_getlist(request, "ward")
        min_budget = _clean_get(request, "min_budget")
        max_budget = _clean_get(request, "max_budget")
        start_date = _clean_get(request, "start_date")
        end_date = _clean_get(request, "end_date")
        map_layer = _clean_get(request, "map_layer") or "wards"
        search_query = _clean_get(request, "search")

        # Apply enhanced filters
        if selected_county:
            projects = projects.filter(county__iexact=selected_county)
        
        if selected_year:
            projects = projects.filter(start_date__year=selected_year)
        
        if selected_statuses:
            projects = projects.filter(status__in=selected_statuses)
        
        if selected_sectors:
            projects = projects.filter(sector__in=selected_sectors)

        # Enhanced spatial filtering with hierarchical support
        if selected_subcounties:
            try:
                subcounty_geoms = KenyaSubCounty.objects.filter(subcounty__in=selected_subcounties)
                if selected_county:
                    subcounty_geoms = subcounty_geoms.filter(county__iexact=selected_county)
                    
                if subcounty_geoms.exists():
                    combined_geom = subcounty_geoms.aggregate(union=Union('geom'))['union']
                    if combined_geom:
                        projects = projects.filter(location__within=combined_geom)
            except Exception as e:
                print(f"Error in subcounty filtering: {e}")

        if selected_wards:
            try:
                ward_geoms = Kenyawards.objects.filter(ward__in=selected_wards)
                if selected_county:
                    ward_geoms = ward_geoms.filter(county__iexact=selected_county)
                    
                if ward_geoms.exists():
                    combined_geom = ward_geoms.aggregate(union=Union('geom'))['union']
                    if combined_geom:
                        projects = projects.filter(location__within=combined_geom)
            except Exception as e:
                print(f"Error in ward filtering: {e}")

        # Budget filters with validation
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

        # Date range filters
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

        # Search functionality
        if search_query:
            projects = projects.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(sector__icontains=search_query) |
                Q(project_manager__icontains=search_query) |
                Q(county__icontains=search_query)
            )

        # ---------------- Enhanced Analytics & Metrics ----------------
        current_date = timezone.now().date()
        
        # Core metrics with error handling
        try:
            total_projects = projects.count()
            total_budget = projects.aggregate(total=Sum("budget"))["total"] or 0
        except Exception as e:
            print(f"Error calculating core metrics: {e}")
            total_projects = 0
            total_budget = 0

        # Population calculations
        try:
            if selected_county:
                county_obj = KenyaCounty.objects.filter(county__iexact=selected_county).first()
                county_population = county_obj.pop_2009 if county_obj else 1
                budget_per_capita = total_budget / county_population if county_population else 0
            else:
                total_population = KenyaCounty.objects.aggregate(Sum('pop_2009'))['pop_2009__sum'] or 1
                budget_per_capita = total_budget / total_population if total_population else 0
                county_population = total_population
        except Exception as e:
            print(f"Error in population calculations: {e}")
            county_population = 1
            budget_per_capita = 0

        # Enhanced budget analytics
        try:
            budget_stats = projects.aggregate(
                avg_budget=Avg("budget"),
                min_budget=Min("budget"),
                max_budget=Max("budget"),
                total_budget=Sum("budget")
            )
        except Exception as e:
            print(f"Error in budget analytics: {e}")
            budget_stats = {
                'avg_budget': 0,
                'min_budget': 0,
                'max_budget': 0,
                'total_budget': 0
            }

        # Project performance metrics
        try:
            completed_projects = projects.filter(status="completed").count()
            ongoing_projects = projects.filter(status="ongoing").count()
            delayed_projects = projects.filter(status="delayed").count()
            planned_projects = projects.filter(status="planned").count()
            
            completion_rate = round((completed_projects / total_projects * 100), 1) if total_projects else 0
            ongoing_rate = round((ongoing_projects / total_projects * 100), 1) if total_projects else 0
        except Exception as e:
            print(f"Error in performance metrics: {e}")
            completed_projects = ongoing_projects = delayed_projects = planned_projects = 0
            completion_rate = ongoing_rate = 0

        # Timeline and scheduling analytics
        try:
            overdue_projects = projects.filter(
                Q(status="ongoing") & Q(end_date__lt=current_date)
            ).count()
            
            upcoming_deadlines = projects.filter(
                Q(status="ongoing"),
                end_date__gte=current_date,
                end_date__lte=current_date + timedelta(days=30),
            ).count()

            high_risk_projects = projects.filter(
                Q(status='delayed') | 
                Q(end_date__lt=current_date) |
                Q(budget__gt=Avg('budget') * 2)
            ).count()
        except Exception as e:
            print(f"Error in timeline analytics: {e}")
            overdue_projects = upcoming_deadlines = high_risk_projects = 0

        # Enhanced project lists with ranking
        try:
            highest_budget_projects = projects.order_by("-budget")[:10]
            lowest_budget_projects = projects.order_by("budget")[:10]
            recent_projects = projects.order_by("-start_date")[:10]
            
            risky_projects = projects.filter(
                Q(status='delayed') | 
                Q(end_date__lt=current_date)
            )[:15]
        except Exception as e:
            print(f"Error in project lists: {e}")
            highest_budget_projects = lowest_budget_projects = recent_projects = risky_projects = Project.objects.none()

        # Status analytics with enhanced metrics - FOR CHARTS
        status_counts_dict = {}
        status_counts_chart = {}
        try:
            status_distribution = projects.values("status").annotate(
                count=Count("id")
            ).order_by("status")
            
            for item in status_distribution:
                status_counts_dict[item["status"]] = {
                    'count': item["count"],
                    'total_budget': 0,
                    'avg_budget': 0,
                    'delayed': 0,
                    'completion_rate': 0,
                    'avg_duration': None
                }
                status_counts_chart[item["status"]] = item["count"]

            # Complete status analytics with budget data
            status_analytics = projects.values("status").annotate(
                count=Count("id"),
                total_budget=Sum("budget"),
                avg_budget=Avg("budget"),
                delayed_count=Count("id", filter=Q(end_date__lt=current_date, status='ongoing')),
                completion_rate=Count("id", filter=Q(status='completed')) * 100 / Count('id'),
                avg_duration=Avg(ExpressionWrapper(F('end_date') - F('start_date'), output_field=DurationField()))
            )
            
            for item in status_analytics:
                if item["status"] in status_counts_dict:
                    status_counts_dict[item["status"]].update({
                        'total_budget': item["total_budget"] or 0,
                        'avg_budget': item["avg_budget"] or 0,
                        'delayed': item["delayed_count"],
                        'completion_rate': item["completion_rate"] or 0,
                        'avg_duration': item["avg_duration"]
                    })
        except Exception as e:
            print(f"Error in status analytics: {e}")

        # Enhanced sector analytics
        sector_data = []
        sector_data_chart = []
        try:
            sector_analytics = projects.values("sector").annotate(
                count=Count("id"), 
                total_budget=Sum("budget"), 
                avg_budget=Avg("budget"),
                completed=Count("id", filter=Q(status="completed")),
                ongoing=Count("id", filter=Q(status="ongoing")),
                delayed=Count("id", filter=Q(status="delayed")),
                planned=Count("id", filter=Q(status="planned"))
            ).order_by("-count")

            for item in sector_analytics:
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
                    "ongoing": item["ongoing"],
                    "delayed": item["delayed"],
                    "planned": item["planned"]
                })
                sector_data_chart.append({
                    "sector": item["sector"] or "Not Specified",
                    "count": item["count"]
                })
        except Exception as e:
            print(f"Error in sector analytics: {e}")

        # Enhanced geographic analytics
        county_stats = []
        try:
            all_counties = KenyaCounty.objects.all()
            
            for county in all_counties:
                county_projects = projects.filter(county__iexact=county.county)
                project_count = county_projects.count()
                if project_count > 0:
                    county_budget = county_projects.aggregate(Sum('budget'))['budget__sum'] or 0
                    
                    county_stats.append({
                        "county": county.county,
                        "count": project_count,
                        "total_budget": county_budget,
                        "avg_budget": county_budget / project_count,
                        "completed": county_projects.filter(status='completed').count(),
                        "ongoing": county_projects.filter(status='ongoing').count(),
                        "delayed": county_projects.filter(status='delayed').count(),
                        "completion_rate": round((county_projects.filter(status='completed').count() / project_count * 100), 1),
                        "population": county.pop_2009,
                        "budget_per_capita": round(county_budget / county.pop_2009, 2) if county.pop_2009 else 0
                    })
            
            county_stats = sorted(county_stats, key=lambda x: x['count'], reverse=True)
        except Exception as e:
            print(f"Error in county analytics: {e}")

        # Subcounty analytics
        subcounty_stats = []
        try:
            subcounties_query = KenyaSubCounty.objects.all()
            if selected_county:
                subcounties_query = subcounties_query.filter(county__iexact=selected_county)
            
            for subcounty in subcounties_query:
                try:
                    subcounty_projects = projects.filter(location__within=subcounty.geom)
                    project_count = subcounty_projects.count()
                    if project_count > 0:
                        subcounty_budget = subcounty_projects.aggregate(Sum('budget'))['budget__sum'] or 0
                        
                        subcounty_stats.append({
                            "subcounty": subcounty.subcounty,
                            "county": subcounty.county,
                            "count": project_count,
                            "total_budget": subcounty_budget,
                            "avg_budget": subcounty_budget / project_count,
                            "completed": subcounty_projects.filter(status='completed').count(),
                            "ongoing": subcounty_projects.filter(status='ongoing').count(),
                            "completion_rate": round((subcounty_projects.filter(status='completed').count() / project_count * 100), 1)
                        })
                except Exception as e:
                    print(f"Error processing subcounty {subcounty.subcounty}: {e}")
                    continue
            
            subcounty_stats = sorted(subcounty_stats, key=lambda x: x['count'], reverse=True)
        except Exception as e:
            print(f"Error in subcounty analytics: {e}")

        # Ward analytics - FIXED with comprehensive error handling
        ward_stats = []
        try:
            wards_query = Kenyawards.objects.all()
            if selected_county:
                wards_query = wards_query.filter(county__iexact=selected_county)
            
            # Process wards in batches to avoid memory issues
            for ward in wards_query:
                try:
                    ward_projects = projects.filter(location__within=ward.geom)
                    project_count = ward_projects.count()
                    
                    if project_count > 0:
                        ward_budget = ward_projects.aggregate(Sum('budget'))['budget__sum'] or 0
                        
                        ward_stats.append({
                            "ward": ward.ward,
                            "subcounty": ward.subcounty,
                            "county": ward.county,
                            "count": project_count,
                            "total_budget": ward_budget,
                            "avg_budget": ward_budget / project_count,
                            "completed": ward_projects.filter(status='completed').count(),
                            "completion_rate": round((ward_projects.filter(status='completed').count() / project_count * 100), 1) if project_count else 0
                        })
                except Exception as e:
                    print(f"Error processing ward {ward.ward}: {str(e)}")
                    continue

            ward_stats = sorted(ward_stats, key=lambda x: x['count'], reverse=True)[:20]
        except Exception as e:
            print(f"Error in ward analytics: {e}")

        # Enhanced timeline analytics
        monthly_timeline = []
        yearly_timeline = []
        monthly_timeline_data = {}
        try:
            monthly_timeline = (
                projects.annotate(month=TruncMonth("start_date"))
                .values("month")
                .annotate(
                    count=Count("id"),
                    total_budget=Sum("budget"),
                    avg_budget=Avg("budget")
                )
                .order_by("month")
            )

            yearly_timeline = (
                projects.annotate(year=ExtractYear("start_date"))
                .values("year")
                .annotate(
                    count=Count("id"),
                    total_budget=Sum("budget")
                )
                .order_by("year")
            )

            # Monthly timeline for charts
            for item in monthly_timeline:
                if item['month']:
                    month_key = item['month'].strftime('%Y-%m')
                    monthly_timeline_data[month_key] = item['count']
        except Exception as e:
            print(f"Error in timeline analytics: {e}")

        # Recent activity tracking
        recent_updates = []
        new_projects = 0
        recent_updates_count = 0
        try:
            recent_updates = ProjectUpdate.objects.select_related("project")
            if selected_county:
                recent_updates = recent_updates.filter(project__county__iexact=selected_county)
            recent_updates = recent_updates.order_by("-created_at")[:15]

            # New projects and updates for alerts
            new_projects = projects.filter(created_at__gte=current_date - timedelta(days=7)).count()
            
            recent_updates_query = ProjectUpdate.objects.all()
            if selected_county:
                recent_updates_query = recent_updates_query.filter(project__county__iexact=selected_county)
            recent_updates_count = recent_updates_query.filter(
                created_at__gte=current_date - timedelta(days=3)
            ).count()
        except Exception as e:
            print(f"Error in activity tracking: {e}")

        # Enhanced citizen engagement analytics
        report_counts_dict = {}
        approval_rate = 0
        try:
            report_analytics = CitizenReport.objects.select_related("project")
            if selected_county:
                report_analytics = report_analytics.filter(project__county__iexact=selected_county)
            
            report_analytics = report_analytics.values("report_type").annotate(
                count=Count("id"),
                approved=Count("id", filter=Q(is_approved=True)),
                recent=Count("id", filter=Q(created_at__gte=current_date - timedelta(days=30))),
                avg_approval_time=Avg(ExpressionWrapper(F('created_at') - F('project__created_at'), output_field=DurationField()))
            )
            
            for item in report_analytics:
                report_counts_dict[item["report_type"]] = {
                    'total': item["count"],
                    'approved': item["approved"],
                    'recent': item["recent"],
                    'approval_rate': round((item["approved"] / item["count"] * 100), 1) if item["count"] else 0,
                    'avg_approval_time': item["avg_approval_time"]
                }
            
            approved_reports_query = CitizenReport.objects.filter(is_approved=True)
            total_reports_query = CitizenReport.objects.all()
            
            if selected_county:
                approved_reports_query = approved_reports_query.filter(project__county__iexact=selected_county)
                total_reports_query = total_reports_query.filter(project__county__iexact=selected_county)
            
            approved_reports = approved_reports_query.count()
            total_reports = total_reports_query.count()
            approval_rate = round((approved_reports / total_reports * 100), 1) if total_reports else 0
        except Exception as e:
            print(f"Error in citizen engagement analytics: {e}")

        # Budget distribution analytics - FOR CHARTS
        budget_by_status_chart = []
        budget_by_sector = []
        try:
            budget_by_status = (
                projects.values("status")
                .annotate(total_budget=Sum("budget"))
                .order_by("status")
            )

            for item in budget_by_status:
                budget_by_status_chart.append({
                    "status": item["status"],
                    "total_budget": float(item["total_budget"] or 0)
                })

            budget_by_sector = (
                projects.values("sector")
                .annotate(total_budget=Sum("budget"))
                .order_by("-total_budget")[:10]
            )
        except Exception as e:
            print(f"Error in budget distribution analytics: {e}")

        # Enhanced manager performance analytics
        manager_stats = []
        try:
            manager_stats = (
                projects.values("project_manager")
                .annotate(
                    count=Count("id"),
                    completed=Count("id", filter=Q(status="completed")),
                    total_budget=Sum("budget"),
                    avg_budget=Avg("budget"),
                    completion_rate=Count("id", filter=Q(status="completed")) * 100 / Count('id'),
                    avg_completion_time=Avg(
                        ExpressionWrapper(F('end_date') - F('start_date'), output_field=DurationField()),
                        filter=Q(status="completed")
                    ),
                    delayed_projects=Count("id", filter=Q(status="delayed"))
                )
                .exclude(project_manager="")
                .order_by("-count")[:10]
            )
        except Exception as e:
            print(f"Error in manager analytics: {e}")

        # Risk and performance analytics
        performance_metrics = {
            'efficiency_score': 0,
            'spatial_distribution_score': 0,
            'budget_utilization_score': 0,
            'timeline_adherence_score': 0,
            'citizen_engagement_score': 0
        }
        try:
            performance_metrics = {
                'efficiency_score': calculate_efficiency_score(projects, current_date),
                'spatial_distribution_score': calculate_spatial_distribution_score(projects, subcounties_query),
                'budget_utilization_score': calculate_budget_utilization_score(projects),
                'timeline_adherence_score': calculate_timeline_adherence_score(projects, current_date),
                'citizen_engagement_score': calculate_citizen_engagement_score(projects)
            }
        except Exception as e:
            print(f"Error in performance metrics: {e}")

        # ---------------- Enhanced Dropdown Data ----------------
        fiscal_years = []
        status_choices = []
        status_labels = {}
        sectors = []
        counties = []
        subcounties = []
        wards = []
        county_subcounties = {}
        subcounty_wards = {}

        try:
            fiscal_years_qs = Project.objects.dates("start_date", "year").order_by("-start_date")
            fiscal_years = sorted({year.year for year in fiscal_years_qs}, reverse=True)

            status_choices = [choice[0] for choice in Project.STATUS_CHOICES]
            status_labels = dict(Project.STATUS_CHOICES)

            sectors = (
                Project.objects
                .exclude(sector__isnull=True)
                .exclude(sector="")
                .values_list("sector", flat=True)
                .distinct()
                .order_by("sector")
            )

            # Administrative hierarchies
            counties = list(
                KenyaCounty.objects
                .exclude(county__isnull=True)
                .values_list("county", flat=True)
                .distinct()
                .order_by("county")
            )
            
            subcounties = list(
                KenyaSubCounty.objects
                .exclude(subcounty__isnull=True)
                .values_list("subcounty", flat=True)
                .distinct()
                .order_by("subcounty")
            )
            
            if selected_county:
                subcounties = list(
                    KenyaSubCounty.objects.filter(county__iexact=selected_county)
                    .exclude(subcounty__isnull=True)
                    .values_list("subcounty", flat=True)
                    .distinct()
                    .order_by("subcounty")
                )
            
            wards = list(
                Kenyawards.objects
                .exclude(ward__isnull=True)
                .values_list("ward", flat=True)
                .distinct()
                .order_by("ward")
            )
            
            if selected_county:
                wards = list(
                    Kenyawards.objects.filter(county__iexact=selected_county)
                    .exclude(ward__isnull=True)
                    .values_list("ward", flat=True)
                    .distinct()
                    .order_by("ward")
                )

            # Enhanced hierarchical data for JavaScript
            for sc in KenyaSubCounty.objects.all().order_by("county", "subcounty"):
                if sc.county and sc.subcounty:
                    county_subcounties.setdefault(sc.county, []).append(sc.subcounty)

            for w in Kenyawards.objects.all().order_by("subcounty", "ward"):
                if w.subcounty and w.ward:
                    subcounty_wards.setdefault(w.subcounty, []).append(w.ward)
        except Exception as e:
            print(f"Error loading dropdown data: {e}")

        # ---------------- Enhanced GeoJSON for Interactive Map ----------------
        features = []
        valid_projects = 0
        
        try:
            for project in projects:
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
                    health_score = calculate_project_health(project, current_date)
                    risk_level = calculate_risk_level(project, current_date)
                    
                    features.append({
                        "type": "Feature",
                        "geometry": point_geom,
                        "properties": {
                            "id": project.id,
                            "name": project.name,
                            "county": project.county or "",
                            "status": project.status,
                            "sector": project.sector or "",
                            "budget": float(project.budget) if project.budget else 0,
                            "start_date": project.start_date.strftime("%Y-%m-%d") if project.start_date else "",
                            "end_date": project.end_date.strftime("%Y-%m-%d") if project.end_date else "",
                            "project_manager": project.project_manager or "",
                            "health_score": health_score,
                            "risk_level": risk_level,
                            "is_delayed": project.end_date < current_date if project.end_date and project.status == 'ongoing' else False,
                            "days_remaining": (project.end_date - current_date).days if project.end_date and project.status == 'ongoing' else None,
                            "update_count": project.updates.count(),
                            "report_count": project.citizen_reports.count()
                        },
                    })
                    valid_projects += 1

            geojson = {
                "type": "FeatureCollection", 
                "features": features,
                "properties": {
                    "total_projects": valid_projects,
                    "selected_county": selected_county or "All Counties",
                    "population": county_population,
                    "total_budget": float(total_budget),
                    "avg_budget": float(budget_stats['avg_budget'] or 0)
                }
            }
        except Exception as e:
            print(f"Error generating GeoJSON: {e}")
            geojson = {"type": "FeatureCollection", "features": [], "properties": {}}

        # ---------------- Enhanced Context for Template ----------------
        context = {
            # Core metrics
            "total_projects": total_projects,
            "total_budget": total_budget,
            "budget_per_capita": round(budget_per_capita, 2),
            "county_population": county_population,
            "completion_rate": completion_rate,
            "ongoing_rate": ongoing_rate,
            "overdue_projects": overdue_projects,
            "upcoming_deadlines": upcoming_deadlines,
            "high_risk_projects": high_risk_projects,
            "new_projects": new_projects,
            "recent_updates_count": recent_updates_count,
            "current_date": current_date,
            # Enhanced analytics
            "budget_stats": budget_stats,
            "highest_budget_projects": highest_budget_projects,
            "lowest_budget_projects": lowest_budget_projects,
            "recent_projects": recent_projects,
            "risky_projects": risky_projects,
            "status_counts": status_counts_dict,
            "status_labels": status_labels,
            "sector_data": sector_data,
            "county_stats": county_stats,
            "subcounty_stats": subcounty_stats,
            "ward_stats": ward_stats,
            "monthly_timeline": list(monthly_timeline),
            "yearly_timeline": list(yearly_timeline),
            "recent_updates": recent_updates,
            "report_counts": report_counts_dict,
            "approval_rate": approval_rate,
            "budget_by_status": list(budget_by_status_chart),
            "budget_by_sector": list(budget_by_sector),
            "manager_stats": list(manager_stats),
            "performance_metrics": performance_metrics,
            
            # Filter options
            "fiscal_years": fiscal_years,
            "status_choices": status_choices,
            "sectors": sectors,
            "counties": counties,
            "subcounties": subcounties,
            "wards": wards,
            "selected_county": selected_county or "",
            
            # JSON data for JavaScript
            "county_subcounties_json": json.dumps(county_subcounties),
            "subcounty_wards_json": json.dumps(subcounty_wards),
            "geojson": json.dumps(geojson),
            
            # CHART DATA - NEW ADDITIONS
            "status_counts_json": json.dumps(status_counts_chart),
            "status_labels_json": json.dumps(status_labels),
            "sector_data_json": json.dumps(sector_data_chart[:8]),  # Top 8 sectors for chart
            "budget_by_status_json": json.dumps(budget_by_status_chart),
            "monthly_timeline_json": json.dumps(monthly_timeline_data),
            
            # Current filter values
            "selected_year": selected_year or "",
            "selected_statuses": selected_statuses,
            "selected_sectors": selected_sectors,
            "selected_subcounties": selected_subcounties,
            "selected_wards": selected_wards,
            "map_layer": map_layer,
            "search_query": search_query or "",
            "selected_subcounties_json": json.dumps(selected_subcounties),
            "selected_wards_json": json.dumps(selected_wards),
            "min_budget": min_budget or "",
            "max_budget": max_budget or "",
            "start_date": start_date or "",
            "end_date": end_date or "",
        }
        
        return render(request, "app/home.html", context)
        
    except Exception as e:
        print(f"Critical error in home view: {e}")
        # Return a basic error context
        return render(request, "app/home.html", {
            "total_projects": 0,
            "total_budget": 0,
            "error": "An error occurred while loading the dashboard. Please try again."
        })

# Enhanced utility functions
def calculate_project_health(project, current_date):
    """Calculate comprehensive health score (0-100)"""
    score = 50  # Base score
    
    # Status-based scoring
    status_scores = {
        'completed': 30,
        'ongoing': 20,
        'planned': 10,
        'delayed': -20
    }
    score += status_scores.get(project.status, 0)
    
    # Timeline health
    if project.end_date and project.start_date:
        total_days = (project.end_date - project.start_date).days
        if total_days > 0 and project.status == 'ongoing':
            elapsed_days = (current_date - project.start_date).days
            expected_progress = elapsed_days / total_days
            if expected_progress <= 1.0:
                progress_score = (1 - expected_progress) * 20
                score += progress_score
            else:
                score -= 30
    
    return max(0, min(100, round(score)))

def calculate_risk_level(project, current_date):
    """Calculate project risk level"""
    risk_score = 0
    
    # Status risk
    if project.status == 'delayed':
        risk_score += 3
    
    # Timeline risk
    if project.end_date and project.status == 'ongoing':
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
    
    efficiency = (on_time / completed.count() * 100)
    return round(efficiency, 1)

def calculate_spatial_distribution_score(projects, subcounties):
    """Calculate spatial distribution evenness"""
    if projects.count() == 0 or subcounties.count() == 0:
        return 0
    
    projects_per_subcounty = []
    for subcounty in subcounties:
        count = projects.filter(location__within=subcounty.geom).count()
        projects_per_subcounty.append(count)
    
    avg_projects = sum(projects_per_subcounty) / len(projects_per_subcounty)
    if avg_projects == 0:
        return 0
    
    distribution_score = min(100, (avg_projects / max(projects_per_subcounty)) * 100)
    return round(distribution_score, 1)

def calculate_budget_utilization_score(projects):
    """Calculate budget utilization efficiency"""
    if projects.count() == 0:
        return 0
    
    total_budget = projects.aggregate(Sum('budget'))['budget__sum'] or 0
    completed_budget = projects.filter(status='completed').aggregate(Sum('budget'))['budget__sum'] or 0
    
    # Use completion rate as proxy for budget utilization
    utilization = (completed_budget / total_budget * 100) if total_budget > 0 else 0
    return round(utilization, 1)

def calculate_timeline_adherence_score(projects, current_date):
    """Calculate timeline adherence score"""
    if projects.count() == 0:
        return 0
    
    completed_projects = projects.filter(status='completed')
    if completed_projects.count() == 0:
        return 0
    
    # Simplified version - assume projects completed on time if they have end_date
    completed_on_time = completed_projects.filter(
        end_date__isnull=False
    ).count()
    
    adherence = (completed_on_time / completed_projects.count() * 100)
    return round(adherence, 1)

def calculate_citizen_engagement_score(projects):
    """Calculate citizen engagement score"""
    if projects.count() == 0:
        return 0
    
    projects_with_reports = projects.filter(citizen_reports__isnull=False).distinct().count()
    engagement = (projects_with_reports / projects.count() * 100)
    return round(engagement, 1)

# Enhanced API endpoints
def project_locations_geojson(request):
    """API endpoint for filtered project locations with enhanced data"""
    try:
        projects = Project.objects.all()
        
        # Apply filters
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
        
        # Build enhanced GeoJSON
        features = []
        current_date = timezone.now().date()
        
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
                health_score = calculate_project_health(project, current_date)
                risk_level = calculate_risk_level(project, current_date)
                
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
                        "health_score": health_score,
                        "risk_level": risk_level,
                        "update_count": project.updates.count(),
                        "report_count": project.citizen_reports.count()
                    }
                })
        
        return JsonResponse({
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "total_projects": len(features),
                "filters_applied": {
                    "year": selected_year,
                    "statuses": selected_statuses,
                    "sectors": selected_sectors,
                    "counties": selected_counties
                }
            }
        })
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def counties_geojson(request):
    """Enhanced counties GeoJSON with comprehensive statistics"""
    try:
        counties = KenyaCounty.objects.all()
        selected_counties = _clean_getlist(request, "county")
        
        if selected_counties:
            counties = counties.filter(county__in=selected_counties)
        
        features = []
        current_date = timezone.now().date()
        
        for county in counties:
            projects_in_county = Project.objects.filter(county__iexact=county.county)
            project_count = projects_in_county.count()
            
            if project_count > 0:
                stats = projects_in_county.aggregate(
                    total_budget=Sum('budget'),
                    completed=Count('id', filter=Q(status='completed')),
                    ongoing=Count('id', filter=Q(status='ongoing')),
                    delayed=Count('id', filter=Q(status='delayed'))
                )
                
                feature = {
                    "type": "Feature",
                    "geometry": json.loads(county.geom.geojson),
                    "properties": {
                        "id": county.id,
                        "county": county.county,
                        "pop_2009": county.pop_2009,
                        "project_count": project_count,
                        "total_budget": stats['total_budget'] or 0,
                        "completed_projects": stats['completed'] or 0,
                        "ongoing_projects": stats['ongoing'] or 0,
                        "delayed_projects": stats['delayed'] or 0,
                        "completion_rate": round((stats['completed'] / project_count * 100), 1) if project_count else 0,
                        "budget_per_capita": round(stats['total_budget'] / (county.pop_2009 or 1), 2),
                        "area_sqkm": round(county.geom.area * 10000, 2),
                        "project_density": round(project_count / (county.geom.area * 10000), 2) if county.geom.area else 0
                    }
                }
                features.append(feature)
        
        return JsonResponse({
            "type": "FeatureCollection",
            "features": features
        })
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

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
            avg_duration=Avg(ExpressionWrapper(F('end_date') - F('start_date'), output_field=DurationField()))
        )
        
        # Risk analysis
        current_date = timezone.now().date()
        risk_analysis = {
            'overdue_projects': projects.filter(status='ongoing', end_date__lt=current_date).count(),
            'high_budget_risk': projects.filter(budget__gt=performance_metrics['avg_budget'] * 2).count(),
            'delayed_projects': projects.filter(status='delayed').count()
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

def subcounties_geojson(request):
    """Enhanced subcounties GeoJSON with comprehensive statistics"""
    try:
        subcounties = KenyaSubCounty.objects.all()
        selected_counties = _clean_getlist(request, "county")
        
        if selected_counties:
            subcounties = subcounties.filter(county__in=selected_counties)
        
        features = []
        
        for subcounty in subcounties:
            projects_in_subcounty = Project.objects.filter(location__within=subcounty.geom)
            project_count = projects_in_subcounty.count()
            
            feature = {
                "type": "Feature",
                "geometry": json.loads(subcounty.geom.geojson),
                "properties": {
                    "id": subcounty.id,
                    "subcounty": subcounty.subcounty,
                    "county": subcounty.county,
                    "project_count": project_count,
                    "area_sqkm": round(subcounty.geom.area * 10000, 2),
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
    """Enhanced wards GeoJSON with comprehensive statistics"""
    try:
        wards = Kenyawards.objects.all()
        selected_counties = _clean_getlist(request, "county")
        
        if selected_counties:
            wards = wards.filter(county__in=selected_counties)
        
        features = []
        
        for ward in wards:
            projects_in_ward = Project.objects.filter(location__within=ward.geom)
            project_count = projects_in_ward.count()
            
            feature = {
                "type": "Feature",
                "geometry": json.loads(ward.geom.geojson),
                "properties": {
                    "id": ward.id,
                    "ward": ward.ward,
                    "subcounty": ward.subcounty,
                    "county": ward.county,
                    "project_count": project_count,
                    "area_sqkm": round(ward.geom.area * 10000, 2),
                }
            }
            features.append(feature)
        
        return JsonResponse({
            "type": "FeatureCollection",
            "features": features
        })
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

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
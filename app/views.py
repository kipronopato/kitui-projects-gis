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
from django.db.models import Q, Count, Sum, Avg, Min, Max, F
from django.db.models.functions import ExtractYear, TruncMonth
from django.db.models import Avg, Sum, Count, Min, Max, StdDev
def home(request):
    # Start with all projects
    projects = Project.objects.all()

    # ---------------- Filters ----------------
    # Year filter
    selected_year = request.GET.get("year")
    if selected_year:
        projects = projects.filter(start_date__year=selected_year)

    # Status filter
    selected_statuses = request.GET.getlist("status")
    if selected_statuses:
        projects = projects.filter(status__in=selected_statuses)

    # Sector filter
    selected_sectors = request.GET.getlist("sector")
    if selected_sectors:
        projects = projects.filter(sector__in=selected_sectors)

    # County filter
    selected_counties = request.GET.getlist("county")
    if selected_counties:
        projects = projects.filter(county__in=selected_counties)

    # Budget range filter
    min_budget = request.GET.get("min_budget")
    max_budget = request.GET.get("max_budget")
    if min_budget:
        try:
            projects = projects.filter(budget__gte=Decimal(min_budget))
        except:
            pass
    if max_budget:
        try:
            projects = projects.filter(budget__lte=Decimal(max_budget))
        except:
            pass

    # Date range filter
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    if start_date:
        projects = projects.filter(start_date__gte=start_date)
    if end_date:
        projects = projects.filter(end_date__lte=end_date)

    # ---------------- Comprehensive Metrics ----------------
    total_projects = projects.count()
    total_budget = projects.aggregate(total=Sum('budget'))['total'] or 0
    county_count = projects.values('county').distinct().count()

    # Budget analysis
    budget_stats = projects.aggregate(
        avg_budget=Avg('budget'),
        min_budget=Min('budget'),
        max_budget=Max('budget'),
        total_budget=Sum('budget')
    )
    
    # Top and bottom budget projects
    highest_budget_projects = projects.order_by('-budget')[:5]
    lowest_budget_projects = projects.order_by('budget')[:5]

    # Status analysis
    status_counts = projects.values('status').annotate(count=Count('id'))
    status_data = {item['status']: item['count'] for item in status_counts}

    total_with_status = sum(status_data.values())
    status_percentages = {
        status: round((count / total_with_status * 100), 1) if total_with_status else 0
        for status, count in status_data.items()
    }

    # Timeline analysis
    current_date = timezone.now().date()
    overdue_projects = projects.filter(
        Q(status='ongoing') & Q(end_date__lt=current_date)
    ).count()
    
    upcoming_deadlines = projects.filter(
        Q(status='ongoing') & 
        Q(end_date__gte=current_date) & 
        Q(end_date__lte=current_date + timedelta(days=30))
    ).count()

    # Completion rate
    completed_projects = projects.filter(status='completed').count()
    completion_rate = round((completed_projects / total_projects * 100), 1) if total_projects else 0

    # Sector analysis
    sector_stats = projects.values('sector').annotate(
        count=Count('id'),
        total_budget=Sum('budget'),
        avg_budget=Avg('budget')
    ).order_by('-total_budget')

    sector_data = []
    for item in sector_stats:
        percentage = (item['count'] / total_projects * 100) if total_projects else 0
        sector_data.append({
            'sector': item['sector'] or 'Not Specified',
            'count': item['count'],
            'total_budget': item['total_budget'] or 0,
            'avg_budget': item['avg_budget'] or 0,
            'percentage': round(percentage, 1)
        })

    # County analysis
    county_stats = projects.values('county').annotate(
        count=Count('id'),
        total_budget=Sum('budget')
    ).order_by('-count')[:10]

    # Monthly timeline
    monthly_timeline = projects.annotate(
        month=TruncMonth('start_date')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')

    # Recent updates
    recent_updates = ProjectUpdate.objects.select_related('project').order_by('-created_at')[:5]

    # Citizen reports analysis
    report_stats = CitizenReport.objects.values('report_type').annotate(
        count=Count('id'),
        approved=Count('id', filter=Q(is_approved=True))
    )

    report_counts = {item['report_type']: item['count'] for item in report_stats}
    approved_reports = sum(item['approved'] for item in report_stats)
    total_reports = sum(item['count'] for item in report_stats)
    approval_rate = round((approved_reports / total_reports * 100), 1) if total_reports else 0

    # Project manager performance
    manager_stats = projects.values('project_manager').annotate(
        count=Count('id'),
        completed=Count('id', filter=Q(status='completed')),
        total_budget=Sum('budget')
    ).exclude(project_manager='').order_by('-count')[:5]

    # Budget utilization by status
    budget_by_status = projects.values('status').annotate(
        total_budget=Sum('budget')
    ).order_by('status')

    # ---------------- Filter Options ----------------
    fiscal_years_qs = Project.objects.dates('start_date', 'year').order_by('-start_date')
    fiscal_years = sorted({year.year for year in fiscal_years_qs}, reverse=True)

    status_choices = [choice[0] for choice in Project.STATUS_CHOICES]
    status_labels = dict(Project.STATUS_CHOICES)

    sectors = Project.objects.exclude(sector__isnull=True).exclude(sector='').values_list('sector', flat=True).distinct().order_by('sector')
    counties = Project.objects.values_list('county', flat=True).distinct().order_by('county')

    # ---------------- GeoJSON for map ----------------
    features = []
    for project in projects.filter(location__isnull=False):
        if project.location:
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
                    "budget": float(project.budget) if project.budget else 0,
                    "start_date": project.start_date.strftime("%Y-%m-%d") if project.start_date else "",
                    "end_date": project.end_date.strftime("%Y-%m-%d") if project.end_date else "",
                    "description": project.description or "",
                    "implementing_agency": project.implementing_agency or "",
                    "contractor": project.contractor or "",
                    "project_manager": project.project_manager or "",
                }
            })

    geojson = {"type": "FeatureCollection", "features": features}

    # ---------------- Context ----------------
    context = {
        # Core metrics
        "total_projects": total_projects,
        "total_budget": total_budget,
        "county_count": county_count,
        "completion_rate": completion_rate,
        "overdue_projects": overdue_projects,
        "upcoming_deadlines": upcoming_deadlines,
        
        # Budget analysis
        "budget_stats": budget_stats,
        "highest_budget_projects": highest_budget_projects,
        "lowest_budget_projects": lowest_budget_projects,
        
        # Status analysis
        "status_counts": status_data,
        "status_percentages": status_percentages,
        "status_labels": status_labels,
        
        # Sector analysis
        "sector_data": sector_data,
        
        # County analysis
        "county_stats": county_stats,
        
        # Timeline
        "monthly_timeline": list(monthly_timeline),
        
        # Recent activity
        "recent_updates": recent_updates,
        
        # Citizen engagement
        "report_counts": report_counts,
        "approval_rate": approval_rate,
        
        # Performance metrics
        "manager_stats": manager_stats,
        "budget_by_status": list(budget_by_status),
        
        # Filter options
        "fiscal_years": fiscal_years,
        "status_choices": status_choices,
        "sectors": sectors,
        "counties": counties,
        
        # GeoJSON
        "geojson": json.dumps(geojson),
        
        # Selected filters
        "selected_year": selected_year,
        "selected_statuses": selected_statuses,
        "selected_sectors": selected_sectors,
        "selected_counties": selected_counties,
        "min_budget": min_budget,
        "max_budget": max_budget,
        "start_date": start_date,
        "end_date": end_date,
    }

    return render(request, "app/home.html", context)



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
    paginate_by = 10


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

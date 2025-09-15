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

from .models import Project, ProjectUpdate, CitizenReport


def home(request):
    # Start with all projects that have location data
    projects = Project.objects.filter(location__isnull=False)

    # ---------------- Filters ----------------
    # Year filter
    selected_year = request.GET.get("year")
    if selected_year:
        projects = projects.filter(start_date__year=selected_year)

    # Phase filter
    selected_phases = request.GET.getlist("phase")
    if selected_phases:
        projects = projects.filter(status__in=[p.lower() for p in selected_phases])

    # Sector filter
    selected_sectors = request.GET.getlist("sector")
    if selected_sectors:
        projects = projects.filter(sector__in=selected_sectors)

    # ---------------- Metrics ----------------
    total_projects = projects.count()
    total_budget = projects.aggregate(total=Sum('budget'))['total'] or 0
    county_count = projects.values('county').distinct().count()

    # Status percentages
    status_counts = projects.values('status').annotate(count=Count('id'))
    status_data = {item['status']: item['count'] for item in status_counts}

    total_with_status = sum(status_data.values())
    status_percentages = {
        status: round((count / total_with_status * 100), 1) if total_with_status else 0
        for status, count in status_data.items()
    }

    # On-budget and on-schedule percentages
    completed_projects = projects.filter(status='completed')
    on_budget_count = completed_projects.count()  # Simplified assumption
    on_schedule_count = projects.filter(
        Q(status='ongoing') & Q(end_date__gte=now())
    ).count()

    percent_on_budget = round((on_budget_count / total_projects * 100), 1) if total_projects else 0
    percent_on_schedule = round((on_schedule_count / total_projects * 100), 1) if total_projects else 0

    # Sector data
    sector_counts = projects.values('sector').annotate(count=Count('id')).order_by('-count')
    sector_data = []
    for item in sector_counts:
        percentage = (item['count'] / total_projects * 100) if total_projects else 0
        sector_data.append({
            'sector': item['sector'] or 'Not Specified',
            'count': item['count'],
            'percentage': round(percentage, 1)
        })

    # Recent updates
    recent_updates = ProjectUpdate.objects.select_related('project').order_by('-created_at')[:3]

    # Budget analysis
    highest_budget_project = projects.order_by('-budget').first()
    average_budget = projects.aggregate(avg=Avg('budget'))['avg'] or 0

    # Citizen reports
    report_counts = CitizenReport.objects.aggregate(
        progress=Count('id', filter=Q(report_type='progress')),
        issue=Count('id', filter=Q(report_type='issue')),
        complaint=Count('id', filter=Q(report_type='complaint'))
    )

    approved_reports = CitizenReport.objects.filter(is_approved=True).count()
    total_reports = CitizenReport.objects.count()
    approval_rate = round((approved_reports / total_reports * 100), 1) if total_reports else 0

    # ---------------- Fiscal Years (Fixed Unique) ----------------
    fiscal_years_qs = Project.objects.dates('start_date', 'year').order_by('-start_date')
    fiscal_years = sorted({year.year for year in fiscal_years_qs}, reverse=True)

    # ---------------- Phases ----------------
    phases = [label for value, label in Project.STATUS_CHOICES]

    # ---------------- GeoJSON for map ----------------
    features = []
    for project in projects:
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
                }
            })

    geojson = {"type": "FeatureCollection", "features": features}

    # ---------------- Context ----------------
    context = {
        "total_projects": total_projects,
        "total_budget": total_budget,
        "percent_on_budget": percent_on_budget,
        "percent_on_schedule": percent_on_schedule,
        "county_count": county_count,
        "status_counts": status_data,
        "status_percentages": status_percentages,
        "sector_data": sector_data,
        "recent_updates": recent_updates,
        "report_counts": report_counts,
        "approval_rate": approval_rate,
        "highest_budget_project": highest_budget_project,
        "average_budget": average_budget,
        "fiscal_years": fiscal_years,
        "phases": phases,
        "geojson": json.dumps(geojson),
        "selected_year": selected_year,
        "selected_phases": selected_phases,
        "selected_sectors": selected_sectors,
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
    projects = Project.objects.all()

    features = []
    for project in projects:
        if project.location:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [project.location.x, project.location.y],
                },
                "properties": {
                    "name": project.name,
                    "status": project.status,
                    "county": project.county,
                    "id": project.id,
                }
            })

    geojson = {"type": "FeatureCollection", "features": features}
    context = {"geojson": geojson, "projects": projects}
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

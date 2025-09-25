from django import template
from django.db.models import QuerySet
register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def get_item(dictionary, key):
    """Return the value from a dict for the given key."""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def get_item(dictionary, key):
    try:
        return dictionary.get(key) if hasattr(dictionary, 'get') else dictionary[key]
    except Exception:
        return ''

@register.filter
def get_item(dictionary, key):
    """Get a dictionary item by key"""
    return dictionary.get(key, "")

@register.filter
def get_item(dictionary, key):
    """Allows dict lookups in templates: {{ mydict|get_item:mykey }}"""
    if dictionary and key in dictionary:
        return dictionary.get(key)
    return None

@register.filter
def get_county_count(county_stats, county_name):
    """
    Given a dict-like object county_stats and county_name,
    return the count for that county or 0 if missing.
    """
    if not county_stats:
        return 0
    return county_stats.get(county_name, 0)

@register.filter
def get_sector_count(sector_data, sector_name):
    """
    Return the count of projects for the given sector.
    sector_data is expected to be a dict like { "Health": {"count": 5, "budget": 20000}, ... }
    """
    if not sector_data:
        return 0
    return sector_data.get(sector_name, {}).get("count", 0)


@register.filter
def get_sector_budget(sector_data, sector_name):
    """
    Return the total budget for the given sector.
    """
    if not sector_data:
        return 0
    return sector_data.get(sector_name, {}).get("budget", 0)


def _safe_get_count_from_item(item, keys):
    for k in keys:
        if k in item and item[k] is not None:
            return item[k]
    return 0

@register.filter
def get_county_count(county_stats, county_name):
    """
    Accepts either:
      - a dict mapping county -> count
      - a list of dicts like [{'county': 'Nakuru', 'count': 5, ...}, ...]
    Returns the count for county_name or 0.
    """
    if not county_stats:
        return 0

    if isinstance(county_stats, dict):
        return county_stats.get(county_name, 0)

    # list-of-dicts fallback
    try:
        for item in county_stats:
            if (item.get("county") == county_name) or (item.get("name") == county_name):
                # common possible keys for count: 'count', 'total', 'projects'
                return _safe_get_count_from_item(item, ("count", "total", "projects"))
    except Exception:
        pass
    return 0


@register.filter
def get_sector_count(sector_data, sector_name):
    """
    Accepts either:
      - a dict mapping sector -> {count:..., budget:...}
      - a list of dicts like [{'sector': 'Health', 'count': 5, ...}, ...]
    Returns the count for sector_name or 0.
    """
    if not sector_data:
        return 0

    if isinstance(sector_data, dict):
        entry = sector_data.get(sector_name)
        if isinstance(entry, dict):
            return entry.get("count", 0)
        return entry or 0

    try:
        for item in sector_data:
            if item.get("sector") == sector_name:
                return item.get("count", 0) or 0
    except Exception:
        pass
    return 0


@register.filter
def get_sector_budget(sector_data, sector_name):
    """
    Return total budget for the sector. Handles dict or list-of-dicts.
    Keys tried (in order): total_budget, budget, total
    """
    if not sector_data:
        return 0

    if isinstance(sector_data, dict):
        entry = sector_data.get(sector_name)
        if isinstance(entry, dict):
            return entry.get("total_budget") or entry.get("budget") or entry.get("total") or 0
        return 0

    try:
        for item in sector_data:
            if item.get("sector") == sector_name:
                return item.get("total_budget") or item.get("budget") or item.get("total") or 0
    except Exception:
        pass
    return 0


@register.filter
def get_projects_count(year_value, projects_qs):
    """
    Usage in template (matches your template): {{ year|get_projects_count:projects }}
    - year_value: year (int or str)
    - projects_qs: QuerySet or iterable of project-like objects with `start_date`
    Returns count of projects that started in that year.
    """
    if not year_value or not projects_qs:
        return 0

    # try QuerySet fast path
    try:
        y = int(year_value)
    except Exception:
        # maybe year_value is "2020-2021" or similar; try to extract first 4 digits
        try:
            import re
            m = re.search(r"\d{4}", str(year_value))
            y = int(m.group(0)) if m else None
        except Exception:
            y = None

    if y is None:
        return 0

    # If it's a QuerySet (has filter)
    try:
        if hasattr(projects_qs, "filter"):
            return projects_qs.filter(start_date__year=y).count()
    except Exception:
        pass

    # Fallback: iterate
    try:
        cnt = 0
        for p in projects_qs:
            sd = getattr(p, "start_date", None)
            if sd and getattr(sd, "year", None) == y:
                cnt += 1
        return cnt
    except Exception:
        return 0

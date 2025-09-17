from django import template

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
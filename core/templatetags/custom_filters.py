from django import template
register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Usage in templates: {{ my_dict|get_item:key }}
    Used in referral_form.html to loop facilities grouped by level.
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, [])
    return []

@register.filter
def split(value, separator=','):
    """Split a string into a list by separator.
    Usage: {{ value|split:',' }}"""
    if value is None:
        return []
    return [item.strip() for item in str(value).split(separator)]

@register.filter
def multiply(value, arg):
    """Multiply a value by arg. Usage: {{ value|multiply:100 }}"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def subtract(value, arg):
    """Subtract arg from value. Usage: {{ value|subtract:arg }}"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def percentage(value, total):
    """Return value as a percentage of total. Usage: {{ value|percentage:total }}"""
    try:
        if float(total) == 0:
            return 0
        return round((float(value) / float(total)) * 100, 1)
    except (ValueError, TypeError):
        return 0


@register.filter
def get_stock(drug_name, facility):
    """
    Look up stock for a drug at a given facility.
    Usage in templates: {{ rx.drug_name|get_stock:request.user.profile.facility }}
    Returns the DrugStock object or None.
    """
    from core.models import DrugStock
    return DrugStock.objects.filter(
        facility=facility,
        drug_name__iexact=drug_name
    ).first()


@register.filter
def severity_colour(severity):
    """Return a CSS badge class based on severity string."""
    mapping = {
        'critical': 'badge-red',
        'severe':   'badge-amber',
        'moderate': 'badge-blue',
        'mild':     'badge-green',
        'high':     'badge-red',
        'medium':   'badge-amber',
        'low':      'badge-green',
    }
    return mapping.get(str(severity).lower(), 'badge-gray')


@register.filter
def priority_border(priority):
    """Return a CSS class for priority-coloured left border on queue items."""
    mapping = {
        'high':   'priority-border-high',
        'medium': 'priority-border-medium',
        'low':    'priority-border-low',
    }
    return mapping.get(str(priority).lower(), 'priority-border-low')


@register.simple_tag
def active_if(request_path, url_name):
    """
    Returns 'active' if the current URL matches the given name.
    Usage: {% active_if request.path 'patient:dashboard' %}
    """
    from django.urls import reverse, NoReverseMatch
    try:
        return 'active' if request_path == reverse(url_name) else ''
    except NoReverseMatch:
        return ''
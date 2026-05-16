from django import template

from labeling.cv_setup_templates import template_bootstrap_icon

register = template.Library()


@register.filter
def cv_template_icon(cv_tpl):
    """Bootstrap Icons suffix for a ``CVSetupTemplate`` (no ``bi-`` prefix)."""
    return template_bootstrap_icon(cv_tpl)

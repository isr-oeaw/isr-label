from django import template

register = template.Library()


@register.filter
def is_project_member(project, user):
    if not user or not user.is_authenticated or not project:
        return False
    return project.is_member(user)

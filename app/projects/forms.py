from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from .models import Project, ProjectMembership

User = get_user_model()


class ProjectForm(forms.ModelForm):
    """Form for creating and editing projects (no M2M collaborators — use team page)."""

    class Meta:
        model = Project
        fields = [
            'title', 'description', 'abstract', 'start_date', 'end_date',
            'status', 'access_level', 'keywords', 'tags', 'project_url',
            'funding_source', 'grant_number',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter project title')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Describe the project objectives and scope...')
            }),
            'abstract': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Brief summary of the project...')
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'access_level': forms.Select(attrs={'class': 'form-select'}),
            'keywords': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter keywords separated by commas')
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter tags separated by commas')
            }),
            'project_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': _('https://example.com/project')
            }),
            'funding_source': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Funding organization name')
            }),
            'grant_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Grant or contract number')
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            pass

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError(_('End date must be after start date.'))
        return cleaned_data

    def clean_keywords(self):
        keywords = self.cleaned_data.get('keywords', '')
        if keywords:
            keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
            if len(keyword_list) > 20:
                raise forms.ValidationError(_('Maximum 20 keywords allowed.'))
        return keywords

    def clean_tags(self):
        tags = self.cleaned_data.get('tags', '')
        if tags:
            tag_list = [t.strip() for t in tags.split(',') if t.strip()]
            if len(tag_list) > 15:
                raise forms.ValidationError(_('Maximum 15 tags allowed.'))
        return tags


class ProjectTransferOwnershipForm(forms.Form):
    new_owner = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_('New Owner'),
        help_text=_('Select the user who will become the new owner of this project')
    )
    confirm_transfer = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_('I confirm that I want to transfer ownership'),
        help_text=_('You will remain a project member (annotator) unless your role is changed.'),
    )

    def __init__(self, *args, **kwargs):
        current_user = kwargs.pop('current_user', None)
        project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)
        if current_user and project:
            excluded = [current_user.pk]
            if project.owner:
                excluded.append(project.owner.pk)
            self.fields['new_owner'].queryset = (
                User.objects.exclude(pk__in=excluded).order_by('username')
            )

    def clean_new_owner(self):
        new_owner = self.cleaned_data.get('new_owner')
        if not new_owner:
            raise forms.ValidationError(_('Please select a new owner for the project.'))
        return new_owner


class ProjectFilterForm(forms.Form):
    STATUS_CHOICES = [('', _('All Statuses'))] + Project.STATUS_CHOICES
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search projects...')
        }),
        label=_('Search')
    )
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_('Status')
    )


class ProjectMemberInviteForm(forms.Form):
    email = forms.EmailField(
        required=True,
        label=_('Email'),
        help_text=_('User must already have an account'),
        widget=forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}),
    )
    role = forms.ChoiceField(
        choices=ProjectMembership.Role.choices,
        initial=ProjectMembership.Role.ANNOTATOR,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_('Role'),
    )


class ProjectMemberRoleForm(forms.ModelForm):
    class Meta:
        model = ProjectMembership
        fields = ['role']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
        }

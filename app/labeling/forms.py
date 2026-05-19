from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.forms import formset_factory
from django.utils.translation import gettext_lazy as _

from labeling.cv_setup_templates import TOOL_CHOICES

from .models import LabelDataset

User = get_user_model()


class LabelDatasetForm(forms.ModelForm):
    class Meta:
        model = LabelDataset
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class DatasetAssigneesForm(forms.Form):
    assigned_users = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': 10}),
        label=_('Assigned users'),
        help_text=_(
            'Project members who may label this dataset when restrictions apply. '
            'Leave empty with no groups so any project labeler may work on this dataset.'
        ),
    )
    assigned_groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.order_by('name'),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': 8}),
        label=_('Assigned groups'),
        help_text=_('Django groups (site-wide). Members may label this dataset when restrictions apply.'),
    )

    def __init__(self, *args, project=None, dataset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project:
            self.fields['assigned_users'].queryset = User.objects.filter(
                project_memberships__project=project
            ).distinct().order_by('username')
        if dataset:
            self.fields['assigned_users'].initial = list(
                dataset.assigned_users.values_list('pk', flat=True)
            )
            self.fields['assigned_groups'].initial = list(
                dataset.assigned_groups.values_list('pk', flat=True)
            )


class MultiImageForm(forms.Form):
    anything = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean(self):
        return self.cleaned_data


class LabelEntryForm(forms.Form):
    label_id = forms.CharField(
        max_length=64,
        label=_('Label id'),
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
    )
    name = forms.CharField(
        max_length=200,
        label=_('Name'),
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
    )
    color = forms.CharField(
        max_length=20,
        required=False,
        initial='#e74c3c',
        label=_('Color'),
        widget=forms.TextInput(
            attrs={'class': 'form-control form-control-sm', 'type': 'color'}
        ),
    )
    hotkey = forms.CharField(
        max_length=8,
        required=False,
        label=_('Hotkey'),
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
    )


LabelEntryFormSet = formset_factory(
    LabelEntryForm,
    extra=1,
    can_delete=True,
    min_num=0,
)


class LabelSchemaEditForm(forms.Form):
    tools = forms.MultipleChoiceField(
        label=_('Tools'),
        choices=TOOL_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    allow_empty = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Allow empty submission'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    multi_label = forms.BooleanField(
        required=False,
        initial=False,
        label=_('Multi-label (classification)'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    mask_import_enabled = forms.BooleanField(
        required=False,
        initial=False,
        label=_('Allow segmentation mask import'),
        help_text=_(
            'When enabled, admins can import PNG/TIF label masks (pixel class → label id) '
            'as polygon pre-labels for this project. The polygon tool should be on; see documentation.'
        ),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    instructions = forms.CharField(
        required=False,
        label=_('Labeling instructions for annotators'),
        help_text=_(
            'Optional. Shown on the labeling task page. Safe HTML is allowed: links, lists, headings, emphasis.'
        ),
        widget=forms.Textarea(
            attrs={'class': 'form-control', 'rows': 5, 'spellcheck': 'true'}
        ),
    )
    use_advanced_json = forms.BooleanField(
        required=False,
        initial=False,
        label=_('Edit raw JSON only'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    config_text = forms.CharField(
        required=False,
        label=_('Configuration (JSON)'),
        widget=forms.Textarea(
            attrs={
                'class': 'form-control font-monospace small',
                'rows': 18,
                'id': 'id_config_text',
                'spellcheck': 'false',
                'data-codemirror-target': '1',
            }
        ),
    )
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Active'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )


class LabelSchemaApplyTemplateForm(forms.Form):
    slug = forms.CharField(max_length=64, widget=forms.HiddenInput())

    def clean_slug(self):
        from labeling.cv_setup_templates import get_cv_template

        slug = self.cleaned_data['slug']
        if not get_cv_template(slug):
            raise forms.ValidationError(_('Unknown template.'))
        return slug

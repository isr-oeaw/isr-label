from django import forms
from django.utils.translation import gettext_lazy as _

from .models import LabelDataset, LabelSchema


class LabelDatasetForm(forms.ModelForm):
    class Meta:
        model = LabelDataset
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class MultiImageForm(forms.Form):
    anything = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean(self):
        return self.cleaned_data


class LabelSchemaEditForm(forms.Form):
    config_text = forms.CharField(
        required=True,
        label=_('Configuration (JSON)'),
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 20}),
    )
    is_active = forms.BooleanField(required=False, initial=True, label=_('Active'))

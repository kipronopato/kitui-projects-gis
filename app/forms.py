from django import forms
from .models import CitizenReport

class CitizenReportForm(forms.ModelForm):
    class Meta:
        model = CitizenReport
        fields = ['report_type', 'description', 'photo']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'report_type': forms.Select(attrs={'class': 'form-control'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
        }
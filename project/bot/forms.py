from django import forms
from .models import Profile


class ProfileForm(forms.ModelForm):

    class Meta:
        model = Profile
        fields = (
            'external_id',
            'name',
            'status',
            'question',
            'points',
        )
        widgets = {
            'name': forms.TextInput,
        }

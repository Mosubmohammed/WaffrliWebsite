# forms.py
from django import forms
from django.contrib.auth.models import User
from .models import Customer, ReportedDeal

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'phone', 'gender', 'formatted_address', 'image']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'formatted_address': forms.TextInput(attrs={'class': 'form-control'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }
        labels = {
            'formatted_address': 'Address',  # This will make the field still display as "Address" in the form
        }

class ReportDealForm(forms.ModelForm):
    class Meta:
        model = ReportedDeal
        fields = ['reason', 'details']
        widgets = {
            'reason': forms.RadioSelect(),
            'details': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Please provide any additional details about this report'})
        }
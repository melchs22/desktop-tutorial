from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Client

class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )

class SimpleClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'passport_number', 'nin', 'district']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'passport_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Passport Number'}),
            'nin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'NIN (Optional)'}),
            'district': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'District (Optional)'}),
        }

class DocumentUploadForm(forms.Form):
    # Option 1: Upload individual documents
    passport_photos = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'multiple': True,
            'accept': 'image/*'
        }),
        required=False,
        help_text="Upload passport photos (images will be converted to PDF)"
    )
    
    passport_book = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'multiple': True,
            'accept': 'image/*'
        }),
        required=False,
        help_text="Upload passport book pages"
    )
    
    yellow_fever = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'multiple': True,
            'accept': 'image/*,.pdf'
        }),
        required=False,
        help_text="Upload yellow fever certificates"
    )
    
    # Option 2: Upload complete PDF package (NEW)
    complete_pdf = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf'
        }),
        required=False,
        help_text="Upload complete PDF package (if client already has compiled PDF)"
    )
    
    # Option 3: Upload other PDF files (NEW)
    other_documents = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'multiple': True,
            'accept': '.pdf'
        }),
        required=False,
        help_text="Upload other PDF documents"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        complete_pdf = cleaned_data.get('complete_pdf')
        has_individual_docs = any([
            cleaned_data.get('passport_photos'),
            cleaned_data.get('passport_book'),
            cleaned_data.get('yellow_fever'),
            cleaned_data.get('other_documents')
        ])
        
        if complete_pdf and has_individual_docs:
            raise forms.ValidationError(
                "Please choose either uploading a complete PDF OR individual documents, not both."
            )
        
        if not complete_pdf and not has_individual_docs:
            raise forms.ValidationError(
                "Please upload at least one document or a complete PDF."
            )
        
        return cleaned_data

class QuickClientForm(forms.Form):
    """Form for quick client addition with complete PDF"""
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'})
    )
    passport_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Passport Number'})
    )
    nin = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'NIN (Optional)'})
    )
    district = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'District (Optional)'})
    )
    complete_pdf = forms.FileField(
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf'
        }),
        help_text="Upload the complete PDF document for this client"
    )
    additional_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Any additional notes about this client...'
        })
    )
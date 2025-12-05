from django.db import models
from django.contrib.auth.models import User
import os

def client_folder_path(instance, filename):
    """Generate file path for client documents - only PDFs will be stored"""
    safe_name = f"{instance.client.name.replace(' ', '_')}_{instance.client.passport_number}"
    return os.path.join('Dubai Details', safe_name, filename)

class Client(models.Model):
    name = models.CharField(max_length=200)
    passport_number = models.CharField(max_length=50)
    nin = models.CharField(max_length=50, verbose_name="NIN", blank=True)
    district = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.passport_number}"
    
    def get_folder_path(self):
        """Get the absolute folder path for this client"""
        from django.conf import settings
        folder_name = f"{self.name.replace(' ', '_')}_{self.passport_number}"
        return os.path.join(settings.MEDIA_ROOT, folder_name)

class ClientDocument(models.Model):
    DOCUMENT_TYPES = [
        ('passport_photos', 'Passport Photos'),
        ('passport_book', 'Passport Book Photos'),
        ('yellow_fever', 'Yellow Fever Certificate'),
        ('complete_pdf', 'Complete PDF Package'),  # NEW: For pre-existing complete PDFs
        ('other', 'Other Documents'),  # NEW: For additional files
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to=client_folder_path)
    description = models.CharField(max_length=255, blank=True)  # Added description field
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.client.name} - {self.get_document_type_display()}"
    
    def get_preview_url(self):
        """Get URL for PDF preview"""
        from django.conf import settings
        return f"{settings.MEDIA_URL}{self.file.name}"
    
    def get_icon_class(self):
        """Get appropriate icon class based on document type"""
        icon_map = {
            'passport_photos': 'bi-camera text-primary',
            'passport_book': 'bi-passport text-warning',
            'yellow_fever': 'bi-file-medical text-danger',
            'complete_pdf': 'bi-file-pdf text-success',  # NEW
            'other': 'bi-file-earmark text-secondary',
        }
        return icon_map.get(self.document_type, 'bi-file-earmark text-secondary')
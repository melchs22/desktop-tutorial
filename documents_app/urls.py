from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Client Management
    path('add-client/', views.add_client, name='add_client'),
    path('client/<int:client_id>/', views.client_detail, name='client_detail'),
    path('client/<int:client_id>/upload/', views.upload_documents, name='upload_documents'),
    path('client/<int:client_id>/download-all/', views.download_all, name='download_all'),
    path('client/<int:client_id>/delete/', views.delete_client, name='delete_client'),
    
    # Document Downloads
    path('document/<int:document_id>/download/', views.download_file, name='download_file'),
    path('viewer/document/<int:document_id>/download/', views.download_file_viewer, name='download_file_viewer'),
    
    # Public Viewer
    path('viewer/', views.document_viewer, name='document_viewer'),  # Search page
    path('viewer/client/<int:client_id>/', views.client_detail_viewer, name='client_detail_viewer'),
    path('viewer/passport/<str:passport_number>/', views.document_viewer_by_passport, name='document_viewer_by_passport'),
    path('client/<int:client_id>/complete-pdf/', views.download_comprehensive_pdf, name='download_comprehensive_pdf'),
    path('add-quick-client/', views.add_quick_client, name='add_quick_client'),
    # Home redirects
    path('', views.document_viewer, name='home'),
]
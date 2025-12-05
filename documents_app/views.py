from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, HttpResponse
from django.conf import settings
from django.utils import timezone
import os
import zipfile
from io import BytesIO
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .models import Client, ClientDocument
from .forms import LoginForm, SimpleClientForm, DocumentUploadForm, QuickClientForm

# ========== AUTHENTICATION ==========
def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = LoginForm()
    
    return render(request, 'documents_app/login.html', {'form': form})

def user_logout(request):
    logout(request)
    return redirect('login')

# ========== PUBLIC VIEWER (No login required) ==========
def document_viewer(request):
    """Public search page for viewing client documents"""
    if request.method == 'POST':
        search_query = request.POST.get('search', '').strip()
        if search_query:
            # Try to find exact match by passport number first
            exact_client = Client.objects.filter(passport_number__iexact=search_query).first()
            if exact_client:
                # Redirect to client detail view
                return redirect('client_detail_viewer', client_id=exact_client.id)
            
            # If no exact match, show search results
            clients = Client.objects.filter(
                passport_number__icontains=search_query
            ) | Client.objects.filter(
                name__icontains=search_query
            )
            
            if clients.count() == 1:
                # If only one result, redirect to that client
                return redirect('client_detail_viewer', client_id=clients.first().id)
            
            # Show multiple results
            return render(request, 'documents_app/viewer.html', {
                'clients': clients,
                'search_query': search_query
            })
    
    # Show empty search form
    return render(request, 'documents_app/viewer.html')

def client_detail_viewer(request, client_id):
    """Public view of client details (no login required)"""
    client = get_object_or_404(Client, id=client_id)
    return get_client_detail_data(request, client, is_viewer=True)

def document_viewer_by_passport(request, passport_number):
    """Direct access by passport number"""
    client = get_object_or_404(Client, passport_number=passport_number)
    return redirect('client_detail_viewer', client_id=client.id)

# ========== STAFF DASHBOARD (Login required) ==========
@login_required
def dashboard(request):
    clients = Client.objects.all().order_by('-created_at')
    total_clients = clients.count()
    
    # Get all client data with images
    clients_data = []
    for client in clients:
        # Get all passport photos
        passport_photos = client.documents.filter(document_type='passport_photos')
        first_photo = passport_photos.first()
        
        # Get document counts
        passport_photos_count = passport_photos.count()
        passport_book_count = client.documents.filter(document_type='passport_book').count()
        yellow_fever_count = client.documents.filter(document_type='yellow_fever').count()
        
        clients_data.append({
            'client': client,
            'first_photo': first_photo,
            'passport_photos_count': passport_photos_count,
            'passport_book_count': passport_book_count,
            'yellow_fever_count': yellow_fever_count,
            'total_docs': passport_photos_count + passport_book_count + yellow_fever_count
        })
    
    return render(request, 'documents_app/dashboard.html', {
        'clients_data': clients_data,
        'total_clients': total_clients
    })

# ========== ADD CLIENT ==========
@login_required
def add_client(request):
    if request.method == 'POST':
        form = SimpleClientForm(request.POST)
        if form.is_valid():
            client = form.save(commit=False)
            client.created_by = request.user
            client.save()
            
            # Create folder for this client
            client_folder = client.get_folder_path()
            os.makedirs(client_folder, exist_ok=True)
            
            messages.success(request, f'Client {client.name} added successfully!')
            return redirect('upload_documents', client_id=client.id)
    else:
        form = SimpleClientForm()
    
    return render(request, 'documents_app/add_client.html', {'form': form})

# ========== UPLOAD DOCUMENTS ==========
@login_required
def upload_documents(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        form = SimpleClientForm(request.POST, request.FILES)
        
        # Get client folder
        client_folder = client.get_folder_path()
        os.makedirs(client_folder, exist_ok=True)
        
        uploaded_files = []
        
        # 1. PROCESS PASSPORT PHOTOS
        passport_photos = request.FILES.getlist('passport_photos')
        for i, photo in enumerate(passport_photos, 1):
            if photo:
                # Save file directly as PDF
                filename = f"passport_photo_{i}.pdf"
                file_path = os.path.join(client_folder, filename)
                
                # Convert image to PDF immediately
                title = f"Passport Photo {i}"
                generate_pdf_from_image(photo, file_path, title)
                
                # Create document record
                ClientDocument.objects.create(
                    client=client,
                    document_type='passport_photos',
                    file=os.path.join(os.path.basename(client_folder), filename)
                )
                uploaded_files.append(file_path)
        
        # 2. PROCESS PASSPORT BOOK PHOTOS
        passport_book_files = request.FILES.getlist('passport_book')
        for i, book_file in enumerate(passport_book_files, 1):
            if book_file:
                ext = book_file.name.split('.')[-1].lower()
                filename = f"passport_book_{i}.pdf"
                file_path = os.path.join(client_folder, filename)
                
                if ext == 'pdf':
                    # Save PDF directly
                    with open(file_path, 'wb+') as f:
                        for chunk in book_file.chunks():
                            f.write(chunk)
                else:
                    # Convert image to PDF
                    title = f"Passport Book Page {i}"
                    generate_pdf_from_image(book_file, file_path, title)
                
                # Create document record
                ClientDocument.objects.create(
                    client=client,
                    document_type='passport_book',
                    file=os.path.join(os.path.basename(client_folder), filename)
                )
                uploaded_files.append(file_path)
        
        # 3. PROCESS YELLOW FEVER CERTIFICATES
        yellow_fever_files = request.FILES.getlist('yellow_fever')
        for i, yf_file in enumerate(yellow_fever_files, 1):
            if yf_file:
                ext = yf_file.name.split('.')[-1].lower()
                filename = f"yellow_fever_{i}.pdf"
                file_path = os.path.join(client_folder, filename)
                
                if ext == 'pdf':
                    # Save PDF directly
                    with open(file_path, 'wb+') as f:
                        for chunk in yf_file.chunks():
                            f.write(chunk)
                else:
                    # Convert image to PDF
                    title = f"Yellow Fever Certificate {i}"
                    generate_pdf_from_image(yf_file, file_path, title)
                
                ClientDocument.objects.create(
                    client=client,
                    document_type='yellow_fever',
                    file=os.path.join(os.path.basename(client_folder), filename)
                )
                uploaded_files.append(file_path)
        
        # 4. GENERATE COMPREHENSIVE PDF WITH ALL DOCUMENTS
        generate_comprehensive_client_pdf(client)
        
        messages.success(request, f'{len(uploaded_files)} documents uploaded successfully! PDFs generated.')
        return redirect('client_detail', client_id=client.id)
    else:
        form = SimpleClientForm()
    
    return render(request, 'documents_app/upload_documents.html', {
        'form': form,
        'client': client
    })

# ========== HELPER FUNCTION FOR CLIENT DETAIL ==========
def get_client_detail_data(request, client, is_viewer=False):
    """Helper function to get client detail data"""
    documents = client.documents.all()
    
    # Get all passport photos
    passport_photos = documents.filter(document_type='passport_photos')
    
    # Get first passport photo for the main display
    first_passport_photo = passport_photos.first()
    
    # Get other document types
    passport_book = documents.filter(document_type='passport_book')
    yellow_fever = documents.filter(document_type='yellow_fever')
    
    # Get all PDF files in client folder
    client_folder = client.get_folder_path()
    pdf_files = []
    if os.path.exists(client_folder):
        all_files = sorted(os.listdir(client_folder))
        # Filter only PDF files
        pdf_files = [f for f in all_files if f.lower().endswith('.pdf')]
    
    # Check if comprehensive PDF exists
    comprehensive_pdf = os.path.join(client_folder, f"{client.name.replace(' ', '_')}_Complete_Documents.pdf")
    has_comprehensive_pdf = os.path.exists(comprehensive_pdf)
    
    return render(request, 'documents_app/client_detail.html', {
        'client': client,
        'first_passport_photo': first_passport_photo,
        'passport_photos': passport_photos,
        'passport_book': passport_book,
        'yellow_fever': yellow_fever,
        'pdf_files': pdf_files,
        'client_folder': client_folder,
        'has_comprehensive_pdf': has_comprehensive_pdf,
        'comprehensive_pdf_path': comprehensive_pdf,
        'is_viewer': is_viewer
    })

# ========== CLIENT DETAIL ==========
@login_required
def client_detail(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    return get_client_detail_data(request, client, is_viewer=False)

# ========== FILE DOWNLOADS ==========
@login_required
def download_file(request, document_id):
    document = get_object_or_404(ClientDocument, id=document_id)
    file_path = os.path.join(settings.MEDIA_ROOT, document.file.name)
    
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), 
                          as_attachment=True,
                          filename=os.path.basename(file_path))
    
    messages.error(request, 'File not found!')
    return redirect('client_detail', client_id=document.client.id)

def download_file_viewer(request, document_id):
    """Public download (no login required)"""
    document = get_object_or_404(ClientDocument, id=document_id)
    file_path = os.path.join(settings.MEDIA_ROOT, document.file.name)
    
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), 
                          as_attachment=True,
                          filename=os.path.basename(file_path))
    
    return HttpResponse("File not found", status=404)

@login_required
def download_all(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    client_folder = client.get_folder_path()
    
    # Create zip file
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        if os.path.exists(client_folder):
            for file in os.listdir(client_folder):
                if file.lower().endswith('.pdf'):  # Only include PDFs
                    file_path = os.path.join(client_folder, file)
                    if os.path.isfile(file_path):
                        zf.write(file_path, file)
    
    memory_file.seek(0)
    
    response = HttpResponse(memory_file.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{client.name}_documents.zip"'
    return response

def download_comprehensive_pdf(request, client_id):
    """Download the comprehensive PDF"""
    client = get_object_or_404(Client, id=client_id)
    comprehensive_pdf = os.path.join(client.get_folder_path(), f"{client.name.replace(' ', '_')}_Complete_Documents.pdf")
    
    if os.path.exists(comprehensive_pdf):
        return FileResponse(open(comprehensive_pdf, 'rb'),
                          as_attachment=True,
                          filename=f"{client.name}_Complete_Documents.pdf")
    
    # If comprehensive PDF doesn't exist, generate it
    generate_comprehensive_client_pdf(client)
    
    if os.path.exists(comprehensive_pdf):
        return FileResponse(open(comprehensive_pdf, 'rb'),
                          as_attachment=True,
                          filename=f"{client.name}_Complete_Documents.pdf")
    
    messages.error(request, 'Could not generate comprehensive PDF!')
    return redirect('client_detail', client_id=client_id)

# ========== DELETE CLIENT ==========
@login_required
def delete_client(request, client_id):
    """Delete client and all associated files"""
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        # Delete client folder
        client_folder = client.get_folder_path()
        if os.path.exists(client_folder):
            import shutil
            shutil.rmtree(client_folder)
        
        # Delete client from database
        client_name = client.name
        client.delete()
        
        messages.success(request, f'Client {client_name} deleted successfully!')
        return redirect('dashboard')
    
    return render(request, 'documents_app/confirm_delete.html', {'client': client})

# ========== PDF GENERATION FUNCTIONS ==========
def generate_pdf_from_image(file_obj, output_pdf_path, title="Document"):
    """Convert uploaded image file to PDF immediately"""
    try:
        # Create a temporary file
        temp_path = output_pdf_path + '.temp'
        with open(temp_path, 'wb+') as f:
            for chunk in file_obj.chunks():
                f.write(chunk)
        
        # Create PDF
        c = canvas.Canvas(output_pdf_path, pagesize=letter)
        width, height = letter
        
        # Add title
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width/2, height - 50, title)
        
        # Add image
        try:
            img = Image.open(temp_path)
            img_width, img_height = img.size
            
            # Scale to fit page
            max_width = width - 100
            max_height = height - 100
            
            if img_width > max_width or img_height > max_height:
                ratio = min(max_width/img_width, max_height/img_height)
                img_width = int(img_width * ratio)
                img_height = int(img_height * ratio)
            
            # Center on page
            x = (width - img_width) / 2
            y = (height - img_height) / 2
            
            # Save image to temporary file in proper format
            img_temp = temp_path + '.jpg'
            img.save(img_temp, 'JPEG', quality=90)
            
            c.drawImage(img_temp, x, y, width=img_width, height=img_height)
            
            # Clean up temp files
            if os.path.exists(img_temp):
                os.remove(img_temp)
        except Exception as e:
            c.setFont("Helvetica", 12)
            c.drawString(50, height - 100, f"Error: Could not process image")
        
        # Add footer
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(50, 30, f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M')}")
        c.drawString(width - 150, 30, "Dubai Documents")
        
        c.save()
        
        # Remove temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return output_pdf_path
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return None

def generate_comprehensive_client_pdf(client):
    """Generate ONE comprehensive PDF with all client documents"""
    client_folder = client.get_folder_path()
    os.makedirs(client_folder, exist_ok=True)
    
    pdf_path = os.path.join(client_folder, f"{client.name.replace(' ', '_')}_Complete_Documents.pdf")
    
    # Get all documents
    passport_photos = client.documents.filter(document_type='passport_photos')
    passport_book = client.documents.filter(document_type='passport_book')
    yellow_fever = client.documents.filter(document_type='yellow_fever')
    
    # Create PDF
    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter
    
    # COVER PAGE
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width/2, height - 100, "DUBAI DOCUMENTS")
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width/2, height - 150, "CLIENT DOCUMENT PORTFOLIO")
    c.setFont("Helvetica", 16)
    c.drawCentredString(width/2, height - 200, client.name)
    c.setFont("Helvetica", 14)
    c.drawCentredString(width/2, height - 230, f"Passport Number: {client.passport_number}")
    
    # Client info box
    y_pos = height - 300
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, y_pos, "Client Information:")
    y_pos -= 30
    
    c.setFont("Helvetica", 12)
    info = [
        f"Name: {client.name}",
        f"Passport: {client.passport_number}",
        f"NIN: {client.nin if client.nin else 'N/A'}",
        f"District: {client.district if client.district else 'N/A'}",
        f"Date: {client.created_at.strftime('%Y-%m-%d %H:%M')}",
    ]
    
    for line in info:
        c.drawString(120, y_pos, line)
        y_pos -= 25
    
    # Document summary
    y_pos -= 20
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, y_pos, "Document Summary:")
    y_pos -= 30
    
    c.setFont("Helvetica", 12)
    summary = [
        f"✓ Passport Photos: {passport_photos.count()}",
        f"✓ Passport Book Pages: {passport_book.count()}",
        f"✓ Yellow Fever Certificates: {yellow_fever.count()}",
        f"✓ Total Pages: {passport_photos.count() + passport_book.count() + yellow_fever.count() + 1}",
    ]
    
    for line in summary:
        c.drawString(120, y_pos, line)
        y_pos -= 25
    
    # Footer
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width/2, 50, f"Generated on: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    c.showPage()
    
    # PASSPORT PHOTOS SECTION
    if passport_photos.exists():
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(width/2, height - 50, "SECTION 1: PASSPORT PHOTOS")
        c.showPage()
        
        for i, doc in enumerate(passport_photos, 1):
            doc_path = os.path.join(settings.MEDIA_ROOT, doc.file.name)
            if os.path.exists(doc_path):
                try:
                    # Try to extract image from PDF for display
                    # For now, just add a placeholder with document info
                    c.setFont("Helvetica-Bold", 16)
                    c.drawCentredString(width/2, height - 100, f"Passport Photo {i}")
                    c.setFont("Helvetica", 14)
                    c.drawCentredString(width/2, height - 130, f"File: {os.path.basename(doc_path)}")
                    c.drawCentredString(width/2, height - 160, f"Uploaded: {doc.uploaded_at.strftime('%Y-%m-%d %H:%M')}")
                    
                    # Add PDF icon
                    c.setFont("Helvetica", 72)
                    c.drawCentredString(width/2, height/2, "📄")
                    
                    c.setFont("Helvetica", 12)
                    c.drawCentredString(width/2, height/2 - 50, "PDF Document Included")
                    c.drawCentredString(width/2, height/2 - 70, "See attached PDF file for actual image")
                except:
                    pass
            
            if i < passport_photos.count():
                c.showPage()
    
    # PASSPORT BOOK PAGES SECTION
    if passport_book.exists():
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(width/2, height - 50, "SECTION 2: PASSPORT BOOK PAGES")
        c.showPage()
        
        for i, doc in enumerate(passport_book, 1):
            doc_path = os.path.join(settings.MEDIA_ROOT, doc.file.name)
            if os.path.exists(doc_path):
                try:
                    c.setFont("Helvetica-Bold", 16)
                    c.drawCentredString(width/2, height - 100, f"Passport Book Page {i}")
                    c.setFont("Helvetica", 14)
                    c.drawCentredString(width/2, height - 130, f"File: {os.path.basename(doc_path)}")
                    c.drawCentredString(width/2, height - 160, f"Uploaded: {doc.uploaded_at.strftime('%Y-%m-%d %H:%M')}")
                    
                    # Add PDF icon
                    c.setFont("Helvetica", 72)
                    c.drawCentredString(width/2, height/2, "📄")
                    
                    c.setFont("Helvetica", 12)
                    c.drawCentredString(width/2, height/2 - 50, "PDF Document Included")
                except:
                    pass
            
            if i < passport_book.count():
                c.showPage()
    
    # YELLOW FEVER CERTIFICATES SECTION
    if yellow_fever.exists():
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(width/2, height - 50, "SECTION 3: YELLOW FEVER CERTIFICATES")
        c.showPage()
        
        for i, doc in enumerate(yellow_fever, 1):
            doc_path = os.path.join(settings.MEDIA_ROOT, doc.file.name)
            if os.path.exists(doc_path):
                try:
                    c.setFont("Helvetica-Bold", 16)
                    c.drawCentredString(width/2, height - 100, f"Yellow Fever Certificate {i}")
                    c.setFont("Helvetica", 14)
                    c.drawCentredString(width/2, height - 130, f"File: {os.path.basename(doc_path)}")
                    c.drawCentredString(width/2, height - 160, f"Uploaded: {doc.uploaded_at.strftime('%Y-%m-%d %H:%M')}")
                    
                    # Add PDF icon
                    c.setFont("Helvetica", 72)
                    c.drawCentredString(width/2, height/2, "📄")
                    
                    c.setFont("Helvetica", 12)
                    c.drawCentredString(width/2, height/2 - 50, "PDF Document Included")
                except:
                    pass
            
            if i < yellow_fever.count():
                c.showPage()
    
    c.save()
    return pdf_path
@login_required
def add_quick_client(request):
    """Add client with complete PDF in one step"""
    if request.method == 'POST':
        form = QuickClientForm(request.POST, request.FILES)
        if form.is_valid():
            # Create client
            client = Client.objects.create(
                name=form.cleaned_data['name'],
                passport_number=form.cleaned_data['passport_number'],
                nin=form.cleaned_data['nin'],
                district=form.cleaned_data['district'],
                created_by=request.user
            )
            
            # Create folder for this client
            client_folder = client.get_folder_path()
            os.makedirs(client_folder, exist_ok=True)
            
            # Save complete PDF directly (no conversion needed)
            complete_pdf = form.cleaned_data['complete_pdf']
            
            # Generate a clean filename
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            pdf_filename = f"{client.name.replace(' ', '_')}_{client.passport_number}_complete_{unique_id}.pdf"
            pdf_path = os.path.join(client_folder, pdf_filename)
            
            # Save the PDF file directly
            with open(pdf_path, 'wb+') as f:
                for chunk in complete_pdf.chunks():
                    f.write(chunk)
            
            # Create document record for complete PDF
            ClientDocument.objects.create(
                client=client,
                document_type='complete_pdf',
                file=os.path.join(os.path.basename(client_folder), pdf_filename),
                description=form.cleaned_data['additional_notes'] or f"Complete PDF document for {client.name}"
            )
            
            # Generate a simple summary PDF (optional)
            generate_client_summary_pdf(client)
            
            messages.success(request, f'Client {client.name} added successfully with complete PDF!')
            return redirect('client_detail', client_id=client.id)
    else:
        form = QuickClientForm()
    
    return render(request, 'documents_app/add_quick_client.html', {'form': form})
def generate_client_summary_pdf(client):
    """Generate a simple summary PDF for the client"""
    try:
        client_folder = client.get_folder_path()
        os.makedirs(client_folder, exist_ok=True)
        
        pdf_path = os.path.join(client_folder, f"{client.name.replace(' ', '_')}_Summary.pdf")
        
        c = canvas.Canvas(pdf_path, pagesize=letter)
        width, height = letter
        
        # Title
        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(width/2, height - 50, "CLIENT SUMMARY")
        
        # Client Information
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, height - 100, "Client Information:")
        
        c.setFont("Helvetica", 12)
        y_position = height - 130
        
        info_lines = [
            f"Name: {client.name}",
            f"Passport Number: {client.passport_number}",
            f"NIN: {client.nin if client.nin else 'Not provided'}",
            f"District: {client.district if client.district else 'Not provided'}",
            f"Date Created: {client.created_at.strftime('%Y-%m-%d %H:%M')}",
            f"Created By: {client.created_by.username if client.created_by else 'System'}",
        ]
        
        for line in info_lines:
            c.drawString(70, y_position, line)
            y_position -= 25
        
        # Document Information
        y_position -= 20
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y_position, "Document Information:")
        
        c.setFont("Helvetica", 12)
        y_position -= 30
        
        # Get document counts
        documents = client.documents.all()
        passport_photos_count = documents.filter(document_type='passport_photos').count()
        passport_book_count = documents.filter(document_type='passport_book').count()
        yellow_fever_count = documents.filter(document_type='yellow_fever').count()
        complete_pdf_count = documents.filter(document_type='complete_pdf').count()
        other_count = documents.filter(document_type='other').count()
        
        doc_lines = []
        if complete_pdf_count > 0:
            doc_lines.append(f"✓ Complete PDF Package: {complete_pdf_count}")
        if passport_photos_count > 0:
            doc_lines.append(f"✓ Passport Photos: {passport_photos_count}")
        if passport_book_count > 0:
            doc_lines.append(f"✓ Passport Book Pages: {passport_book_count}")
        if yellow_fever_count > 0:
            doc_lines.append(f"✓ Yellow Fever Certificates: {yellow_fever_count}")
        if other_count > 0:
            doc_lines.append(f"✓ Other Documents: {other_count}")
        
        if doc_lines:
            for line in doc_lines:
                c.drawString(70, y_position, line)
                y_position -= 25
        else:
            c.drawString(70, y_position, "No documents uploaded yet")
            y_position -= 25
        
        # Footer
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(50, 30, "Dubai Documents Management System")
        c.drawString(width - 200, 30, f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M')}")
        
        c.save()
        return pdf_path
    except Exception as e:
        print(f"Error generating summary PDF: {e}")
        return None
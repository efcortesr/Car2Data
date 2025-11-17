import os
import threading
import traceback
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, CreateView, ListView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import Document, ExtractedData
from .forms import DocumentUploadForm
from services.pdf_extractor import PDFExtractor
import logging

logger = logging.getLogger(__name__)

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'documents/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_documents = Document.objects.filter(user=self.request.user)
        
        # Documentos recientes (últimos 5)
        context['recent_documents'] = user_documents.order_by('-uploaded_at')[:5]
        
        # Contadores
        context['total_documents'] = user_documents.count()
        context['processed_documents'] = user_documents.filter(status='completed').count()
        context['processing_documents'] = user_documents.filter(status__in=['pending', 'processing']).count()
        
        # INFORMACIÓN DE SUSCRIPCIÓN
        try:
            subscription = self.request.user.subscription
            context['subscription'] = subscription
            context['documents_used'] = subscription.documents_used
            context['documents_limit'] = subscription.get_documents_limit()
            context['documents_remaining'] = subscription.get_remaining_documents()
            context['can_upload'] = subscription.can_generate_document()
            context['plan_name'] = subscription.get_plan_display()
        except:
            # Si no tiene suscripción, valores por defecto
            context['subscription'] = None
            context['documents_used'] = 0
            context['documents_limit'] = 3
            context['documents_remaining'] = 3
            context['can_upload'] = True
            context['plan_name'] = 'Starter'
        
        return context

class DocumentUploadView(LoginRequiredMixin, CreateView):
    model = Document
    form_class = DocumentUploadForm
    template_name = 'documents/upload.html'
    
    def form_valid(self, form):
        # VERIFICAR LÍMITE DE DOCUMENTOS ANTES DE SUBIR
        try:
            subscription = self.request.user.subscription
        except:
            messages.error(self.request, 'No se encontró tu suscripción. Por favor, contacta al soporte técnico.')
            return redirect('documents:dashboard')
        
        # Verificar si puede generar más documentos
        if not subscription.can_generate_document():
            messages.warning(
                self.request,
                f'Has alcanzado tu límite de {subscription.get_documents_limit()} documentos en el plan gratuito. '
                f'¡Actualiza a Pro para obtener hasta 100 documentos por mes!'
            )
            return redirect('authentication:checkout')
        
        # Proceder con el guardado
        form.instance.user = self.request.user
        response = super().form_valid(form)
        
        # Iniciar procesamiento en segundo plano
        if self.object.file:
            logger.info(f"Iniciando procesamiento para documento {self.object.id}")
            thread = threading.Thread(
                target=self.process_document_background,
                args=(self.object.id,)
            )
            thread.daemon = True
            thread.start()
        
        remaining = subscription.get_remaining_documents() - 1  # -1 porque estamos procesando uno ahora
        messages.success(
            self.request, 
            f'Documento subido correctamente. Te quedan {remaining} documentos disponibles en tu plan actual.'
        )
        return response
    
    def process_document_background(self, document_id):
        """Procesa el documento en segundo plano"""
        document = None
        try:
            logger.info(f"Iniciando procesamiento en segundo plano para documento {document_id}")
            
            document = Document.objects.get(id=document_id)
            document.status = 'processing'
            document.save()
            
            logger.info(f"Documento marcado como 'processing': {document.name}")
            
            # Verificar que el archivo existe
            if not document.file or not os.path.exists(document.file.path):
                raise FileNotFoundError(f"No se pudo encontrar el archivo: {document.file.path if document.file else 'No especificado'}")
            
            # Obtener la ruta del archivo
            pdf_path = document.file.path
            logger.info(f"Ruta del PDF: {pdf_path}")
            
            # Crear extractor y probar conexión
            extractor = PDFExtractor()
            
            # Probar conexión antes de procesar
            if not extractor.test_connection():
                # Manejo controlado cuando no hay cuota/conectividad/modelo inválido
                logger.warning("Gemini no disponible o modelo inválido. Documento marcado como error amigable.")
                document.status = 'error'
                document.error_message = (
                    "El servicio de IA no está disponible en este momento (cuota, conectividad o modelo no soportado). "
                    "Inténtalo de nuevo más tarde o verifica la configuración."
                )
                document.save()
                return

            logger.info("Conexión con Gemini establecida correctamente")
            
            # Extraer información usando Gemini con timeout
            try:
                extracted_data = extractor.extract_vehicle_info(pdf_path)
                logger.info(f"Datos extraídos: {extracted_data}")
                
                # Guardar los datos extraídos
                document.set_extracted_data(extracted_data)
                
                # Actualizar el tipo de documento si se identificó
                if extracted_data.get('tipo_documento') and extracted_data.get('tipo_documento') != 'No identificado':
                    doc_type = extracted_data.get('tipo_documento', '').lower()
                    doc_type_mapping = {
                        'matrícula': 'registration',
                        'matricula': 'registration',
                        'registro': 'registration',
                        'propiedad': 'ownership',
                        'tarjeta': 'ownership'
                    }
                    
                    for key, value in doc_type_mapping.items():
                        if key in doc_type:
                            document.document_type = value
                            break
                
                document.status = 'completed'
                document.processed_at = timezone.now()
                document.error_message = ''
                logger.info(f"Documento procesado exitosamente: {document.name}")
                
                # INCREMENTAR CONTADOR DE DOCUMENTOS USADOS
                try:
                    subscription = document.user.subscription
                    subscription.increment_documents()
                    logger.info(f"Contador incrementado. Documentos usados: {subscription.documents_used}/{subscription.get_documents_limit()}")
                except Exception as e:
                    logger.error(f"Error al actualizar el contador de documentos: {str(e)}")
                
            except Exception as e:
                logger.error(f"Error durante el procesamiento del documento: {str(e)}")
                logger.error(traceback.format_exc())
                document.status = 'error'
                document.error_message = f"Error al procesar el documento: {str(e)}"
            
            document.save()
            
        except FileNotFoundError as e:
            logger.error(f"Error: Archivo no encontrado - {str(e)}")
            if document:
                document.status = 'error'
                document.error_message = f"No se pudo encontrar el archivo: {str(e)}"
                document.save()
        except Exception as e:
            logger.error(f"Error al procesar el documento: {str(e)}")
            logger.error(traceback.format_exc())
            
            if document:
                document.status = 'error'
                document.error_message = f"Ocurrió un error inesperado: {str(e)}"
                document.save()
                logger.info(f"Documento {document_id} marcado como error")

class DataPreviewView(LoginRequiredMixin, TemplateView):
    template_name = 'documents/data_preview.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doc_id = kwargs['pk']
        document = get_object_or_404(Document, id=doc_id, user=self.request.user)
        
        # Obtener datos extraídos
        extracted_data = document.get_extracted_data()
        
        context['document'] = document
        context['extracted_data'] = extracted_data
        return context

class DocumentHistoryView(LoginRequiredMixin, ListView):
    model = Document
    template_name = 'documents/history.html'
    context_object_name = 'documents'
    paginate_by = 10
    
    def get_queryset(self):
        return Document.objects.filter(
            user=self.request.user
        ).order_by('-uploaded_at')

class ProcessDocumentView(LoginRequiredMixin, TemplateView):
    template_name = 'documents/process.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doc_id = kwargs['pk']
        context['document'] = get_object_or_404(
            Document, id=doc_id, user=self.request.user
        )
        return context

@login_required
@require_POST
@csrf_exempt
def reprocess_document(request, pk):
    """Reprocesa un documento"""
    try:
        document = get_object_or_404(Document, id=pk, user=request.user)
        
        logger.info(f"Reprocessing document {pk}")
        
        # Reiniciar estado
        document.status = 'processing'
        document.extraction_error = None
        document.extracted_data_json = None
        document.save()
        
        # Procesar en segundo plano
        upload_view = DocumentUploadView()
        thread = threading.Thread(
            target=upload_view.process_document_background,
            args=(document.id,)
        )
        thread.daemon = True
        thread.start()
        
        return JsonResponse({'status': 'success', 'message': 'Reprocesamiento iniciado'})
    except Exception as e:
        logger.error(f"Error en reprocess_document: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
def document_status(request, pk):
    """Obtiene el estado actual de un documento"""
    try:
        document = get_object_or_404(Document, id=pk, user=request.user)
        return JsonResponse({
            'status': document.status,
            'processed_at': document.processed_at.isoformat() if document.processed_at else None,
            'error': document.extraction_error
        })
    except Exception as e:
        logger.error(f"Error en document_status: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)})
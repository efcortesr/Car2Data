# car2data_project/services/DocumentGenerator.py

import os
import json
from datetime import datetime
from decimal import Decimal
from django.conf import settings
from django.template.loader import get_template
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch
from .PdfFormFiller import PDFFormFiller  # Nota: El nombre del archivo es case-sensitive
import logging

logger = logging.getLogger(__name__)

class DocumentGenerator:
    """
    Servicio para generar documentos PDF autodiligenciados
    Utiliza plantillas PDF oficiales cuando están disponibles,
    y genera documentos con ReportLab como respaldo
    """
    
    def __init__(self):
        # Asegurarse de que el directorio de plantillas existe
        self.templates_path = os.path.join(settings.STATIC_ROOT, 'pdf_templates')
        if not os.path.exists(self.templates_path):
            os.makedirs(self.templates_path, exist_ok=True)
            
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
        # Inicializar el sistema de relleno de formularios
        self.pdf_form_filler = PDFFormFiller()
        
        # Verificar que las plantillas existan
        self.verify_templates()
    
    def verify_templates(self):
        """Verificar que las plantillas necesarias existan"""
        required_templates = [
            'formulario_tramite_template.pdf',
            'contrato_compraventa_template.pdf',
            'contrato_mandato_template.pdf'
        ]
        
        for template in required_templates:
            template_path = os.path.join(self.templates_path, template)
            if not os.path.exists(template_path):
                logger.warning(f'Plantilla no encontrada: {template_path}')
                
    def setup_custom_styles(self):
        """Configurar estilos personalizados para los PDFs"""
        if 'Title' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='Title',
                parent=self.styles['Heading1'],
                fontSize=16,
                spaceAfter=20,
                alignment=1,  # Centrado
                textColor=colors.HexColor('#0e2455')
            ))
        
        if 'Subtitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='Subtitle',
                parent=self.styles['Heading2'],
                fontSize=12,
                spaceAfter=12,
                textColor=colors.HexColor('#12c3d6')
            ))
        
        if 'Field' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='Field',
                parent=self.styles['Normal'],
                fontSize=10,
                spaceAfter=6,
            ))
    
    def generate_contrato_mandato(self, extracted_data, mandante_data, mandatario_data, document_path):
        """Genera un contrato de mandato usando plantilla PDF oficial"""
        logger.info(f"Iniciando generación de Contrato de Mandato para el documento: {document_path}")
        logger.debug(f"Datos extraídos: {json.dumps(extracted_data, indent=2, default=str)}")
        logger.debug(f"Datos del mandante: {json.dumps(mandante_data, indent=2, default=str)}")
        logger.debug(f"Datos del mandatario: {json.dumps(mandatario_data, indent=2, default=str)}")

        try:
            # Preparar datos para el relleno del formulario
            form_data = {
                'vehiculo': extracted_data.get('vehiculo', {}),
                'mandante': {
                    'nombre': mandante_data.get('nombre', ''),
                    'documento': mandante_data.get('documento', ''),
                    'ciudad': mandante_data.get('ciudad', ''),
                    'direccion': mandante_data.get('direccion', ''),
                    'telefono': mandante_data.get('telefono', '')
                },
                'mandatario': {
                    'nombre': mandatario_data.get('nombre', ''),
                    'documento': mandatario_data.get('documento', ''),
                    'ciudad': mandatario_data.get('ciudad', ''),
                    'direccion': mandatario_data.get('direccion', ''),
                    'telefono': mandatario_data.get('telefono', '')
                },
                # Incluir todos los datos adicionales del formulario
                'tramites_autorizados': extracted_data.get('tramites_autorizados', ''),
                'organismo_transito': extracted_data.get('organismo_transito', ''),
                'ciudad_contrato': extracted_data.get('ciudad_contrato', ''),
                'fecha_contrato': extracted_data.get('fecha_contrato', '')
            }
            
            # Asegurarse de que los datos del vehículo estén en el nivel superior para compatibilidad
            if 'vehiculo' in extracted_data and extracted_data['vehiculo']:
                form_data.update({
                    'placa': extracted_data['vehiculo'].get('placa', ''),
                    'marca': extracted_data['vehiculo'].get('marca', ''),
                    'linea': extracted_data['vehiculo'].get('linea', ''),
                    'modelo': extracted_data['vehiculo'].get('modelo', '')
                })
            
            # Intentar usar plantilla PDF oficial primero
            success = self.pdf_form_filler.fill_pdf_form('contrato_mandato', form_data, document_path)
            
            if success:
                logger.info(f"Contrato de mandato generado con plantilla oficial: {document_path}")
                return True
            else:
                logger.warning("Plantilla oficial no disponible, usando generación por ReportLab")
                return self._generate_contrato_mandato_fallback(extracted_data, mandante_data, mandatario_data, document_path)
                
        except Exception as e:
            logger.error(f"Error generando contrato de mandato: {str(e)}")
            return False
    
    def _generate_contrato_mandato_fallback(self, extracted_data, mandante_data, mandatario_data, document_path):
        """Método de respaldo para generar contrato de mandato con ReportLab"""
        try:
            doc = SimpleDocTemplate(document_path, pagesize=letter)
            elements = []
            
            # Título
            title = Paragraph("CONTRATO DE MANDATO VEHICULAR", self.styles['Title'])
            elements.append(title)
            elements.append(Spacer(1, 20))
            
            # Información del vehículo
            vehiculo = extracted_data.get('vehiculo', {})
            if vehiculo:
                vehiculo_section = Paragraph("DATOS DEL VEHÍCULO", self.styles['Subtitle'])
                elements.append(vehiculo_section)
                
                vehiculo_info = [
                    ['Placa:', vehiculo.get('placa', 'N/A')],
                    ['Marca:', vehiculo.get('marca', 'N/A')],
                    ['Línea:', vehiculo.get('linea', 'N/A')],
                    ['Modelo:', vehiculo.get('modelo', 'N/A')]
                ]
                
                vehiculo_table = Table(vehiculo_info, colWidths=[2*inch, 4*inch])
                vehiculo_table.setStyle(TableStyle([
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                    ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
                    ('FONTSIZE', (0,0), (-1,-1), 10),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ]))
                elements.append(vehiculo_table)
                elements.append(Spacer(1, 20))
            
            # Información del mandante
            mandante_section = Paragraph("DATOS DEL MANDANTE", self.styles['Subtitle'])
            elements.append(mandante_section)
            
            mandante_info = [
                ['Nombre:', mandante_data.get('nombre', 'N/A')],
                ['Documento:', mandante_data.get('documento', 'N/A')],
                ['Dirección:', mandante_data.get('direccion', 'N/A')],
                ['Teléfono:', mandante_data.get('telefono', 'N/A')],
                ['Ciudad:', mandante_data.get('ciudad', 'N/A')]
            ]
            
            mandante_table = Table(mandante_info, colWidths=[2*inch, 4*inch])
            mandante_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            elements.append(mandante_table)
            elements.append(Spacer(1, 20))
            
            # Información del mandatario
            mandatario_section = Paragraph("DATOS DEL MANDATARIO", self.styles['Subtitle'])
            elements.append(mandatario_section)
            
            mandatario_info = [
                ['Nombre:', mandatario_data.get('nombre', 'N/A')],
                ['Documento:', mandatario_data.get('documento', 'N/A')],
                ['Dirección:', mandatario_data.get('direccion', 'N/A')],
                ['Teléfono:', mandatario_data.get('telefono', 'N/A')],
                ['Ciudad:', mandatario_data.get('ciudad', 'N/A')]
            ]
            
            mandatario_table = Table(mandatario_info, colWidths=[2*inch, 4*inch])
            mandatario_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            elements.append(mandatario_table)
            elements.append(Spacer(1, 20))
            
            # Información del contrato
            contrato_section = Paragraph("INFORMACIÓN DEL CONTRATO", self.styles['Subtitle'])
            elements.append(contrato_section)
            
            # Obtener datos del formulario
            tramites = extracted_data.get('tramites_autorizados', 'No especificado')
            organismo = extracted_data.get('organismo_transito', 'No especificado')
            ciudad = extracted_data.get('ciudad_contrato', 'No especificada')
            fecha = extracted_data.get('fecha_contrato', 'No especificada')
            
            if isinstance(fecha, str):
                try:
                    fecha_dt = datetime.strptime(fecha, '%Y-%m-%d')
                    fecha = fecha_dt.strftime('%d/%m/%Y')
                except (ValueError, TypeError):
                    pass
            
            contrato_info = [
                ['Trámites Autorizados:', tramites],
                ['Organismo de Tránsito:', organismo],
                ['Ciudad del Contrato:', ciudad],
                ['Fecha del Contrato:', fecha]
            ]
            
            contrato_table = Table(contrato_info, colWidths=[2*inch, 4*inch])
            contrato_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('VALIGN', (0,0), (0,0), 'TOP'),
                ('VALIGN', (1,0), (1,0), 'TOP'),
            ]))
            elements.append(contrato_table)
            elements.append(Spacer(1, 20))
            
            # Información del vehículo
            vehiculo_section = Paragraph("DATOS DEL VEHÍCULO", self.styles['Subtitle'])
            elements.append(vehiculo_section)
            
            # Obtener la información del vehículo de la estructura correcta
            vehiculo_info = extracted_data.get('vehiculo', {})
            
            vehiculo_data = [
                ['Placa:', vehiculo_info.get('placa', 'N/A')],
                ['Marca:', vehiculo_info.get('marca', 'N/A')],
                ['Línea:', vehiculo_info.get('linea', 'N/A')],
                ['Modelo:', str(vehiculo_info.get('modelo', 'N/A'))],
                ['Color:', vehiculo_info.get('color', 'N/A')],
                ['VIN:', vehiculo_info.get('vin', 'N/A')],
                ['Número de Motor:', vehiculo_info.get('numero_motor', 'N/A')],
                ['Número de Chasis:', vehiculo_info.get('numero_chasis', 'N/A')],
                ['Cilindrada (cc):', str(vehiculo_info.get('cilindrada_cc', 'N/A'))],
                ['Combustible:', vehiculo_info.get('combustible', 'N/A')],
                ['Servicio:', vehiculo_info.get('servicio', 'N/A')]
            ]
            
            vehiculo_table = Table(vehiculo_data, colWidths=[2*inch, 4*inch])
            vehiculo_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            elements.append(vehiculo_table)
            elements.append(Spacer(1, 20))
            
            # Cláusulas del contrato
            clausulas_section = Paragraph("CLÁUSULAS", self.styles['Subtitle'])
            elements.append(clausulas_section)
            
            clausulas = [
                "PRIMERA: El MANDANTE confiere poder especial al MANDATARIO para realizar ante los organismos de tránsito todos los trámites relacionados con el vehículo descrito.",
                "SEGUNDA: El presente mandato incluye específicamente: Registro, matrícula, cambio de propietario, traspasos, y demás trámites ante autoridades de tránsito.",
                "TERCERA: El MANDATARIO se obliga a realizar las gestiones con la debida diligencia y cuidado.",
                "CUARTA: Este contrato se regirá por las leyes colombianas vigentes."
            ]
            
            for clausula in clausulas:
                elements.append(Paragraph(clausula, self.styles['Normal']))
                elements.append(Spacer(1, 12))
            
            # Firmas
            elements.append(Spacer(1, 40))
            firmas = [
                ['_________________________', '_________________________'],
                ['MANDANTE', 'MANDATARIO'],
                [mandante_data.get('nombre', 'N/A'), mandatario_data.get('nombre', 'N/A')],
                [f"C.C. {mandante_data.get('documento', 'N/A')}", f"C.C. {mandatario_data.get('documento', 'N/A')}"]
            ]
            
            firmas_table = Table(firmas, colWidths=[3*inch, 3*inch])
            firmas_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ]))
            elements.append(firmas_table)
            
            # Fecha y ciudad
            fecha_info = f"Fecha: {datetime.now().strftime('%d de %B de %Y')}"
            elements.append(Spacer(1, 20))
            elements.append(Paragraph(fecha_info, self.styles['Normal']))
            
            doc.build(elements)
            logger.info(f"Contrato de mandato generado exitosamente (fallback): {document_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error generando contrato de mandato (fallback): {str(e)}")
            return False
    
    def generate_contrato_compraventa(self, extracted_data, vendedor_data, comprador_data, 
                                    valor_venta, document_path, forma_pago=None):
        """Genera un contrato de compraventa usando plantilla PDF oficial"""
        logger.info(f"Iniciando generación de Contrato de Compraventa para el documento: {document_path}")
        logger.debug(f"Datos extraídos para el vehículo: {json.dumps(extracted_data, indent=2, default=str)}")
        logger.debug(f"Datos del vendedor: {json.dumps(vendedor_data, indent=2, default=str)}")
        logger.debug(f"Datos del comprador: {json.dumps(comprador_data, indent=2, default=str)}")
        logger.debug(f"Valor de venta: {valor_venta}")

        try:
            # Preparar datos para el relleno del formulario
            form_data = {
                'vehiculo': extracted_data.get('vehiculo', {}),
                'vendedor': {
                    'nombre': vendedor_data.get('nombre', ''),
                    'documento': vendedor_data.get('documento', ''),
                    'ciudad': vendedor_data.get('ciudad', ''),
                    'direccion': vendedor_data.get('direccion', ''),
                    'telefono': vendedor_data.get('telefono', '')
                },
                'comprador': {
                    'nombre': comprador_data.get('nombre', ''),
                    'documento': comprador_data.get('documento', ''),
                    'ciudad': comprador_data.get('ciudad', ''),
                    'direccion': comprador_data.get('direccion', ''),
                    'telefono': comprador_data.get('telefono', '')
                },
                'valor_venta': valor_venta,
                'forma_pago': forma_pago
            }
            
            # Intentar usar plantilla PDF oficial primero
            success = self.pdf_form_filler.fill_pdf_form('contrato_compraventa', form_data, document_path)
            
            if success:
                logger.info(f"Contrato de compraventa generado con plantilla oficial: {document_path}")
                return True
            else:
                logger.warning("Plantilla oficial no disponible, usando generación por ReportLab")
                return self._generate_contrato_compraventa_fallback(extracted_data, vendedor_data, comprador_data, valor_venta, document_path)
                
        except Exception as e:
            logger.error(f"Error generando contrato de compraventa: {str(e)}")
            return False
    
    def _generate_contrato_compraventa_fallback(self, extracted_data, vendedor_data, comprador_data, 
                                              valor_venta, document_path):
        """Método de respaldo para generar contrato de compraventa con ReportLab"""
        try:
            doc = SimpleDocTemplate(document_path, pagesize=letter)
            elements = []
            
            # Título
            title = Paragraph("CONTRATO DE COMPRAVENTA VEHICULAR", self.styles['Title'])
            elements.append(title)
            elements.append(Spacer(1, 20))
            
            # Información del vendedor
            vendedor_section = Paragraph("DATOS DEL VENDEDOR", self.styles['Subtitle'])
            elements.append(vendedor_section)
            
            vendedor_info = [
                ['Nombre:', vendedor_data.get('nombre', 'N/A')],
                ['Documento:', vendedor_data.get('documento', 'N/A')],
                ['Dirección:', vendedor_data.get('direccion', 'N/A')],
                ['Teléfono:', vendedor_data.get('telefono', 'N/A')],
                ['Ciudad:', vendedor_data.get('ciudad', 'N/A')]
            ]
            
            vendedor_table = Table(vendedor_info, colWidths=[2*inch, 4*inch])
            vendedor_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            elements.append(vendedor_table)
            elements.append(Spacer(1, 20))
            
            # Información del comprador
            comprador_section = Paragraph("DATOS DEL COMPRADOR", self.styles['Subtitle'])
            elements.append(comprador_section)
            
            comprador_info = [
                ['Nombre:', comprador_data.get('nombre', 'N/A')],
                ['Documento:', comprador_data.get('documento', 'N/A')],
                ['Dirección:', comprador_data.get('direccion', 'N/A')],
                ['Teléfono:', comprador_data.get('telefono', 'N/A')],
                ['Ciudad:', comprador_data.get('ciudad', 'N/A')]
            ]
            
            comprador_table = Table(comprador_info, colWidths=[2*inch, 4*inch])
            comprador_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            elements.append(comprador_table)
            elements.append(Spacer(1, 20))
            
            # Información del vehículo
            vehiculo_section = Paragraph("DATOS DEL VEHÍCULO", self.styles['Subtitle'])
            elements.append(vehiculo_section)
            
            vehiculo_info = extracted_data.get('vehiculo', {})
            
            vehiculo_data = [
                ['Placa:', vehiculo_info.get('placa', 'N/A')],
                ['Marca:', vehiculo_info.get('marca', 'N/A')],
                ['Línea:', vehiculo_info.get('linea', 'N/A')],
                ['Modelo:', str(vehiculo_info.get('modelo', 'N/A'))],
                ['Color:', vehiculo_info.get('color', 'N/A')],
                ['VIN:', vehiculo_info.get('vin', 'N/A')],
                ['Número de Motor:', vehiculo_info.get('numero_motor', 'N/A')],
                ['Número de Chasis:', vehiculo_info.get('numero_chasis', 'N/A')],
                ['Cilindrada (cc):', str(vehiculo_info.get('cilindrada_cc', 'N/A'))],
                ['Combustible:', vehiculo_info.get('combustible', 'N/A')],
                ['Servicio:', vehiculo_info.get('servicio', 'N/A')],
                ['Clase de Vehículo:', vehiculo_info.get('clase_vehiculo', 'N/A')],
                ['Tipo de Carrocería:', vehiculo_info.get('tipo_carroceria', 'N/A')],
                ['Capacidad (Kg/PSJ):', str(vehiculo_info.get('capacidad_kg_psj', 'N/A'))],
                ['Potencia (HP):', str(vehiculo_info.get('potencia_hp', 'N/A'))],
                ['Puertas:', str(vehiculo_info.get('puertas', 'N/A'))]
            ]
            
            vehiculo_table = Table(vehiculo_data, colWidths=[2*inch, 4*inch])
            vehiculo_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            elements.append(vehiculo_table)
            elements.append(Spacer(1, 20))
            
            # Valor de venta
            valor_section = Paragraph("VALOR DE LA VENTA", self.styles['Subtitle'])
            elements.append(valor_section)
            
            valor_formateado = f"${valor_venta:,.2f}" if valor_venta else "N/A"
            valor_info = [
                ['Valor en números:', valor_formateado],
                ['Valor en letras:', self.number_to_words(valor_venta) if valor_venta else 'N/A']
            ]
            
            valor_table = Table(valor_info, colWidths=[2*inch, 4*inch])
            valor_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            elements.append(valor_table)
            elements.append(Spacer(1, 20))
            
            # Cláusulas del contrato
            clausulas_section = Paragraph("CLÁUSULAS", self.styles['Subtitle'])
            elements.append(clausulas_section)
            
            clausulas = [
                "PRIMERA: El VENDEDOR declara ser propietario del vehículo descrito y lo vende al COMPRADOR.",
                "SEGUNDA: El COMPRADOR acepta la compra del vehículo en las condiciones descritas.",
                "TERCERA: El precio de venta es el establecido y será pagado en la forma acordada.",
                "CUARTA: El vehículo se entrega en el estado en que se encuentra.",
                "QUINTA: Los gastos de traspaso corren por cuenta del COMPRADOR."
            ]
            
            for clausula in clausulas:
                elements.append(Paragraph(clausula, self.styles['Normal']))
                elements.append(Spacer(1, 12))
            
            # Firmas
            elements.append(Spacer(1, 40))
            firmas = [
                ['_________________________', '_________________________'],
                ['VENDEDOR', 'COMPRADOR'],
                [vendedor_data.get('nombre', 'N/A'), comprador_data.get('nombre', 'N/A')],
                [f"C.C. {vendedor_data.get('documento', 'N/A')}", f"C.C. {comprador_data.get('documento', 'N/A')}"]
            ]
            
            firmas_table = Table(firmas, colWidths=[3*inch, 3*inch])
            firmas_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ]))
            elements.append(firmas_table)
            
            # Fecha y ciudad
            fecha_info = f"Fecha: {datetime.now().strftime('%d de %B de %Y')}"
            elements.append(Spacer(1, 20))
            elements.append(Paragraph(fecha_info, self.styles['Normal']))
            
            doc.build(elements)
            logger.info(f"Contrato de compraventa generado exitosamente (fallback): {document_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error generando contrato de compraventa (fallback): {str(e)}")
            return False
    
    def generate_formulario_tramite(self, form_data, documento_path):
        """Genera un formulario de trámite usando plantilla PDF oficial y los datos del formulario."""
        logger.info(f"Iniciando generación de Formulario de Trámite: {documento_path}")
        logger.debug(f"Datos del formulario para el PDF: {json.dumps(form_data, indent=2, default=str)}")

        try:
            # Los datos del formulario ya están completos, se pasan directamente
            success = self.pdf_form_filler.fill_pdf_form('formulario_tramite', form_data, documento_path)
            
            if success:
                logger.info(f"Formulario de trámite generado con plantilla oficial: {documento_path}")
                return True
            else:
                logger.warning("Plantilla oficial no disponible, usando generación por ReportLab")
                return self._generate_formulario_tramite_fallback(form_data, documento_path)
                
        except Exception as e:
            logger.error(f"Error generando formulario de trámite: {str(e)}")
            return False
    
    def _generate_formulario_tramite_fallback(self, form_data, documento_path):
        """Método de respaldo para generar formulario de trámite con ReportLab usando datos del formulario."""
        try:
            doc = SimpleDocTemplate(documento_path, pagesize=letter)
            elements = []
            
            title = Paragraph("FORMULARIO DE TRÁMITE VEHICULAR", self.styles['Title'])
            elements.append(title)
            elements.append(Spacer(1, 20))
            
            vehiculo_section = Paragraph("INFORMACIÓN DEL VEHÍCULO", self.styles['Subtitle'])
            elements.append(vehiculo_section)
            
            vehiculo_data = [
                ['Placa:', form_data.get('placa', 'N/A')],
                ['Marca:', form_data.get('marca', 'N/A')],
                ['Línea:', form_data.get('linea', 'N/A')],
                ['Modelo:', str(form_data.get('modelo', 'N/A'))],
                ['Color:', form_data.get('color', 'N/A')],
                ['VIN:', form_data.get('numero_vin', 'N/A')],
                ['Número de Motor:', form_data.get('numero_motor', 'N/A')],
                ['Número de Chasis:', form_data.get('numero_chasis', 'N/A')],
                ['Cilindrada (cc):', str(form_data.get('cilindrada', 'N/A'))],
                ['Carrocería:', form_data.get('carroceria', 'N/A')]
            ]
            
            vehiculo_table = Table(vehiculo_data, colWidths=[2*inch, 4*inch])
            vehiculo_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
            ]))
            elements.append(vehiculo_table)
            elements.append(Spacer(1, 20))

            propietario_section = Paragraph("INFORMACIÓN DEL PROPIETARIO", self.styles['Subtitle'])
            elements.append(propietario_section)
            
            propietario_nombre = f"{form_data.get('propietario_primer_apellido','')} {form_data.get('propietario_segundo_apellido','')} {form_data.get('propietario_nombres','')}".strip()
            propietario_data = [
                ['Nombre:', propietario_nombre],
                ['Identificación:', form_data.get('propietario_documento', 'N/A')],
                ['Dirección:', form_data.get('propietario_direccion', 'N/A')],
                ['Ciudad:', form_data.get('propietario_ciudad', 'N/A')],
                ['Teléfono:', form_data.get('propietario_telefono', 'N/A')]
            ]
            
            propietario_table = Table(propietario_data, colWidths=[2*inch, 4*inch])
            propietario_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
            ]))
            elements.append(propietario_table)
            elements.append(Spacer(1, 20))

            # Detalles de registro (si están disponibles en el formulario)
            registro_section = Paragraph("DETALLES DE REGISTRO", self.styles['Subtitle'])
            elements.append(registro_section)

            registro_data = [
                ['Licencia de Tránsito:', form_data.get('licencia_transito', 'N/A')],
                ['Organismo de Tránsito:', form_data.get('organismo_transito', 'N/A')],
                ['Fecha de Matrícula:', form_data.get('fecha_matricula', 'N/A')]
            ]
            
            registro_table = Table(registro_data, colWidths=[2*inch, 4*inch])
            registro_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
            ]))
            elements.append(registro_table)
            elements.append(Spacer(1, 30))

            # Observaciones (si vienen en el formulario)
            observaciones = form_data.get('observaciones', '')
            if observaciones:
                obs_section = Paragraph("OBSERVACIONES", self.styles['Subtitle'])
                elements.append(obs_section)
                obs_paragraph = Paragraph(observaciones.replace('\n', '<br/>'), self.styles['Normal'])
                elements.append(obs_paragraph)
                elements.append(Spacer(1, 20))

            # Fecha y firma
            fecha_info = f"Fecha de diligenciamiento: {datetime.now().strftime('%d/%m/%Y')}"
            elements.append(Paragraph(fecha_info, self.styles['Normal']))
            elements.append(Spacer(1, 40))

            firma_info = "____________________________\nFirma del solicitante"
            elements.append(Paragraph(firma_info, self.styles['Normal']))

            doc.build(elements)
            logger.info(f"Formulario de trámite generado exitosamente (fallback): {documento_path}")
            return True

        except Exception as e:
            logger.error(f"Error generando formulario de trámite (fallback): {str(e)}")
            return False

    def number_to_words(self, number):
        """Convierte números a palabras (implementación básica)"""
        try:
            # Implementación básica - en producción usar una librería como num2words
            if not number:
                return "Cero pesos"
            
            # Para simplificar, retornamos un formato básico
            return f"{number:.2f} pesos colombianos"
            
        except Exception:
            return "N/A"

    def get_document_path(self, form_type, document_id):
        """Genera la ruta donde se guardará el documento"""
        filename = f"{form_type}_{document_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return os.path.join(settings.MEDIA_ROOT, 'generated_forms', filename)
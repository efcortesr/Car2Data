# car2data_project/services/PDFFormFiller.py - VERSIÓN MEJORADA

import os
import logging
from datetime import datetime
from django.conf import settings
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PyPDF2 import PdfReader, PdfWriter
import io

logger = logging.getLogger(__name__)

class PDFFormFiller:
    """
    Servicio mejorado para rellenar formularios PDF oficiales usando plantillas
    Con coordenadas más precisas y mejor mapeo de campos
    """
    
    def __init__(self):
        self.templates_path = os.path.join(settings.BASE_DIR, 'static', 'pdf_templates')
        self.setup_fonts()
        
        # COORDENADAS CORREGIDAS - Ajustadas según los resultados mostrados
        # Las coordenadas son (X, Y) desde la esquina INFERIOR IZQUIERDA
        # 1 punto = 1/72 pulgadas. Página carta = 612x792 puntos
        self.required_fields = {
            'formulario_tramite': [
                'placa', 'marca', 'linea', 'modelo', 'color',
                'propietario_nombres', 'propietario_documento'
            ],
            'contrato_compraventa': {
                'vehiculo': ['placa', 'marca', 'linea', 'modelo'],
                'vendedor': ['nombre', 'documento'],
                'comprador': ['nombre', 'documento'],
                'valor_venta': None
            },
            'contrato_mandato': {
                'vehiculo': ['placa'],
                'mandante': ['nombre', 'documento'],
                # Mandatario opcional: permitir generar sin datos de mandatario
                'mandatario': []
            }
        }
        self.field_coordinates = {
            'formulario_tramite': {
                # Placa - Campo 2 (corregido para alinearse con campos reales)
                'placa_letras': (750, 495),    # Posición exacta del campo letras
                'placa_numeros': (770, 495),   # Posición exacta del campo números

                # Campos de vehículo (reposicionados según cuadrícula)
                'marca': (390, 460),              # Campo 5 - posición corregida
                'linea': (480, 460),              # Campo 6 - posición corregida
                'color': (390, 430),              # Campo 8 - posición corregida
                'modelo': (660, 430),             # Campo 9 - posición corregida
                'cilindrada': (720, 430),         # Campo 10 - posición corregida

                # Capacidad, Blindaje, Potencia (reajustados)
                'capacidad': (390, 405),          # Campo 11        # Campo 13 NO
                'potencia': (720, 405),           # Campo 14

                # Tipo de combustible (fila de checkboxes) - reposicionados
                'combustible_gasolina': (575, 453),
                'combustible_diesel': (606, 453),
                'combustible_gas': (626, 453),
                'combustible_mixto': (656, 453),
                'combustible_electrico': (686, 453),
                'combustible_hidrogeno': (716, 453),
                'combustible_etanol': (746, 453),
                'combustible_biodiesel': (776, 453),

                # Clase de vehículo (reposicionados según cuadrícula)
                'clase_automovil': (30, 370),
                'clase_bus': (90, 370),
                'clase_buseta': (120, 370),
                'clase_camion': (170, 370),
                'clase_campero': (270, 370),
                'clase_camioneta': (220, 370),
                'clase_tractocamion': (30, 370),
                'clase_motocicleta': (90, 350),
                'clase_motocarro': (120, 350),
                'clase_mototriciclo': (170, 350),
                'clase_cuatrimoto': (220, 350),
                'clase_volqueta': (270, 350),
                'clase_microbus': (320, 370),
                'clase_otro': (320, 350),

                # Carrocería - Campo 15 (corregido)
                'carroceria': (390, 345),

                # Identificación del vehículo - Campo 16 (coordenadas corregidas)
                'numero_motor': (600, 370),
                'reg_motor_n': (780, 370),  # REG Motor = N
                'reg_motor_s': (755, 370),  # REG Motor = S
                'numero_chasis': (600, 350),
                'reg_chasis_n': (780, 345),  # REG Chasis = N
                'reg_chasis_s': (755, 345),  # REG Chasis = S
                'numero_serie': (600, 320),
                'reg_serie_n': (780, 320),  # REG Serie = N
                'reg_serie_s': (755, 320),  # REG Serie = S
                'numero_vin': (600, 290),

                # Tipo de servicio - Campo 18 (coordenadas corregidas según imagen)
                'servicio_particular': (602, 240),
                'servicio_publico': (620, 240),
                'servicio_diplomatico': (650, 240),
                'servicio_oficial': (680, 240),
                'servicio_especial': (710, 240),
                'otros_servicio': (740, 240),

                # Datos del propietario - Campo 21 (coordenadas corregidas según imagen)
                'propietario_primer_apellido': (30, 290),
                'propietario_segundo_apellido': (140, 290),
                'propietario_nombres': (270, 290),

                # Tipo de documento del propietario (reajustados)


                'propietario_documento': (320, 265),
                'propietario_direccion': (30, 240),
                'propietario_ciudad': (205, 240),
                'propietario_telefono': (320, 240),

                # Datos del comprador (traspaso) - Campo 22 (coordenadas corregidas)
                'comprador_primer_apellido': (30, 155),
                'comprador_segundo_apellido': (140, 155),
                'comprador_nombres': (270, 155),

                # Tipo de documento del comprador (reajustados)


                'comprador_documento': (320, 125),
                'comprador_direccion': (30, 100),
                'comprador_ciudad': (205, 100),
                'comprador_telefono': (320, 100),

                # Observaciones - Campo 23 (reposicionado)
                'observaciones': (390, 130),

                # Datos de importación
                'declaracion_importacion': (390, 250),
                'importacion_dia': (480, 250),
                'importacion_mes': (505, 250),
                'importacion_ano': (545, 250),
            },
            
            'contrato_compraventa': {
                # Basadas en la imagen de resultado mostrada
                
                # Línea de vendedor (coordenadas corregidas según cuadrícula)
                'vendedor_nombre': (130, 690),
                'vendedor_ciudad': (200, 675),
                
                # Línea de comprador (coordenadas corregidas)
                'comprador_nombre': (70, 645),
                'comprador_ciudad': (150, 630),
                
                # Identificación del vehículo (reposicionado)
                'vehiculo_tipo': (70, 545),
                
                # Campos del vehículo en tabla (coordenadas corregidas según cuadrícula)
                'marca': (140, 520),
                'linea': (370, 520),
                'placa': (140, 507),
                'modelo': (370, 507),
                'motor': (140, 493),
                'chasis': (370, 493),
                'color': (140, 481),
                'matriculado_en': (400, 481),
                'vin': (140, 468),
                'serie': (370, 468),
                
                # Precio (coordenadas ajustadas)
                'precio_numeros': (440, 440),
                'precio_letras': (80, 422),
                
                # Forma de pago (reposicionado)
                'forma_pago': (190, 377),
                
                # Lugar y fecha (coordenadas corregidas según imagen)
                'ciudad_contrato': (350, 260),
                'dia_contrato': (520, 260),
                'mes_contrato': (160, 245),
                'año_contrato': (380, 245),
                
                # Datos para firmas (coordenadas ajustadas)
                'vendedor_doc_firma': (110, 115),
                'vendedor_dir_firma': (110, 100),
                'vendedor_tel_firma': (110, 85),
                
                'comprador_doc_firma': (360, 115),
                'comprador_dir_firma': (360, 100),
                'comprador_tel_firma': (360, 85),
            },
            
            'contrato_mandato': {
                # Basadas en la imagen de resultado que muestra superposición
                
                # Primera línea - datos del mandante (coordenadas corregidas)
                'mandante_nombre': (240, 660),  # Aumentado de 635 a 680
                'mandante_ciudad': (310, 645),  # Aumentado de 610 a 655
                'mandante_documento': (245, 630), # Aumentado de 585 a 630
                
                # Segunda línea - datos del mandatario (coordenadas Y más altas)
                'mandatario_nombre': (120, 600),  # Aumentado de 545 a 590
                'mandatario_documento': (90, 570), # Aumentado de 510 a 555
                
                # Trámites autorizados (reposicionado más arriba)
                'tramites_autorizados': (90, 462), # Aumentado de 375 a 420
                
                # Placa del vehículo (coordenada Y más alta)
                'vehiculo_placa': (410, 445),  # Aumentado de 350 a 450
                
                # Organismo de tránsito (reajustado hacia arriba)
                'organismo_transito': (220, 430), # Aumentado de 325 a 425
                
                # Lugar y fecha del contrato (coordenadas Y más altas para la parte inferior)
                'ciudad_contrato': (90, 310),  # Aumentado de 240 a 340
                'dia_contrato': (223, 310),     # Aumentado de 215 a 315
                'mes_contrato': (330, 310),     # Aumentado de 215 a 315
                'año_contrato': (480, 310),     # Aumentado de 215 a 315
            }
        }
    
    def setup_fonts(self):
        """Configurar fuentes para el PDF con manejo mejorado de errores"""
        try:
            # Intentar usar fuentes del sistema en orden de preferencia
            font_attempts = [
                ('Arial', [
                    '/System/Library/Fonts/Arial.ttf',  # macOS
                    'C:\\Windows\\Fonts\\arial.ttf',    # Windows
                    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',  # Linux
                ]),
                ('Helvetica', [])  # Helvetica es nativa de ReportLab
            ]
            
            for font_name, paths in font_attempts:
                if font_name == 'Helvetica':
                    # Helvetica está disponible por defecto
                    self.default_font = 'Helvetica'
                    break
                    
                for font_path in paths:
                    if os.path.exists(font_path):
                        pdfmetrics.registerFont(TTFont(font_name, font_path))
                        self.default_font = font_name
                        logger.info(f"Fuente {font_name} configurada desde: {font_path}")
                        return
            
            # Si no encontró ninguna fuente específica, usar Helvetica por defecto
            self.default_font = 'Helvetica'
            logger.info("Usando fuente Helvetica por defecto")
            
        except Exception as e:
            logger.warning(f"Error configurando fuentes: {e}")
            self.default_font = 'Helvetica'
    
    def get_template_path(self, form_type):
        """Obtener la ruta de la plantilla PDF según el tipo de formulario"""
        templates = {
            'formulario_tramite': 'formulario_tramite_template.pdf',
            'contrato_compraventa': 'contrato_compraventa_template.pdf',
            'contrato_mandato': 'contrato_mandato_template.pdf',
        }
        
        template_file = templates.get(form_type)
        if not template_file:
            raise ValueError(f"Tipo de formulario no soportado: {form_type}")
        
        template_path = os.path.join(self.templates_path, template_file)
        
        # Si no existe la plantilla, retornar None para usar fallback
        if not os.path.exists(template_path):
            logger.warning(f"Plantilla no encontrada: {template_path}")
            return None
            
        return template_path
    
    def create_overlay(self, data, form_type):
        """Crear un overlay mejorado con los datos a rellenar"""
        packet = io.BytesIO()
        # Usar el tamaño de página de la plantilla cuando esté disponible
        page_size = letter
        try:
            template_path = self.get_template_path(form_type)
            if template_path and os.path.exists(template_path):
                tpl_reader = PdfReader(open(template_path, 'rb'))
                if tpl_reader.pages:
                    mbox = tpl_reader.pages[0].mediabox
                    # PyPDF2 devuelve valores tipo DecimalObject; forzar a float
                    page_size = (float(mbox.width), float(mbox.height))
        except Exception as _e:
            # En caso de error, continuar con tamaño carta por defecto
            pass
        c = canvas.Canvas(packet, pagesize=page_size)
        
        # Configurar fuente con tamaño adecuado
        c.setFont(self.default_font, 9)
        c.setFillColorRGB(0, 0, 0)  # Negro sólido
        
        # Obtener las coordenadas para este tipo de formulario
        coordinates = self.field_coordinates.get(form_type, {})
        
        if not coordinates:
            logger.warning(f"No hay coordenadas definidas para {form_type}")
            c.save()
            packet.seek(0)
            return packet
        
        logger.info(f"Rellenando {form_type} con {len(coordinates)} campos disponibles")
        logger.debug(f"Datos recibidos para {form_type}: {data}")
        
        try:
            # Rellenar según el tipo de formulario
            if form_type == 'formulario_tramite':
                self._fill_formulario_tramite_improved(c, data, coordinates)
            elif form_type == 'contrato_compraventa':
                self._fill_contrato_compraventa_improved(c, data, coordinates)
            elif form_type == 'contrato_mandato':
                self._fill_contrato_mandato_improved(c, data, coordinates)
            else:
                logger.error(f"Tipo de formulario no soportado: {form_type}")
                return None
                
            c.save()
            packet.seek(0)
            return packet
            
        except Exception as e:
            logger.error(f"Error al crear overlay para {form_type}: {str(e)}")
            logger.exception("Detalles del error:")
            return None

    def _clean_document_number(self, doc_number: str) -> str:
        """Limpia el número de documento eliminando prefijos comunes y caracteres no numéricos."""
        if not doc_number:
            return ''
        # Eliminar prefijos comunes, puntos y espacios
        cleaned = str(doc_number).upper().replace('C.C.', '').replace('CC', '').replace('.', '').strip()
        return cleaned
    
    def _fill_formulario_tramite_improved(self, canvas_obj, data, coords):
        """Rellenar formulario de trámite con mapeo mejorado usando un diccionario de datos plano."""
        logger.info(f"Datos del formulario a rellenar: {data}")
        # Helper para obtener un valor desde data plana o desde una sección anidada 'vehiculo'
        def getv(key, aliases=None):
            if aliases is None:
                aliases = []
            # Plano
            val = data.get(key)
            if val:
                return val
            # Aliases planos
            for ak in aliases:
                if data.get(ak):
                    return data.get(ak)
            # Anidado en 'vehiculo'
            veh = data.get('vehiculo') or {}
            if veh.get(key):
                return veh.get(key)
            for ak in aliases:
                if veh.get(ak):
                    return veh.get(ak)
            return ''
        
        # Fecha actual
        today = datetime.now()
        self._draw_text_if_coord(canvas_obj, coords, 'fecha_dia', f"{today.day:02d}")
        self._draw_text_if_coord(canvas_obj, coords, 'fecha_mes', f"{today.month:02d}")
        self._draw_text_if_coord(canvas_obj, coords, 'fecha_año', str(today.year))
        
        # Organismo de tránsito (por defecto)
        self._draw_text_if_coord(canvas_obj, coords, 'organismo_transito', 'RUNT')
        
        # PLACA - dividir en letras y números
        placa_raw = str(getv('placa')).upper().strip()
        if placa_raw:
            # Limpiar caracteres no alfanuméricos (ej. guiones, espacios)
            placa = ''.join(ch for ch in placa_raw if ch.isalnum())
            # Asumir siempre tres primeros caracteres como letras (AAA123 o AAA12A, motocicletas)
            if len(placa) <= 3:
                letras = placa
                numeros = ''
            else:
                letras = placa[:3]
                numeros = placa[3:]

            # Dibujo agrupado para conservar separación al ajustar por overflow
            self._draw_plate_group(canvas_obj, coords, letras, numeros)
        
        # DATOS BÁSICOS DEL VEHÍCULO
        self._draw_text_if_coord(canvas_obj, coords, 'marca', str(getv('marca')).upper())
        self._draw_text_if_coord(canvas_obj, coords, 'linea', str(getv('linea')).upper())
        self._draw_text_if_coord(canvas_obj, coords, 'color', str(getv('color')).upper())
        # Modelo puede ser largo; usar auto-ajuste sin modificar coordenadas
        self._draw_text_fit_if_coord(canvas_obj, coords, 'modelo', str(getv('modelo')), max_width=120)
        self._draw_text_if_coord(canvas_obj, coords, 'cilindrada', str(getv('cilindrada', ['cilindrada_cc'])))
        self._draw_text_if_coord(canvas_obj, coords, 'capacidad', str(getv('capacidad', ['capacidad_kg_psj'])))
        self._draw_text_if_coord(canvas_obj, coords, 'potencia', str(getv('potencia', ['potencia_hp'])))
        self._draw_text_if_coord(canvas_obj, coords, 'carroceria', str(getv('carroceria', ['tipo_carroceria'])).upper())
        
        # NÚMEROS DE IDENTIFICACIÓN DEL VEHÍCULO (con auto-ajuste para cadenas largas)
        self._draw_text_fit_if_coord(canvas_obj, coords, 'numero_motor', getv('numero_motor'), max_width=260)
        # REG Motor
        reg_motor_raw = getv('reg_numero_motor')
        reg_motor = str(reg_motor_raw).upper().strip() if reg_motor_raw and str(reg_motor_raw).lower() not in ['no disponible', 'none', ''] else ''
        logger.info(f"REG Motor valor raw: '{reg_motor_raw}' -> procesado: '{reg_motor}'")
        if reg_motor == 'N':
            self._draw_checkbox_if_coord(canvas_obj, coords, 'reg_motor_n', True, font_size=10)
            logger.info("Marcando REG Motor = N")
        elif reg_motor == 'S':
            self._draw_checkbox_if_coord(canvas_obj, coords, 'reg_motor_s', True, font_size=10)
            logger.info("Marcando REG Motor = S")
        
        self._draw_text_fit_if_coord(canvas_obj, coords, 'numero_chasis', getv('numero_chasis'), max_width=260)
        # REG Chasis
        reg_chasis_raw = getv('reg_numero_chasis')
        reg_chasis = str(reg_chasis_raw).upper().strip() if reg_chasis_raw and str(reg_chasis_raw).lower() not in ['no disponible', 'none', ''] else ''
        logger.info(f"REG Chasis valor raw: '{reg_chasis_raw}' -> procesado: '{reg_chasis}'")
        if reg_chasis == 'N':
            self._draw_checkbox_if_coord(canvas_obj, coords, 'reg_chasis_n', True, font_size=10)
            logger.info("Marcando REG Chasis = N")
        elif reg_chasis == 'S':
            self._draw_checkbox_if_coord(canvas_obj, coords, 'reg_chasis_s', True, font_size=10)
            logger.info("Marcando REG Chasis = S")
        
        self._draw_text_fit_if_coord(canvas_obj, coords, 'numero_serie', getv('numero_serie'), max_width=260)
        # REG Serie
        reg_serie_raw = getv('reg_numero_serie')
        reg_serie = str(reg_serie_raw).upper().strip() if reg_serie_raw and str(reg_serie_raw).lower() not in ['no disponible', 'none', ''] else ''
        logger.info(f"REG Serie valor raw: '{reg_serie_raw}' -> procesado: '{reg_serie}'")
        if reg_serie == 'N':
            self._draw_checkbox_if_coord(canvas_obj, coords, 'reg_serie_n', True, font_size=10)
            logger.info("Marcando REG Serie = N")
        elif reg_serie == 'S':
            self._draw_checkbox_if_coord(canvas_obj, coords, 'reg_serie_s', True, font_size=10)
            logger.info("Marcando REG Serie = S")
        
        self._draw_text_fit_if_coord(canvas_obj, coords, 'numero_vin', getv('numero_vin', ['vin']), max_width=260)
        
        # CHECKBOXES PARA COMBUSTIBLE
        combustible = str(getv('combustible')).lower()
        if 'gasolina' in combustible:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'combustible_gasolina', True)
        elif 'diesel' in combustible or 'diésel' in combustible:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'combustible_diesel', True)
        elif 'gas' in combustible:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'combustible_gas', True)
        elif 'eléctrico' in combustible or 'electrico' in combustible:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'combustible_electrico', True)
        
        # CHECKBOXES PARA CLASE DE VEHÍCULO
        clase = str(getv('clase_vehiculo')).lower()
        if 'automóvil' in clase or 'automovil' in clase or 'auto' in clase:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'clase_automovil', True)
        elif 'motocicleta' in clase or 'moto' in clase:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'clase_motocicleta', True)
        elif 'camioneta' in clase:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'clase_camioneta', True)
        elif 'camión' in clase or 'camion' in clase:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'clase_camion', True)
        elif 'bus' in clase:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'clase_bus', True)
        else:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'clase_otro', True)
        
        # CHECKBOXES PARA TIPO DE SERVICIO
        servicio = str(getv('servicio')).lower()
        if 'particular' in servicio or 'privado' in servicio:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'servicio_particular', True)
        elif 'público' in servicio or 'publico' in servicio:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'servicio_publico', True)
        elif 'oficial' in servicio:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'servicio_oficial', True)
        elif 'diplomático' in servicio or 'diplomatico' in servicio:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'servicio_diplomatico', True)
        else:
            # Por defecto marcar particular si no se especifica
            self._draw_checkbox_if_coord(canvas_obj, coords, 'servicio_particular', True)
        
        # DATOS DEL PROPIETARIO
        self._draw_text_if_coord(canvas_obj, coords, 'propietario_primer_apellido', data.get('propietario_primer_apellido', '').upper())
        self._draw_text_if_coord(canvas_obj, coords, 'propietario_segundo_apellido', data.get('propietario_segundo_apellido', '').upper())
        self._draw_text_if_coord(canvas_obj, coords, 'propietario_nombres', data.get('propietario_nombres', '').upper())

        # Documento del propietario
        propietario_documento = self._clean_document_number(data.get('propietario_documento', ''))
        self._draw_text_if_coord(canvas_obj, coords, 'propietario_documento', propietario_documento)
        self._draw_text_if_coord(canvas_obj, coords, 'propietario_direccion', data.get('propietario_direccion', ''))
        self._draw_text_if_coord(canvas_obj, coords, 'propietario_ciudad', data.get('propietario_ciudad', ''))
        self._draw_text_if_coord(canvas_obj, coords, 'propietario_telefono', data.get('propietario_telefono', ''))
        
        # Marcar tipo de documento (Propietario)
        tipo_doc = data.get('propietario_tipo_documento', '').lower()
        if 'c.c.' in tipo_doc or 'ciudadanía' in tipo_doc:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'propietario_cc', True)
        elif 'nit' in tipo_doc:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'propietario_nit', True)
        elif 'c.e.' in tipo_doc or 'extranjería' in tipo_doc:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'propietario_ce', True)
        elif 'pasaporte' in tipo_doc:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'propietario_pasaporte', True)
        else:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'propietario_otro_doc', True)

        # DATOS DEL COMPRADOR (si aplica traspaso)
        self._draw_text_if_coord(canvas_obj, coords, 'comprador_primer_apellido', data.get('comprador_primer_apellido', '').upper())
        self._draw_text_if_coord(canvas_obj, coords, 'comprador_segundo_apellido', data.get('comprador_segundo_apellido', '').upper())
        self._draw_text_if_coord(canvas_obj, coords, 'comprador_nombres', data.get('comprador_nombres', '').upper())

        # Documento del comprador
        comprador_documento = self._clean_document_number(data.get('comprador_documento', ''))
        self._draw_text_if_coord(canvas_obj, coords, 'comprador_documento', comprador_documento)
        self._draw_text_if_coord(canvas_obj, coords, 'comprador_direccion', data.get('comprador_direccion', ''))
        self._draw_text_if_coord(canvas_obj, coords, 'comprador_ciudad', data.get('comprador_ciudad', ''))
        self._draw_text_if_coord(canvas_obj, coords, 'comprador_telefono', data.get('comprador_telefono', ''))

        # Marcar tipo de documento (Comprador)
        tipo_doc_compr = data.get('comprador_tipo_documento', '').lower()
        if 'c.c.' in tipo_doc_compr or 'ciudadanía' in tipo_doc_compr:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'comprador_cc', True)
        elif 'nit' in tipo_doc_compr:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'comprador_nit', True)
        elif 'c.e.' in tipo_doc_compr or 'extranjería' in tipo_doc_compr:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'comprador_ce', True)
        elif 'pasaporte' in tipo_doc_compr:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'comprador_pasaporte', True)
        elif tipo_doc_compr:
            self._draw_checkbox_if_coord(canvas_obj, coords, 'comprador_otro_doc', True)
        
        # OBSERVACIONES
        self._draw_text_fit_if_coord(canvas_obj, coords, 'observaciones', data.get('observaciones', ''), max_width=350)

        # DATOS DE IMPORTACIÓN
        self._draw_text_if_coord(canvas_obj, coords, 'declaracion_importacion', data.get('declaracion_importacion', ''))
        
        fecha_importacion_str = str(data.get('fecha_importacion', ''))
        if fecha_importacion_str:
            try:
                # Reemplazar separadores comunes y dividir
                parts = fecha_importacion_str.replace('/', '-').split('-')
                if len(parts) == 3:
                    # Asumir formato AAAA-MM-DD o DD-MM-AAAA
                    if len(parts[0]) == 4:
                        ano, mes, dia = parts[0], parts[1], parts[2]
                    else:
                        dia, mes, ano = parts[0], parts[1], parts[2]
                    
                    self._draw_text_if_coord(canvas_obj, coords, 'importacion_dia', dia)
                    self._draw_text_if_coord(canvas_obj, coords, 'importacion_mes', mes)
                    self._draw_text_if_coord(canvas_obj, coords, 'importacion_ano', ano) # Año completo
            except Exception as e:
                logger.error(f"No se pudo procesar la fecha de importación '{fecha_importacion_str}': {e}")
        
        logger.info(f"Formulario de trámite completado con {len([k for k in coords.keys() if 'propietario' in k or 'vehiculo' in k])} campos")

    def _draw_text_fit_if_coord(self, canvas_obj, coords, field_name, text, max_width=160):
        """Dibujar texto que se ajuste al ancho máximo reduciendo el tamaño de fuente si es necesario y evitando desbordes a la derecha."""
        if field_name in coords and text and str(text).strip():
            x, y = coords[field_name]
            text_str = str(text).strip()
            page_w, _ = canvas_obj._pagesize
            # Probar tamaños de fuente decrecientes para encajar
            for size in [9, 8, 7, 6]:
                try:
                    canvas_obj.setFont(self.default_font, size)
                    from reportlab.pdfbase import pdfmetrics
                    width = pdfmetrics.stringWidth(text_str, self.default_font, size)
                    if width <= max_width:
                        # Evitar desborde a la derecha de la página
                        x_draw = x
                        overflow = (x + width) - (page_w - 2)
                        if overflow > 0:
                            x_draw = max(2, x - overflow)
                        canvas_obj.drawString(x_draw, y, text_str)
                        logger.debug(f"Texto (fit) dibujado en {field_name} ({x_draw}, {y}) size={size}: {text_str}")
                        # Restaurar tamaño por defecto para otros campos
                        canvas_obj.setFont(self.default_font, 9)
                        return
                except Exception:
                    # Si falla cálculo, intentar dibujar en tamaño por defecto
                    pass
            # Si no cupo, truncar conservando final (por identificadores)
            trunc = text_str[-30:]
            canvas_obj.setFont(self.default_font, 6)
            # Evitar desborde cuando se trunca también
            try:
                from reportlab.pdfbase import pdfmetrics
                width_t = pdfmetrics.stringWidth(trunc, self.default_font, 6)
                x = max(2, min(x, (page_w - 2) - width_t))
            except Exception:
                pass
            canvas_obj.drawString(x, y, trunc)
            canvas_obj.setFont(self.default_font, 9)
            logger.debug(f"Texto (fit-trunc) dibujado en {field_name} ({x}, {y}): {trunc}")
    
    def _name_to_nombres_apellidos(self, full_name: str) -> str:
        """Reordenar un nombre posiblemente capturado como 'Apellidos Nombres' a 'Nombres Apellidos'.
        Heurística simple:
        - Si hay coma: 'Apellidos, Nombres' -> 'Nombres Apellidos'.
        - 2 tokens: asumir 'Apellido Nombre' -> 'Nombre Apellido'.
        - >=3 tokens: asumir dos primeros son apellidos y el resto nombres -> 'Nombres Apellidos'.
        Mantiene conectores como 'DE', 'DEL', 'LA', etc. con el token original.
        """
        if not full_name:
            return ''
        s = ' '.join(str(full_name).split())  # normalizar espacios
        # Caso con coma
        if ',' in s:
            parts = [p.strip() for p in s.split(',', 1)]
            ap = parts[0]
            no = parts[1]
            return f"{no} {ap}".strip()
        tokens = s.split(' ')
        if len(tokens) == 1:
            return s
        if len(tokens) == 2:
            ap, no = tokens[0], tokens[1]
            return f"{no} {ap}".strip()
        # Heurística para >=3 tokens
        # Conectores usuales que pueden pertenecer a apellidos compuestos
        connectors = {"DE", "DEL", "LA", "LAS", "LOS", "SAN", "SANTA"}
        up_tokens = [t.upper() for t in tokens]
        # Tomar los dos primeros como base de apellidos
        apellidos_end = 2
        # Extender apellidos si el tercer token es conector (casos como "PEREZ DE LA")
        while apellidos_end < len(tokens) and up_tokens[apellidos_end] in connectors:
            apellidos_end += 1
        apellidos = ' '.join(tokens[:apellidos_end])
        nombres = ' '.join(tokens[apellidos_end:])
        # Si por alguna razón nombres quedó vacío, no reordenar agresivamente
        if not nombres.strip():
            return s
        return f"{nombres} {apellidos}".strip()
    
    def _fill_contrato_compraventa_improved(self, canvas_obj, data, coords):
        """Rellenar contrato de compraventa con mapeo mejorado"""
        vehiculo = data.get('vehiculo', {})
        vendedor = data.get('vendedor', {})
        comprador = data.get('comprador', {})
        valor_venta = data.get('valor_venta')
        
        logger.info(f"Rellenando contrato de compraventa - Vendedor: {vendedor.get('nombre', 'N/A')}")
        fs = 10  # tamaño de fuente ligeramente mayor
        
        # DATOS DEL VENDEDOR
        vendedor_nombre = self._name_to_nombres_apellidos(vendedor.get('nombre', ''))
        self._draw_text_if_coord(canvas_obj, coords, 'vendedor_nombre', vendedor_nombre.upper(), font_size=fs)
        self._draw_text_if_coord(canvas_obj, coords, 'vendedor_ciudad', vendedor.get('ciudad', '').upper(), font_size=fs)
        
        # DATOS DEL COMPRADOR (sin voltear, vienen del formulario)
        self._draw_text_if_coord(canvas_obj, coords, 'comprador_nombre', comprador.get('nombre', '').upper(), font_size=fs)
        self._draw_text_if_coord(canvas_obj, coords, 'comprador_ciudad', comprador.get('ciudad', '').upper(), font_size=fs)
        
        # IDENTIFICACIÓN DEL VEHÍCULO
        clase_vehiculo = vehiculo.get('clase_vehiculo', '')
        if not clase_vehiculo:
            # Inferir de otros campos si no está disponible
            if vehiculo.get('tipo_carroceria'):
                clase_vehiculo = vehiculo.get('tipo_carroceria', '')
        self._draw_text_if_coord(canvas_obj, coords, 'vehiculo_tipo', clase_vehiculo.upper(), font_size=fs)
        
        # DATOS ESPECÍFICOS DEL VEHÍCULO
        self._draw_text_if_coord(canvas_obj, coords, 'marca', vehiculo.get('marca', '').upper(), font_size=fs)
        self._draw_text_if_coord(canvas_obj, coords, 'linea', vehiculo.get('linea', '').upper(), font_size=fs)
        self._draw_text_if_coord(canvas_obj, coords, 'placa', vehiculo.get('placa', '').upper(), font_size=fs)
        self._draw_text_if_coord(canvas_obj, coords, 'modelo', str(vehiculo.get('modelo', '')), font_size=fs)
        self._draw_text_if_coord(canvas_obj, coords, 'motor', vehiculo.get('numero_motor', ''), font_size=fs)
        self._draw_text_if_coord(canvas_obj, coords, 'chasis', vehiculo.get('numero_chasis', ''), font_size=fs)
        self._draw_text_if_coord(canvas_obj, coords, 'color', vehiculo.get('color', '').upper(), font_size=fs)
        
        # MATRICULADO EN (organismo de tránsito)
        organismo = data.get('organismo_transito', '').upper()
        self._draw_text_if_coord(canvas_obj, coords, 'matriculado_en', organismo, font_size=fs)
        
        self._draw_text_if_coord(canvas_obj, coords, 'vin', vehiculo.get('vin', ''), font_size=fs)
        self._draw_text_if_coord(canvas_obj, coords, 'serie', vehiculo.get('numero_serie', ''), font_size=fs)
        
        # VALOR DE LA VENTA
        if valor_venta:
            precio_formateado = f"${valor_venta:,.0f}"
            self._draw_text_if_coord(canvas_obj, coords, 'precio_numeros', precio_formateado, font_size=fs)
            
            # Convertir a letras (implementación básica)
            precio_letras = self._number_to_words_basic(valor_venta)
            self._draw_text_if_coord(canvas_obj, coords, 'precio_letras', precio_letras, font_size=fs)
        
        # FORMA DE PAGO
        self._draw_text_if_coord(canvas_obj, coords, 'forma_pago', data.get('forma_pago', ''), font_size=fs)

        # CIUDAD Y FECHA DEL CONTRATO
        # Usar ciudad_contrato del formulario, sin fallback automático
        ciudad_cv = data.get('ciudad_contrato', '').upper()
        self._draw_text_if_coord(canvas_obj, coords, 'ciudad_contrato', ciudad_cv, font_size=fs)

        # FECHA DEL CONTRATO
        # Usar fecha del formulario si está disponible, sino fecha actual
        fecha_contrato = data.get('fecha_contrato')
        if fecha_contrato:
            if isinstance(fecha_contrato, str):
                from datetime import datetime as dt
                try:
                    fecha_obj = dt.fromisoformat(fecha_contrato)
                except:
                    fecha_obj = datetime.now()
            else:
                fecha_obj = fecha_contrato
        else:
            fecha_obj = datetime.now()
        
        today = fecha_obj
        self._draw_text_if_coord(canvas_obj, coords, 'dia_contrato', str(today.day), font_size=fs)
        
        meses_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                   "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        mes_nombre = meses_es[today.month - 1]
        self._draw_text_if_coord(canvas_obj, coords, 'mes_contrato', mes_nombre, font_size=fs)
        self._draw_text_if_coord(canvas_obj, coords, 'año_contrato', str(today.year), font_size=fs)
        
        # DATOS PARA FIRMAS
        # Mostrar solo los datos sin prefijos
        vendedor_doc = self._clean_document_number(vendedor.get('documento', ''))
        self._draw_text_if_coord(canvas_obj, coords, 'vendedor_doc_firma', vendedor_doc, font_size=fs)
        self._draw_text_if_coord(canvas_obj, coords, 'vendedor_dir_firma', vendedor.get('direccion', ''), font_size=fs)
        self._draw_text_if_coord(canvas_obj, coords, 'vendedor_tel_firma', vendedor.get('telefono', ''), font_size=fs)
        
        comprador_doc = self._clean_document_number(comprador.get('documento', ''))
        self._draw_text_if_coord(canvas_obj, coords, 'comprador_doc_firma', comprador_doc, font_size=fs)
        self._draw_text_if_coord(canvas_obj, coords, 'comprador_dir_firma', comprador.get('direccion', ''), font_size=fs)
        self._draw_text_if_coord(canvas_obj, coords, 'comprador_tel_firma', comprador.get('telefono', ''), font_size=fs)
        
        logger.info("Contrato de compraventa completado")
    
    def _fill_contrato_mandato_improved(self, canvas_obj, data, coords):
        """Rellenar contrato de mandato con mapeo mejorado"""
        vehiculo = data.get('vehiculo', {})
        mandante = data.get('mandante', {})
        mandatario = data.get('mandatario', {})

        # Limpiar números de documento
        mandante_documento = self._clean_document_number(mandante.get('documento', ''))
        mandatario_documento = self._clean_document_number(mandatario.get('documento', ''))

        logger.info(f"Rellenando contrato de mandato - Mandante: {mandante.get('nombre', 'N/A')}")
        logger.info(f"Datos completos del mandante: {mandante}")
        logger.info(f"Datos completos del mandatario: {mandatario}")
        logger.info(f"Datos completos del vehículo: {vehiculo}")
        logger.info(f"Todos los datos recibidos: {data}")
        fs = 11  # tamaño de fuente ligeramente mayor
        
        # Usar los datos limpios en el PDF
        self._draw_text_if_coord(canvas_obj, coords, 'mandante_documento', mandante_documento, font_size=fs)
        self._draw_text_if_coord(canvas_obj, coords, 'mandatario_documento', mandatario_documento, font_size=fs)
        
        # DATOS DEL MANDANTE
        mandante_nombre = self._name_to_nombres_apellidos(mandante.get('nombre', ''))
        self._draw_text_if_coord(canvas_obj, coords, 'mandante_nombre', mandante_nombre.upper(), font_size=fs)
        self._draw_text_if_coord(canvas_obj, coords, 'mandante_ciudad', mandante.get('ciudad', '').upper(), font_size=fs)
        
        
        # DATOS DEL MANDATARIO (sin voltear, vienen del formulario)
        self._draw_text_if_coord(canvas_obj, coords, 'mandatario_nombre', mandatario.get('nombre', '').upper(), font_size=fs)
        
        
        
        # TRÁMITES AUTORIZADOS
        tramites = data.get('tramites_autorizados', 'Matricula, registro, traspaso, cambio de propietario y demás trámites vehiculares')
        self._draw_text_if_coord(canvas_obj, coords, 'tramites_autorizados', tramites, font_size=fs)
        
        # DATOS DEL VEHÍCULO
        placa = vehiculo.get('placa', data.get('placa', '')).upper()
        self._draw_text_if_coord(canvas_obj, coords, 'vehiculo_placa', placa, font_size=fs)
        
        # ORGANISMO DE TRÁNSITO
        organismo = data.get('organismo_transito', 'RUNT')
        self._draw_text_if_coord(canvas_obj, coords, 'organismo_transito', organismo, font_size=fs)
        
        # FECHA Y LUGAR DEL CONTRATO
        ciudad_contrato = data.get('ciudad_contrato', mandante.get('ciudad', 'BOGOTÁ')).upper()
        self._draw_text_if_coord(canvas_obj, coords, 'ciudad_contrato', ciudad_contrato, font_size=fs)
        
        # Usar fecha del formulario o fecha actual
        fecha_contrato = data.get('fecha_contrato')
        if fecha_contrato:
            if isinstance(fecha_contrato, str):
                try:
                    fecha_contrato = datetime.strptime(fecha_contrato, '%Y-%m-%d')
                except (ValueError, TypeError):
                    fecha_contrato = datetime.now()
        else:
            fecha_contrato = datetime.now()
            
        self._draw_text_if_coord(canvas_obj, coords, 'dia_contrato', str(fecha_contrato.day), font_size=fs)
        
        meses_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                   "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        mes_nombre = meses_es[fecha_contrato.month - 1]
        self._draw_text_if_coord(canvas_obj, coords, 'mes_contrato', mes_nombre, font_size=fs)
        self._draw_text_if_coord(canvas_obj, coords, 'año_contrato', str(fecha_contrato.year), font_size=fs)
        
        logger.info("Contrato de mandato completado")
    
    def _draw_text_if_coord(self, canvas_obj, coords, field_name, text, font_size=9):
        """Dibujar texto solo si existe la coordenada para ese campo, evitando desbordar el ancho de página."""
        if field_name in coords and text and str(text).strip():
            x, y = coords[field_name]
            # Convertir a mayúsculas y truncar texto muy largo
            text_str = str(text).strip().upper()[:50]  # Máximo 50 caracteres en MAYÚSCULAS
            # Medir y ajustar si se sale del ancho de la página
            try:
                from reportlab.pdfbase import pdfmetrics
                page_w, _ = canvas_obj._pagesize
                canvas_obj.setFont(self.default_font, font_size)
                width = pdfmetrics.stringWidth(text_str, self.default_font, font_size)
                overflow = (x + width) - (page_w - 2)
                if overflow > 0:
                    x = max(2, x - overflow)
            except Exception:
                pass
            canvas_obj.drawString(x, y, text_str)
            logger.debug(f"Texto dibujado en {field_name} ({x}, {y}) size={font_size}: {text_str}")
    
    def _draw_checkbox_if_coord(self, canvas_obj, coords, field_name, checked=False, font_size=9):
        """Dibujar checkbox solo si existe la coordenada"""
        if field_name in coords and checked:
            x, y = coords[field_name]
            # Limitar a la página actual del canvas
            try:
                page_w, page_h = canvas_obj._pagesize
                x = max(10, min(x, page_w - 10))
                y = max(10, min(y, page_h - 10))
            except Exception:
                pass
            # Establecer fuente y tamaño para la X
            canvas_obj.setFont(self.default_font, font_size)
            canvas_obj.drawString(x, y, "X")
            logger.info(f"Checkbox marcado en {field_name} ({x}, {y}) con tamaño {font_size}")

    def _draw_plate_group(self, canvas_obj, coords, letras, numeros):
        """Dibuja placa letras y números preservando el espaciado relativo, evitando superposición al ajustar por borde derecho."""
        try:
            if 'placa_letras' not in coords or 'placa_numeros' not in coords:
                # Fallback a dibujo simple
                self._draw_text_if_coord(canvas_obj, coords, 'placa_letras', letras)
                self._draw_text_if_coord(canvas_obj, coords, 'placa_numeros', numeros)
                return

            xL, yL = coords['placa_letras']
            xN, yN = coords['placa_numeros']
            # Medidas con fuente estándar
            from reportlab.pdfbase import pdfmetrics
            page_w, _ = canvas_obj._pagesize
            canvas_obj.setFont(self.default_font, 9)
            wL = pdfmetrics.stringWidth(str(letras), self.default_font, 9)
            wN = pdfmetrics.stringWidth(str(numeros), self.default_font, 9)
            # Asegura un gap mínimo entre letras y números para evitar superposición visual
            min_gap = 10  # puntos (aumentado ligeramente)
            xL_draw = xL
            # forzar que números empiecen al menos después del ancho de letras + gap
            xN_draw = max(xN, xL_draw + wL + min_gap)
            # Calcula overflow tomando el borde más a la derecha ya con gap aplicado
            right_edge = max(xL_draw + wL, xN_draw + wN)
            overflow = right_edge - (page_w - 2)
            if overflow > 0:
                xL_draw -= overflow
                xN_draw -= overflow
            # Dibuja
            canvas_obj.drawString(xL_draw, yL, str(letras))
            canvas_obj.drawString(xN_draw, yN, str(numeros))
            logger.debug(f"Placa dibujada agrupada: letras ({xL_draw},{yL})='{letras}', numeros ({xN_draw},{yN})='{numeros}'")
        except Exception as e:
            logger.warning(f"Fallo dibujo agrupado de placa, usando fallback: {e}")
            self._draw_text_if_coord(canvas_obj, coords, 'placa_letras', letras)
            self._draw_text_if_coord(canvas_obj, coords, 'placa_numeros', numeros)

    def _clamp_coords(self, xy):
        """Asegura que las coordenadas estén dentro de la página carta (612x792)."""
        try:
            x, y = xy
            page_w, page_h = letter
            # Margen de seguridad 10pt
            x = max(10, min(x, page_w - 10))
            y = max(10, min(y, page_h - 10))
            return (x, y)
        except Exception:
            return xy
    
    def _number_to_words_basic(self, number):
        """Conversión completa de números a palabras en español sin dígitos"""
        try:
            if not number or number < 0:
                return "CERO PESOS"
                
            # Convertir a entero para evitar decimales
            number = int(round(number))
            
            unidades = ['', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE']
            decenas = ['', 'DIEZ', 'VEINTE', 'TREINTA', 'CUARENTA', 'CINCUENTA', 
                      'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA']
            especiales = ['DIEZ', 'ONCE', 'DOCE', 'TRECE', 'CATORCE', 'QUINCE', 
                        'DIECISEIS', 'DIECISIETE', 'DIECIOCHO', 'DIECINUEVE', 'VEINTE']
            
            def convert_less_than_hundred(n):
                if n <= 0:
                    return ''
                if n < 10:
                    return unidades[n]
                if 10 <= n <= 20:
                    return especiales[n-10]
                if n < 30:
                    return 'VEINTI' + unidades[n%10] if n%10 != 0 else 'VEINTE'
                return decenas[n//10] + (' Y ' + unidades[n%10] if n%10 != 0 else '')
            
            def convert_less_than_thousand(n):
                if n < 100:
                    return convert_less_than_hundred(n)
                centenas = n // 100
                resto = n % 100
                if centenas == 1:
                    return 'CIEN' if resto == 0 else 'CIENTO ' + convert_less_than_hundred(resto)
                if centenas == 5:
                    return 'QUINIENTOS ' + convert_less_than_hundred(resto) if resto > 0 else 'QUINIENTOS'
                if centenas == 7:
                    return 'SETECIENTOS ' + convert_less_than_hundred(resto) if resto > 0 else 'SETECIENTOS'
                if centenas == 9:
                    return 'NOVECIENTOS ' + convert_less_than_hundred(resto) if resto > 0 else 'NOVECIENTOS'
                if centenas == 1:
                    return 'CIENTO ' + convert_less_than_hundred(resto)
                return (unidades[centenas] + 'CIENTOS ' + convert_less_than_hundred(resto)).strip()
            
            if number == 0:
                return 'CERO PESOS'
                
            # Procesar millones
            millones = number // 1000000
            resto = number % 1000000
            
            # Procesar miles
            miles = resto // 1000
            resto = resto % 1000
            
            resultado = ''
            
            if millones > 0:
                if millones == 1:
                    resultado += 'UN MILLON '
                else:
                    resultado += convert_less_than_thousand(millones) + ' MILLONES '
            
            if miles > 0:
                if miles == 1:
                    resultado += 'MIL '
                else:
                    resultado += convert_less_than_thousand(miles) + ' MIL '
            
            if resto > 0 or (millones == 0 and miles == 0):
                resultado += convert_less_than_thousand(resto) + ' '
            
            return (resultado).strip()
            
        except Exception as e:
            logger.warning(f"Error convirtiendo número a palabras: {e}")
            return "VALOR EN PESOS"
    
    def _validate_form_data(self, template_type, data):
        """Validar que los datos del formulario contengan los campos requeridos."""
        if template_type not in self.required_fields:
            logger.error(f"No hay reglas de validación para el tipo de formulario: {template_type}")
            return False, "Tipo de formulario no soportado para validación"

        required = self.required_fields[template_type]
        errors = []

        if isinstance(required, dict):
            # Lógica para estructuras anidadas (compraventa, mandato)
            for main_key, fields in required.items():
                if main_key not in data:
                    errors.append(f"Falta la sección principal de datos: '{main_key}'")
                    continue
                
                if fields is None:  # Para campos que no son diccionarios, como 'valor_venta'
                    if not data.get(main_key):
                        errors.append(f"Falta el campo requerido: '{main_key}'")
                    continue

                for field in fields:
                    if field not in data[main_key] or not data[main_key].get(field):
                        errors.append(f"Falta el dato '{field}' en la sección '{main_key}'")
        else:
            # Lógica para estructuras planas (formulario_tramite)
            for field in required:
                if field not in data or not data.get(field):
                    errors.append(f"Falta el dato requerido: '{field}'")

        if errors:
            error_message = ", ".join(errors)
            logger.error(f"Errores de validación de datos para {template_type}: {error_message}")
            return False, error_message
        
        logger.info(f"Validación de datos exitosa para {template_type}")
        return True, "Validación exitosa"

    def fill_pdf_form(self, template_type, data, output_path):
        """
        Rellenar un formulario PDF usando plantilla oficial con mapeo mejorado
        
        Args:
            template_type (str): Tipo de plantilla ('formulario_tramite', 'contrato_compraventa', 'contrato_mandato')
            data (dict): Diccionario con los datos a rellenar en el formulario
            output_path (str): Ruta donde se guardará el PDF generado
            
        Returns:
            bool: True si el PDF se generó correctamente, False en caso contrario
        """
        try:
            # Validar el tipo de formulario
            if template_type not in self.field_coordinates:
                logger.error(f"Tipo de formulario no soportado: {template_type}")
                return False
                
            # Validar datos de entrada
            is_valid, error_message = self._validate_form_data(template_type, data)
            if not is_valid:
                logger.error(f"La validación de datos falló: {error_message}")
                return False
                
            # Obtener la ruta de la plantilla
            template_path = self.get_template_path(template_type)
            if not template_path or not os.path.exists(template_path):
                logger.error(f"Plantilla no encontrada: {template_path}")
                return False
            
            logger.info(f"Procesando formulario {template_type}...")
            
            # Crear overlay con los datos
            overlay = self.create_overlay(data, template_type)
            if not overlay:
                logger.error("No se pudo crear el overlay del formulario")
                return False
            
            # Leer la plantilla original
            try:
                template_pdf = PdfReader(open(template_path, 'rb'))
                overlay_pdf = PdfReader(overlay)
            except Exception as e:
                logger.error(f"Error al leer archivos PDF: {str(e)}")
                return False
            
            # Verificar que la plantilla tenga páginas
            if not template_pdf.pages:
                logger.error(f"La plantilla {template_path} no contiene páginas")
                return False
            
            # Crear el PDF de salida
            output_pdf = PdfWriter()
            
            # Combinar cada página de la plantilla con el overlay
            for i, page in enumerate(template_pdf.pages):
                # Si hay overlay para esta página, combinarlo
                if i < len(overlay_pdf.pages):
                    page.merge_page(overlay_pdf.pages[i])
                    logger.debug(f"Página {i+1} combinada con overlay")
                
                output_pdf.add_page(page)
            
            # Asegurar que el directorio de salida existe
            try:
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            except Exception as e:
                logger.error(f"Error al crear directorio de salida: {str(e)}")
                return False
            
            # Guardar el resultado
            try:
                with open(output_path, 'wb') as output_file:
                    output_pdf.write(output_file)
                    
                # Verificar que el archivo se creó correctamente
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f"PDF generado exitosamente: {output_path} ({os.path.getsize(output_path)} bytes)")
                    return True
                else:
                    logger.error(f"El archivo de salida no se creó correctamente: {output_path}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error al guardar el archivo PDF: {str(e)}")
                return False
            
        except Exception as e:
            logger.error(f"Error inesperado al rellenar el PDF: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

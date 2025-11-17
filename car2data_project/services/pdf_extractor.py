import os
import base64
import json
import logging
import re
import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)

class PDFExtractor:
    """
    Servicio para extraer información de PDFs de tarjeta de propiedad usando únicamente Gemini Vision
    """
    
    def __init__(self):
        # Usar la configuración de Django
        self.api_key = getattr(settings, 'GEMINI_API_KEY', '')
        if not self.api_key:
            logger.error("La clave de API de Gemini no está configurada en los ajustes")
            raise ValueError("La clave de API de Gemini no está configurada en los ajustes")
        # Configurar Gemini
        try:
            # Configurar con la API key
            genai.configure(api_key=self.api_key)
            
            # Permitir configurar el modelo por variable de entorno; default a un modelo estable
            model_name = os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash')
            try:
                self.model = genai.GenerativeModel(model_name)
            except Exception:
                # Algunos clientes requieren prefijo 'models/'
                alt_name = f"models/{model_name}" if not model_name.startswith("models/") else model_name
                try:
                    self.model = genai.GenerativeModel(alt_name)
                    model_name = alt_name
                except Exception:
                    # Fallback a un modelo conocido compatible
                    fallback = 'gemini-2.0-flash'
                    self.model = genai.GenerativeModel(fallback)
                    model_name = fallback
            logger.info(f"Gemini configurado correctamente con {model_name}")
                
        except Exception as e:
            logger.error(f"Error en la respuesta de Gemini: {str(e)}")
            raise Exception(f"Error al procesar el documento con la inteligencia artificial: {str(e)}")
        
        # Prompt especializado para tarjeta de propiedad
        self.base_prompt = """
        
        Eres un experto en análisis de documentos vehiculares colombianos. Analiza el siguiente documento PDF
        y extrae ÚNICAMENTE la información que esté explícitamente mencionada en la tarjeta de propiedad.

        ⚠️ Reglas:
        - Si un dato no aparece, responde exactamente "No disponible"
        - Devuelve SOLO un JSON válido, sin explicaciones ni texto adicional
        - No inventes información, solo toma lo que esté en el documento

        Formato de salida esperado:

        {
            "tipo_documento": "Debe ser 'Tarjeta de Propiedad' o similar si se identifica",
            "informacion_vehiculo": {
                "placa": "Es el identificador único de un vehículo, generalmente compuesto por letras y números, asignado por la autoridad de tránsito",
                "marca": "Nombre del fabricante del vehículo, como CHEVROLET, Toyota, Ford, etc.",
                "linea": "Subdivisión de una marca que agrupa vehículos con características similares, por ejemplo, la línea SAIL.",
                "modelo": "Año en que el vehículo fue fabricado.",
                "cilindrada_cc": "El volumen total en centímetros cúbicos (cc) de los cilindros del motor.",
                "color": "El color principal de la carrocería del vehículo.",
                "clase_vehiculo": "Clasificación general del tipo de vehículo, como automóvil, motocicleta, camión, etc.",
                "tipo_carroceria": "Se refiere a la estructura principal y forma del vehículo, por ejemplo, SEDAN, hatchback, SUV, etc.",
                "numero_motor": "Identificador alfanumérico único grabado en el motor.",
                "reg_numero_motor": "Campo REG asociado a número de motor. Devuelve solo 'S' (sí) o 'N' (no).",
                "servicio": "Indica el uso que se le da al vehículo, como particular, público, diplomático, etc.",
                "combustible": "El tipo de carburante que utiliza el motor, como gasolina, diésel, o eléctrico.",
                "capacidad_kg_psj": "La capacidad de carga del vehículo, expresada en kilogramos (Kg) o el número de pasajeros (PSJ) que puede transportar.",
                "vin": "Es un código de identificación único mundialmente para cada vehículo automotor.",
                "numero_serie": "Identificador único del vehículo que se usa para su seguimiento y registro.",
                "reg_numero_serie": "Campo REG asociado a número de serie. Devuelve solo 'S' (sí) o 'N' (no).",
                "numero_chasis": "Identificador único del vehículo que se usa para su seguimiento y registro.",
                "reg_numero_chasis": "Campo REG asociado a número de chasis. Devuelve solo 'S' (sí) o 'N' (no).",
                "potencia_hp": "La potencia del motor expresada en caballos de fuerza (HP).",
                "puertas": "El número de puertas que tiene el vehículo."
            },
            "informacion_propietario": {
                "nombre": "Nombre(s) y apellido(s) de la persona o entidad legal propietaria del vehículo.",
                "identificacion": "El número de documento de identidad del propietario, como una cédula de ciudadanía (C.C.).",
                "direccion": "La dirección de residencia del propietario del vehículo.",
                "telefono": "El número de teléfono de contacto del propietario del vehículo.",
                "ciudad": "La ciudad de residencia del propietario del vehículo."
            },
            "detalles_registro": {
                "licencia_transito_numero": "El número único de la licencia de tránsito del vehículo.",
                "declaracion_importacion": "Código o número que identifica el documento aduanero que valida la entrada legal del vehículo al país.",
                "fecha_importacion": "La fecha en que se realizó la declaración de importación del vehículo.",
                "fecha_matricula": "La fecha en que el vehículo fue registrado por primera vez ante la autoridad de tránsito.",
                "fecha_expedicion_licencia": "Fecha en que se emitió el documento de la licencia de tránsito.",
                "organismo_transito": "La entidad u oficina de tránsito responsable de expedir la matrícula y la licencia."
            },
            "restricciones_limitaciones": {
                "restriccion_movilidad": "Indica si el vehículo tiene alguna limitación para circular, a menudo relacionada con normas ambientales o de seguridad.",
                "blindaje": "Se refiere al nivel de protección balística del vehículo.",
                "limitacion_propiedad": "Indica si el vehículo tiene alguna restricción legal, como un embargo, prenda o algún tipo de gravamen."
            }
        }

        Documento a analizar:
        """

    def _analyze_with_vision(self, pdf_path: str) -> dict:
        """Analiza el PDF directamente con Gemini Vision"""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_data = file.read()
                pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
            
            content = [
                self.base_prompt,
                {
                    "mime_type": "application/pdf",
                    "data": pdf_base64
                }
            ]
            
            response = self.model.generate_content(content)
            
            if response and response.text:
                logger.info("Análisis con Vision completado")
                return self.clean_and_parse_json(response.text)
            else:
                return self.create_default_structure("Sin respuesta de Vision")
                
        except Exception as e:
            logger.error(f"Error en análisis con Vision: {str(e)}")
            return self.create_default_structure(f"Error en Vision: {str(e)}")
    
    def clean_and_parse_json(self, response_text: str) -> dict:
        """Limpia y parsea la respuesta JSON de Gemini"""
        try:
            cleaned_text = response_text.strip()
            json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
            else:
                logger.warning("No se encontró JSON válido en la respuesta")
                return self.create_default_structure(response_text)
                
        except json.JSONDecodeError as e:
            logger.error(f"Error al leer el archivo PDF: {str(e)}")
            raise Exception(f"No se pudo leer el archivo PDF: {str(e)}")
    
    def create_default_structure(self, raw_response: str = "") -> dict:
        """Crea una estructura JSON por defecto"""
        return {
            "tipo_documento": "No identificado",
            "informacion_vehiculo": {
                "placa": "No disponible",
                "marca": "No disponible",
                "linea": "No disponible",
                "modelo": "No disponible",
                "cilindrada_cc": "No disponible",
                "color": "No disponible",
                "clase_vehiculo": "No disponible",
                "tipo_carroceria": "No disponible",
                "numero_motor": "No disponible",
                "reg_numero_motor": "No disponible",
                "servicio": "No disponible",
                "combustible": "No disponible",
                "capacidad_kg_psj": "No disponible",
                "vin": "No disponible",
                "numero_serie": "No disponible",
                "reg_numero_serie": "No disponible",
                "numero_chasis": "No disponible",
                "reg_numero_chasis": "No disponible",
                "potencia_hp": "No disponible",
                "puertas": "No disponible"
            },
            "informacion_propietario": {
                "nombre": "No disponible",
                "identificacion": "No disponible",
                "direccion": "No disponible",
                "telefono": "No disponible",
                "ciudad": "No disponible"
            },
            "detalles_registro": {
                "licencia_transito_numero": "No disponible",
                "declaracion_importacion": "No disponible",
                "fecha_importacion": "No disponible",
                "fecha_matricula": "No disponible",
                "fecha_expedicion_licencia": "No disponible",
                "organismo_transito": "No disponible"
            },
            "restricciones_limitaciones": {
                "restriccion_movilidad": "No disponible",
                "blindaje": "No disponible",
                "limitacion_propiedad": "No disponible"
            },
            "observaciones": f"Respuesta original: {raw_response[:300]}..."
        }
    
    def extract_vehicle_info(self, pdf_path: str) -> dict:
        """Extrae información vehicular de un PDF usando Gemini Vision"""
        logger.info(f"Iniciando análisis de PDF con Gemini Vision: {pdf_path}")
        return self._analyze_with_vision(pdf_path)
    
    def test_connection(self) -> bool:
        """Prueba la conexión con Gemini. En caso de 429 (cuota), devuelve False sin lanzar excepción."""
        try:
            test_prompt = "Responde con un JSON simple: {\"test\": \"ok\"}"
            response = self.model.generate_content(test_prompt)
            return bool(response and response.text)
        except Exception as e:
            # Manejo explícito de errores de cuota (429)
            try:
                from google.api_core.exceptions import ResourceExhausted
                if isinstance(e, ResourceExhausted):
                    logger.warning("Cuota de Gemini agotada (429). test_connection devuelve False.")
                    return False
            except Exception:
                pass
            logger.error(f"Error en test_connection: {str(e)}")
            return False

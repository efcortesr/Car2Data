from django.db import models
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
import json


class Document(models.Model):
    DOCUMENT_TYPES = [
        ('ownership', 'Tarjeta de Propiedad'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('error', 'Error'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES, default='unknown')
    file = models.FileField(upload_to='uploads/pdfs/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    # Campos para información extraída por Gemini
    extracted_data_json = models.TextField(blank=True, null=True)
    extraction_error = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} - {self.user.username}"

    @property
    def safe_file_size(self):
        """Devuelve el tamaño del archivo en bytes o None si el archivo no existe."""
        try:
            if self.file and self.file.name and default_storage.exists(self.file.name):
                return self.file.size
        except (FileNotFoundError, OSError, ValueError):
            return None
        return None

    def get_extracted_data(self):
        """Retorna los datos extraídos como diccionario"""
        if self.extracted_data_json:
            try:
                return json.loads(self.extracted_data_json)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_extracted_data(self, data_dict):
        """Guarda los datos extraídos como JSON"""
        self.extracted_data_json = json.dumps(data_dict, ensure_ascii=False, indent=2)
        self.save()

    def get_structured_data(self):
        """
        Retorna los datos extraídos en un formato estructurado para autodiligenciado
        """
        if not self.extracted_data_json:
            return {}

        try:
            data = json.loads(self.extracted_data_json)

            # Crear diccionario de información del vehículo
            info_vehiculo = {
                'placa': self.safe_get(data, ['informacion_vehiculo', 'placa']),
                'marca': self.safe_get(data, ['informacion_vehiculo', 'marca']),
                'linea': self.safe_get(data, ['informacion_vehiculo', 'linea']),
                'modelo': self.safe_get(data, ['informacion_vehiculo', 'modelo']),
                'color': self.safe_get(data, ['informacion_vehiculo', 'color']),
                'vin': self.safe_get(data, ['informacion_vehiculo', 'vin']),
                'numero_motor': self.safe_get(data, ['informacion_vehiculo', 'numero_motor']),
                'reg_numero_motor': self.safe_get(data, ['informacion_vehiculo', 'reg_numero_motor']),
                'numero_chasis': self.safe_get(data, ['informacion_vehiculo', 'numero_chasis']),
                'reg_numero_chasis': self.safe_get(data, ['informacion_vehiculo', 'reg_numero_chasis']),
                'numero_serie': self.safe_get(data, ['informacion_vehiculo', 'numero_serie']),
                'reg_numero_serie': self.safe_get(data, ['informacion_vehiculo', 'reg_numero_serie']),
                'cilindrada_cc': self.safe_get(data, ['informacion_vehiculo', 'cilindrada_cc']),
                'combustible': self.safe_get(data, ['informacion_vehiculo', 'combustible']),
                'servicio': self.safe_get(data, ['informacion_vehiculo', 'servicio']),
                'clase_vehiculo': self.safe_get(data, ['informacion_vehiculo', 'clase_vehiculo']),
                'tipo_carroceria': self.safe_get(data, ['informacion_vehiculo', 'tipo_carroceria']),
                'capacidad_kg_psj': self.safe_get(data, ['informacion_vehiculo', 'capacidad_kg_psj']),
                'potencia_hp': self.safe_get(data, ['informacion_vehiculo', 'potencia_hp']),
                'puertas': self.safe_get(data, ['informacion_vehiculo', 'puertas'])
            }
            
            structured = {
                'vehiculo': info_vehiculo,
                'informacion_vehiculo': info_vehiculo,  # Alias para compatibilidad
                'propietario': {
                    'nombre': self.safe_get(data, ['informacion_propietario', 'nombre']),
                    'identificacion': self.safe_get(data, ['informacion_propietario', 'identificacion']),
                    'direccion': self.safe_get(data, ['informacion_propietario', 'direccion']),
                    'telefono': self.safe_get(data, ['informacion_propietario', 'telefono']),
                    'ciudad': self.safe_get(data, ['informacion_propietario', 'ciudad'])
                },
                'registro': {
                    'licencia_transito_numero': self.safe_get(data, ['detalles_registro', 'licencia_transito_numero']),
                    'declaracion_importacion': self.safe_get(data, ['detalles_registro', 'declaracion_importacion']),
                    'fecha_importacion': self.safe_get(data, ['detalles_registro', 'fecha_importacion']),
                    'fecha_matricula': self.safe_get(data, ['detalles_registro', 'fecha_matricula']),
                    'fecha_expedicion_licencia': self.safe_get(data, ['detalles_registro', 'fecha_expedicion_licencia']),
                    'organismo_transito': self.safe_get(data, ['detalles_registro', 'organismo_transito'])
                },
                'restricciones': {
                    'restriccion_movilidad': self.safe_get(data, ['restricciones_limitaciones', 'restriccion_movilidad']),
                    'blindaje': self.safe_get(data, ['restricciones_limitaciones', 'blindaje']),
                    'limitacion_propiedad': self.safe_get(data, ['restricciones_limitaciones', 'limitacion_propiedad'])
                },
                'tipo_documento': self.safe_get(data, ['tipo_documento'])
            }

            return structured

        except (json.JSONDecodeError, TypeError):
            return {}

    def safe_get(self, data, keys):
        """
        Obtiene un valor de un diccionario anidado de forma segura
        """
        try:
            result = data
            for key in keys:
                result = result[key]
            return result if result and str(result).strip() and result != 'No disponible' else None
        except (KeyError, TypeError, AttributeError):
            return None

    def get_or_create_vehiculo(self):
        """
        Crea o obtiene el objeto Vehiculo basado en los datos extraídos
        """
        from apps.vehicles.models import Vehiculo

        structured_data = self.get_structured_data()
        vehiculo_data = structured_data.get('vehiculo', {})

        if not vehiculo_data.get('placa'):
            return None

        try:
            vehiculo = Vehiculo.objects.get(placa=vehiculo_data['placa'])
        except Vehiculo.DoesNotExist:
            vehiculo = Vehiculo.objects.create(
                placa=vehiculo_data.get('placa', ''),
                marca=vehiculo_data.get('marca', ''),
                linea=vehiculo_data.get('linea', ''),
                modelo=self._parse_int(vehiculo_data.get('modelo')),
                color=vehiculo_data.get('color', ''),
                numero_motor=vehiculo_data.get('numero_motor', ''),
                numero_chasis=vehiculo_data.get('numero_chasis', ''),
                numero_vin=vehiculo_data.get('vin', ''),
                cilindraje=self._parse_int(vehiculo_data.get('cilindrada_cc')),
                clase_vehiculo=vehiculo_data.get('clase_vehiculo', ''),
                carroceria=vehiculo_data.get('tipo_carroceria', ''),
                tipo_combustible=vehiculo_data.get('combustible', ''),
                potencia_hp=self._parse_int(vehiculo_data.get('potencia_hp')),
                capacidad=vehiculo_data.get('capacidad_kg_psj', '')
            )

        return vehiculo

    def get_or_create_persona(self, tipo='propietario'):
        """
        Crea o obtiene el objeto Persona basado en los datos extraídos
        """
        from apps.vehicles.models import Persona

        structured_data = self.get_structured_data() or {}
        raw_persona = structured_data.get('propietario') or {}

        def s(key, default=''):
            val = raw_persona.get(key, default)
            return (val or '').strip()

        identificacion = s('identificacion')
        if not identificacion:
            return None

        try:
            persona = Persona.objects.get(numero_documento=identificacion)
        except Persona.DoesNotExist:
            persona = Persona.objects.create(
                nombre=s('nombre'),
                numero_documento=identificacion,
                tipo_documento='CC',  # Asumir cédula por defecto
                direccion=s('direccion'),
                telefono=s('telefono'),
                ciudad=s('ciudad'),
            )

        return persona

    def _parse_int(self, value):
        """
        Convierte un valor a entero de forma segura
        """
        try:
            if value and str(value).strip() and str(value).strip() != 'No disponible':
                return int(str(value).strip())
        except (ValueError, TypeError):
            pass
        return None

    def get_absolute_url(self):
        """URL para redirección después de crear/actualizar"""
        from django.urls import reverse
        return reverse('documents:data_preview', kwargs={'pk': self.pk})


class ExtractedData(models.Model):
    document = models.OneToOneField(Document, on_delete=models.CASCADE)

    # Datos del vehículo
    license_plate = models.CharField(max_length=10, blank=True)
    vin = models.CharField(max_length=17, blank=True)
    make = models.CharField(max_length=50, blank=True)
    model = models.CharField(max_length=50, blank=True)
    year = models.IntegerField(null=True, blank=True)
    color = models.CharField(max_length=30, blank=True)

    # Datos del propietario
    owner_name = models.CharField(max_length=200, blank=True)
    owner_document = models.CharField(max_length=20, blank=True)
    owner_address = models.TextField(blank=True)
    owner_phone = models.CharField(max_length=15, blank=True)
    owner_email = models.EmailField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

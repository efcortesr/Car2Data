# Guía de Despliegue en AWS Academy con Dominio Personalizado

Esta guía te llevará paso a paso para desplegar tu proyecto Django (Car2Data) en AWS Academy usando únicamente EC2 con Amazon Linux y configurar un dominio personalizado (sin usar RDS, S3, ni otros servicios de AWS distintos a EC2).

---

## 📋 Requisitos Previos

- [ ] Cuenta de AWS Academy activa
- [ ] Proyecto Django funcionando localmente
- [ ] Git instalado
- [ ] Dominio registrado (ej: GoDaddy, Namecheap, Google Domains)
- [ ] Acceso SSH configurado

---

## 🎯 Arquitectura del Despliegue

```
Internet → DNS de tu proveedor → EC2 (Amazon Linux) → Nginx + Gunicorn + Django
                                              ↓
                                     PostgreSQL local (en EC2) o SQLite
                                              ↓
                                    Archivos estáticos/media en disco
```

---

## 📦 PARTE 1: Preparar el Proyecto para Producción

### 1.1 Actualizar `settings.py`

Crea un archivo `settings_prod.py` o modifica `settings.py`:

```python
import os
from pathlib import Path

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'tu-secret-key-temporal')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = [
    'tu-dominio.com',
    'www.tu-dominio.com',
    'tu-ip-elastica-de-aws',
    'tu-instancia-ec2.compute.amazonaws.com'
]

# Database (elige UNA opción)
# Opción A: PostgreSQL local en EC2
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'car2data_db'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}
# Opción B (simple): SQLite en disco
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
#     }
# }

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files (User uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# No se usa S3: archivos servidos desde el disco del EC2

# Security Settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
```

### 1.2 Actualizar `requirements.txt`

```bash
cd c:\Users\Emman\Car2Data
pip freeze > requirements.txt
```

Asegúrate de incluir:
```txt
Django==4.2.7
gunicorn==21.2.0
psycopg2-binary==2.9.9
python-decouple==3.8
whitenoise==6.6.0
```

### 1.3 Crear archivo `.env.example`

```bash
# .env.example
DJANGO_SECRET_KEY=tu-secret-key-aqui
DEBUG=False
DB_NAME=car2data_db
DB_USER=postgres
DB_PASSWORD=tu-password-de-rds
DB_HOST=127.0.0.1
DB_PORT=5432
```

---

## 🚀 PARTE 2: Configurar AWS Academy

### 2.1 Crear Instancia EC2

1. **Inicia sesión en AWS Academy**
   - Ve a tu curso → AWS Academy Learner Lab
   - Click en "Start Lab" (espera a que el círculo se ponga verde)
   - Click en "AWS" para abrir la consola

2. **Lanzar Instancia EC2**
   ```
   Servicios → EC2 → Launch Instance
   ```

3. **Configuración de la Instancia**
   - **Name**: `car2data-production`
   - **AMI**: Amazon Linux 2023 (Free tier eligible)
   - **Instance type**: `t2.medium` (recomendado) o `t2.small` (mínimo)
   - **Key pair**: Crea un nuevo par de llaves → `car2data-key.pem` → Descárgalo
   - **Network settings**:
     - VPC: Default
     - Auto-assign public IP: Enable
     - Security Group: Crear nuevo
       - **SSH (22)**: Tu IP
       - **HTTP (80)**: 0.0.0.0/0
       - **HTTPS (443)**: 0.0.0.0/0
       - **Custom TCP (8000)**: 0.0.0.0/0 (temporal para testing)
   - **Storage**: 20 GB gp3

4. **Launch Instance** → Espera a que esté "Running"

5. **Asignar IP Elástica**
   ```
   EC2 → Elastic IPs → Allocate Elastic IP address
   → Associate Elastic IP address → Selecciona tu instancia
   ```

---

## 🔧 PARTE 3: Configurar el Servidor EC2

### 3.1 Conectar por SSH

**Windows (PowerShell):**
```powershell
# Mover la llave a una ubicación segura
Move-Item .\car2data-key.pem ~\.ssh\

# Cambiar permisos (solo lectura para ti)
icacls ~\.ssh\car2data-key.pem /inheritance:r
icacls ~\.ssh\car2data-key.pem /grant:r "$( $env:USERNAME ):(R)"

# Conectar
ssh -i ~\.ssh\car2data-key.pem ec2-user@TU-IP-ELASTICA
```

**Linux/Mac:**
```bash
chmod 400 car2data-key.pem
ssh -i car2data-key.pem ec2-user@TU-IP-ELASTICA
```

### 3.2 Instalar Dependencias en EC2 (Amazon Linux 2023)

```bash
# Actualizar sistema
sudo dnf update -y

# Instalar Python y herramientas de compilación
sudo dnf install -y python3.11 python3.11-devel python3.11-venv gcc

# Instalar PostgreSQL local (servidor y cliente) - Amazon Linux 2023 usa paquetes versionados
sudo dnf install -y postgresql15 postgresql15-server postgresql15-devel

# Instalar Nginx, Git y utilidades
sudo dnf install -y nginx git curl

# (Opcional) Node.js si usas npm para frontend
# sudo dnf module reset nodejs -y && sudo dnf module enable nodejs:20 -y && sudo dnf install -y nodejs
```

### 3.3 Inicializar PostgreSQL local

```bash
# Inicializar base de datos y habilitar servicio (versión 15)
sudo /usr/pgsql-15/bin/postgresql-15-setup initdb
sudo systemctl enable postgresql-15
sudo systemctl start postgresql-15

# Crear usuario y base de datos
sudo -u postgres /usr/pgsql-15/bin/psql -c "ALTER USER postgres WITH PASSWORD 'tu-password-de-rds';"  # cambia la contraseña
sudo -u postgres /usr/pgsql-15/bin/psql -c "CREATE DATABASE car2data_db OWNER postgres;"

# Permitir conexiones locales (peer → md5)
sudo sed -i 's/^host\s\+all\s\+all\s\+127.0.0.1\/32\s\+ident/host    all             all             127.0.0.1\/32            md5/' /var/lib/pgsql/15/data/pg_hba.conf || true
sudo systemctl restart postgresql-15
```

### 3.4 Clonar y Configurar el Proyecto

```bash
# Crear directorio para la aplicación
sudo mkdir -p /var/www/car2data
sudo chown -R ec2-user:ec2-user /var/www/car2data
cd /var/www/car2data

# Clonar repositorio
git clone https://github.com/SamuArango01/Proyecto-1.git .

# Crear entorno virtual
python3.11 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

# Crear archivo .env
nano .env
```

**Contenido de `.env`:**
```bash
DJANGO_SECRET_KEY=genera-una-nueva-secret-key-aqui
DB_NAME=car2data_db
DB_USER=postgres
DB_PASSWORD=Plastinemor282006*
DB_HOST=127.0.0.1
DB_PORT=5432
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,98.80.15.165,car2data.com,www.car2data.com

# AI Services
OPENAI_API_KEY=your-openai-api-key
GEMINI_API_KEY=AIzaSyDvCpz8ZTxm3FsLuyfrvD8WYu5AO7yiGWo
# Email (Production)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-email-password
EMAIL_USE_TLS=True
# Credenciales de Google OAuth
GOOGLE_CLIENT_ID=463729271301-lnbr7ct7egho1u1kqp0178q7pt74b6pv.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=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
```

**Guardar:** `Ctrl+O` → Enter → `Ctrl+X`

### 3.5 Configurar Django

```bash
# Activar entorno virtual
cd /var/www/car2data
source venv/bin/activate

# Migraciones
python manage.py makemigrations
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Recolectar archivos estáticos
python manage.py collectstatic --noinput

# Probar servidor (temporal)
python manage.py runserver 0.0.0.0:8000
```

Abre `http://TU-IP-ELASTICA:8000` en tu navegador para verificar.

---

## 🌐 PARTE 4: Configurar Gunicorn y Nginx

### 4.1 Crear Servicio Systemd para Gunicorn

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

**Contenido:**
```ini
[Unit]
Description=Gunicorn daemon for Car2Data Django app
After=network.target

[Service]
User=ec2-user
Group=nginx
WorkingDirectory=/var/www/car2data/car2data_project
Environment="PATH=/var/www/car2data/venv/bin"
EnvironmentFile=/var/www/car2data/.env
ExecStart=/var/www/car2data/venv/bin/gunicorn \
          --workers 3 \
          --bind unix:/var/www/car2data/gunicorn.sock \
          car2data_project.wsgi:application

[Install]
WantedBy=multi-user.target
```

**Iniciar Gunicorn:**
```bash
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
sudo systemctl status gunicorn
```

### 4.2 Configurar Nginx

```bash
sudo nano /etc/nginx/conf.d/car2data.conf
```

**Contenido:**
```nginx
server {
    listen 80;
    server_name tu-dominio.com www.tu-dominio.com;

    client_max_body_size 100M;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        alias /var/www/car2data/car2data_project/staticfiles/;
    }

    location /media/ {
        alias /var/www/car2data/car2data_project/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/car2data/gunicorn.sock;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_redirect off;
    }
}
```

**Activar configuración:**
```bash
sudo nginx -t
sudo systemctl restart nginx
```

---

## 🔐 PARTE 5: Configurar HTTPS con Let's Encrypt

### 5.1 Instalar Certbot

```bash
sudo dnf install -y certbot python3-certbot-nginx
```

### 5.2 Obtener Certificado SSL

```bash
sudo certbot --nginx -d tu-dominio.com -d www.tu-dominio.com
```

Sigue las instrucciones:
- Email: tu-email@ejemplo.com
- Acepta términos: Y
- Compartir email: N (opcional)
- Redirect HTTP → HTTPS: 2 (recomendado)

### 5.3 Renovación Automática

```bash
sudo certbot renew --dry-run
```

El certificado se renovará automáticamente cada 90 días.

---

## 🌍 PARTE 6: Configurar Dominio

### 6.1 Configurar DNS en tu Proveedor de Dominio

Ve a tu proveedor de dominio (GoDaddy, Namecheap, etc.) y configura:

**Registros DNS:**
```
Tipo    Nombre    Valor                          TTL
A       @         TU-IP-ELASTICA-DE-AWS          600
A       www       TU-IP-ELASTICA-DE-AWS          600
CNAME   www       tu-dominio.com                 3600
```

**Ejemplo con GoDaddy:**
1. My Products → Domains → DNS
2. Add Record → Type: A → Name: @ → Value: TU-IP-ELASTICA → TTL: 600
3. Add Record → Type: A → Name: www → Value: TU-IP-ELASTICA → TTL: 600

**Espera 5-30 minutos para propagación DNS.**

### 6.2 Verificar DNS

```bash
# En tu computadora local
nslookup tu-dominio.com
ping tu-dominio.com
```

---

## 🔄 PARTE 7: Despliegue y Actualizaciones

### 7.1 Script de Despliegue

Crea un script para automatizar actualizaciones:

```bash
nano /var/www/car2data/deploy.sh
```

**Contenido:**
```bash
#!/bin/bash

echo "🚀 Iniciando despliegue..."

# Ir al directorio del proyecto
cd /var/www/car2data

# Activar entorno virtual
source venv/bin/activate

# Pull últimos cambios
git pull origin main

# Instalar/actualizar dependencias
pip install -r requirements.txt

# Migraciones
python car2data_project/manage.py migrate

# Recolectar estáticos
python car2data_project/manage.py collectstatic --noinput

# Reiniciar Gunicorn
sudo systemctl restart gunicorn

# Reiniciar Nginx
sudo systemctl restart nginx

echo "✅ Despliegue completado!"
```

**Hacer ejecutable:**
```bash
chmod +x /var/www/car2data/deploy.sh
```

### 7.2 Desplegar Cambios

```bash
# Desde tu computadora local
git add -A
git commit -m "Nueva funcionalidad"
git push origin main

# En el servidor EC2
cd /var/www/car2data
./deploy.sh
```

---

## 📊 PARTE 8: Monitoreo y Logs

### 8.1 Ver Logs

```bash
# Logs de Gunicorn
sudo journalctl -u gunicorn -f

# Logs de Nginx
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# Logs de Django
tail -f /var/www/car2data/car2data_project/logs/django.log
```

### 8.2 Comandos Útiles

```bash
# Reiniciar servicios
sudo systemctl restart gunicorn
sudo systemctl restart nginx

# Ver estado
sudo systemctl status gunicorn
sudo systemctl status nginx

# Verificar configuración de Nginx
sudo nginx -t

# Recargar Nginx sin downtime
sudo systemctl reload nginx
```

---

## 🛡️ PARTE 9: Seguridad Adicional

### 9.1 Configurar Firewall (opcional)

```bash
# Amazon Linux no incluye UFW por defecto. Puedes usar security groups de EC2.
# (Opcional) Instalar y usar firewalld
# sudo dnf install -y firewalld
# sudo systemctl enable --now firewalld
# sudo firewall-cmd --permanent --add-service=http
# sudo firewall-cmd --permanent --add-service=https
# sudo firewall-cmd --reload
```

### 9.2 Fail2Ban (Protección contra ataques)

```bash
sudo dnf install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 9.3 Backups Automáticos

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/car2data"
mkdir -p $BACKUP_DIR

# Backup de base de datos (PostgreSQL local)
PGPASSWORD=$DB_PASSWORD pg_dump -h $DB_HOST -U $DB_USER $DB_NAME > $BACKUP_DIR/db_$DATE.sql

# Backup de archivos media
tar -czf $BACKUP_DIR/media_$DATE.tar.gz /var/www/car2data/car2data_project/media

# Limpiar backups antiguos (más de 7 días)
find $BACKUP_DIR -type f -mtime +7 -delete
```

**Automatizar con Cron:**
```bash
sudo crontab -e
```

Agregar:
```
0 2 * * * /usr/local/bin/backup-car2data.sh
```

---

## ✅ Checklist Final

- [ ] EC2 instancia corriendo con IP elástica
- [ ] Proyecto clonado y configurado en EC2
- [ ] Gunicorn corriendo como servicio
- [ ] Nginx configurado y corriendo
- [ ] SSL/HTTPS configurado con Let's Encrypt
- [ ] DNS apuntando a IP elástica
- [ ] Dominio accesible vía HTTPS
- [ ] Backups automáticos configurados
- [ ] Seguridad configurada

---

## 🆘 Troubleshooting

### Problema: "502 Bad Gateway"
```bash
# Verificar Gunicorn
sudo systemctl status gunicorn
sudo journalctl -u gunicorn -n 50

# Verificar socket
ls -la /var/www/car2data/gunicorn.sock

# Reiniciar
sudo systemctl restart gunicorn
```

### Problema: "Static files no cargan"
```bash
cd /var/www/car2data
source venv/bin/activate
python manage.py collectstatic --noinput
sudo systemctl restart nginx
```

### Problema: "No se puede conectar a PostgreSQL local"
```bash
# Verificar servicio
sudo systemctl status postgresql

# Probar conexión local
psql -h 127.0.0.1 -U postgres -d car2data_db
```

### Problema: "Domain no resuelve"
```bash
# Verificar DNS
nslookup tu-dominio.com

# Esperar propagación (hasta 48 horas, usualmente 5-30 min)
# Verificar en: https://dnschecker.org
```

---

## 📚 Recursos Adicionales

- [Django Deployment Checklist](https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/)
- [AWS EC2 Documentation](https://docs.aws.amazon.com/ec2/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)

---

## 🎉 ¡Felicidades!

Tu aplicación Car2Data ahora está desplegada en AWS Academy con:
- ✅ Dominio personalizado
- ✅ HTTPS/SSL
- ✅ Base de datos PostgreSQL local en EC2 (o SQLite)
- ✅ Archivos estáticos/media en el disco del servidor
- ✅ Servidor de producción con Gunicorn + Nginx
- ✅ Backups automáticos
- ✅ Seguridad configurada

**URL de acceso:** `https://tu-dominio.com`
**Panel admin:** `https://tu-dominio.com/admin`

---

**Última actualización:** Noviembre 2025
**Autor:** Car2Data Team
**Versión:** 1.0

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.views.generic import CreateView, TemplateView, UpdateView
from django.contrib.auth.models import User
from django.contrib.auth import forms as auth_forms
from .forms import UserProfileForm, CustomUserCreationForm
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import VerificationCode, UserSubscription
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.views import View
import resend

class LoginView(DjangoLoginView):
    template_name = 'authentication/login.html'
    
    def get_success_url(self):
        return reverse_lazy('documents:dashboard')

class RegisterView(CreateView):
    model = User
    form_class = CustomUserCreationForm
    template_name = 'authentication/register.html'
    success_url = reverse_lazy('authentication:verify_email_prompt')
    
    def form_valid(self, form):
        # Permitir desactivar temporalmente la verificación por email con PIN
        user = form.save(commit=False)
        disable_email_verification = getattr(settings, 'DISABLE_EMAIL_VERIFICATION', False)

        # Si la verificación está desactivada, el usuario se crea activo
        user.is_active = True if disable_email_verification else False
        user.save()
        
        # TODOS los usuarios nuevos inician con plan FREE (starter)
        UserSubscription.objects.create(
            user=user,
            plan='starter',
            payment_status='completed',
            documents_used=0
        )

        if disable_email_verification:
            # Sin verificación: iniciar sesión y enviar al dashboard directamente
            login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(self.request, 'Cuenta creada. Verificación por correo desactivada temporalmente.')
            return redirect('documents:dashboard')

        # Flujo normal con verificación por PIN
        code = VerificationCode.generate_code()
        verification = VerificationCode.objects.create(
            user=user,
            code=code,
            code_type='email_verification',
            email=user.email,
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        
        # Enviar email con código
        self.send_verification_email(user.email, code, user.username)
        
        # Guardar user_id en sesión para el proceso de verificación
        self.request.session['pending_user_id'] = user.id
        
        messages.success(self.request, 'Cuenta creada. Por favor verifica tu correo electrónico.')
        return redirect(self.success_url)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Error al crear la cuenta. Por favor verifica los datos.')
        return super().form_invalid(form)
    
    def send_verification_email(self, email, code, username):
        """Envía el email con el código de verificación"""
        subject = 'Car2Data - Verifica tu cuenta'
        message = f'''Hola {username},

Gracias por registrarte en Car2Data.

Tu código de verificación es: {code}

Este código expira en 15 minutos.

Si no solicitaste esta cuenta, puedes ignorar este mensaje.

Saludos,
Equipo Car2Data'''
        
        # SIEMPRE mostrar el código en consola para desarrollo
        print(f"\n{'='*50}")
        print(f"📧 CÓDIGO DE VERIFICACIÓN")
        print(f"{'='*50}")
        print(f"Usuario: {username}")
        print(f"Email: {email}")
        print(f"Código: {code}")
        print(f"Expira en: 15 minutos")
        print(f"{'='*50}\n")
        
        try:
            api_key = getattr(settings, "RESEND_API_KEY", "")
            if not settings.DEBUG and api_key:
                resend.api_key = api_key
                from_email = getattr(settings, "RESEND_FROM_EMAIL", "") or settings.DEFAULT_FROM_EMAIL
                resend.Emails.send(
                    {
                        "from": from_email,
                        "to": [email],
                        "subject": subject,
                        "text": message,
                    }
                )
                print("✅ Email enviado vía Resend")
            else:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                print("✅ Email enviado exitosamente")
        except SystemExit as e:
            # En algunos entornos, fallos de conexión SMTP provocan SystemExit,
            # lo que tumba el worker de Gunicorn si no se captura.
            print(f"⚠️  Error crítico al enviar email (SystemExit): {e}")
            print("💡 Usa el código mostrado arriba para verificar tu cuenta")
        except Exception as e:
            print(f"⚠️  Error al enviar email: {e}")
            print("💡 Usa el código mostrado arriba para verificar tu cuenta")

class IndexView(TemplateView):
    template_name = 'index.html'
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('documents:dashboard')
        return super().get(request, *args, **kwargs)
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context

def logout_view(request):
    logout(request)
    messages.info(request, 'Has cerrado sesión exitosamente.')
    return redirect('authentication:login')

class UserProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'authentication/profile.html'

    def get(self, request, *args, **kwargs):
        form = UserProfileForm(instance=request.user)
        context = {'form': form}
        # Plan/subscription context
        try:
            subscription = request.user.subscription
            # Features por plan
            features_map = {
                'starter': [
                    '3 documentos/mes',
                    'Autodiligenciado básico',
                ],
                'pro': [
                    '100 documentos/mes',
                    'Contratos y formularios oficiales',
                    'Soporte prioritario',
                ],
                'enterprise': [
                    'Documentos ilimitados',
                    'SLA y soporte dedicado',
                    'Integraciones a medida',
                ],
            }
            plan_key = subscription.plan
            context.update({
                'subscription': subscription,
                'plan_name': subscription.get_plan_display(),
                'documents_used': subscription.documents_used,
                'documents_limit': subscription.get_documents_limit(),
                'documents_remaining': subscription.get_remaining_documents(),
                'can_upload': subscription.can_generate_document(),
                'plan_features': features_map.get(plan_key, []),
                # Fecha de renovación (si aplica). No hay campo explícito; mostrar None para ocultar en template.
                'renewal_date': None,
            })
        except Exception:
            context.update({
                'subscription': None,
                'plan_name': 'Starter',
                'documents_used': 0,
                'documents_limit': 3,
                'documents_remaining': 3,
                'can_upload': True,
                'plan_features': ['3 documentos/mes', 'Autodiligenciado básico'],
                'renewal_date': None,
            })
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tu perfil ha sido actualizado exitosamente.')
            return redirect('authentication:profile')
        messages.error(request, 'Por favor corrige los errores en el formulario.')
        # Include subscription context on error as well
        context = {'form': form}
        try:
            subscription = request.user.subscription
            context.update({
                'subscription': subscription,
                'plan_name': subscription.get_plan_display(),
                'documents_used': subscription.documents_used,
                'documents_limit': subscription.get_documents_limit(),
                'documents_remaining': subscription.get_remaining_documents(),
                'can_upload': subscription.can_generate_document(),
            })
        except Exception:
            context.update({
                'subscription': None,
                'plan_name': 'Starter',
                'documents_used': 0,
                'documents_limit': 3,
                'documents_remaining': 3,
                'can_upload': True,
            })
        return self.render_to_response(context)

class UserSettingsView(LoginRequiredMixin, PasswordChangeView):
    template_name = 'authentication/settings.html'
    success_url = reverse_lazy('authentication:settings')

    def form_valid(self, form):
        messages.success(self.request, 'Tu contraseña ha sido cambiada exitosamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            subscription = self.request.user.subscription
            features_map = {
                'starter': ['3 documentos/mes', 'Autodiligenciado básico'],
                'pro': ['100 documentos/mes', 'Contratos y formularios oficiales', 'Soporte prioritario'],
                'enterprise': ['Documentos ilimitados', 'SLA y soporte dedicado', 'Integraciones a medida'],
            }
            plan_key = subscription.plan
            context.update({
                'subscription': subscription,
                'plan_name': subscription.get_plan_display(),
                'documents_used': subscription.documents_used,
                'documents_limit': subscription.get_documents_limit(),
                'documents_remaining': subscription.get_remaining_documents(),
                'can_upload': subscription.can_generate_document(),
                'plan_features': features_map.get(plan_key, []),
                'renewal_date': None,
            })
        except Exception:
            context.update({
                'subscription': None,
                'plan_name': 'Starter',
                'documents_used': 0,
                'documents_limit': 3,
                'documents_remaining': 3,
                'can_upload': True,
                'plan_features': ['3 documentos/mes', 'Autodiligenciado básico'],
                'renewal_date': None,
            })
        return context

class VerifyEmailPromptView(TemplateView):
    template_name = 'authentication/verify_email_prompt.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_id = self.request.session.get('pending_user_id')
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                context['email'] = user.email
            except User.DoesNotExist:
                pass
        return context

class VerifyEmailView(View):
    def post(self, request):
        code = request.POST.get('code', '').strip()
        user_id = request.session.get('pending_user_id')
        
        if not user_id:
            messages.error(request, 'Sesión expirada. Por favor regístrate nuevamente.')
            return redirect('authentication:register')
        
        try:
            user = User.objects.get(id=user_id)
            verification = VerificationCode.objects.filter(
                user=user,
                code=code,
                code_type='email_verification'
            ).first()
            
            if not verification:
                messages.error(request, 'Código incorrecto. Por favor intenta nuevamente.')
                return redirect('authentication:verify_email_prompt')
            
            if not verification.is_valid():
                messages.error(request, 'El código ha expirado. Solicita uno nuevo.')
                return redirect('authentication:verify_email_prompt')
            
            # Activar usuario y marcar código como usado
            user.is_active = True
            user.save()
            verification.mark_as_used()
            
            # Limpiar sesión
            del request.session['pending_user_id']
            
            # Loguear automáticamente al usuario con backend específico
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            # TODOS van al dashboard con plan FREE
            messages.success(request, '¡Cuenta verificada! Bienvenido a Car2Data. Tienes 3 documentos gratis.')
            return redirect('documents:dashboard')
            
        except User.DoesNotExist:
            messages.error(request, 'Usuario no encontrado.')
            return redirect('authentication:register')

class ResendVerificationCodeView(View):
    def post(self, request):
        user_id = request.session.get('pending_user_id')
        
        if not user_id:
            messages.error(request, 'Sesión expirada. Por favor regístrate nuevamente.')
            return redirect('authentication:register')
        
        try:
            user = User.objects.get(id=user_id)
            
            # Invalidar códigos anteriores
            VerificationCode.objects.filter(
                user=user,
                code_type='email_verification',
                is_used=False
            ).update(is_used=True)
            
            # Generar nuevo código
            code = VerificationCode.generate_code()
            verification = VerificationCode.objects.create(
                user=user,
                code=code,
                code_type='email_verification',
                email=user.email,
                expires_at=timezone.now() + timedelta(minutes=15)
            )
            
            # Enviar email
            self.send_verification_email(user.email, code, user.username)
            
            messages.success(request, 'Se ha enviado un nuevo código a tu correo.')
            return redirect('authentication:verify_email_prompt')
            
        except User.DoesNotExist:
            messages.error(request, 'Usuario no encontrado.')
            return redirect('authentication:register')
    
    def send_verification_email(self, email, code, username):
        subject = 'Car2Data - Nuevo código de verificación'
        message = f'''Hola {username},

Tu nuevo código de verificación es: {code}

Este código expira en 15 minutos.

Saludos,
Equipo Car2Data'''
        
        # SIEMPRE mostrar el código en consola para desarrollo
        print(f"\n{'='*50}")
        print(f"🔄 NUEVO CÓDIGO DE VERIFICACIÓN")
        print(f"{'='*50}")
        print(f"Usuario: {username}")
        print(f"Email: {email}")
        print(f"Código: {code}")
        print(f"Expira en: 15 minutos")
        print(f"{'='*50}\n")
        
        try:
            api_key = getattr(settings, "RESEND_API_KEY", "")
            if not settings.DEBUG and api_key:
                resend.api_key = api_key
                from_email = getattr(settings, "RESEND_FROM_EMAIL", "") or settings.DEFAULT_FROM_EMAIL
                resend.Emails.send(
                    {
                        "from": from_email,
                        "to": [email],
                        "subject": subject,
                        "text": message,
                    }
                )
                print("✅ Email reenviado vía Resend")
            else:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
                print("✅ Email reenviado exitosamente")
        except SystemExit as e:
            print(f"⚠️  Error crítico al reenviar email (SystemExit): {e}")
            print("💡 Usa el código mostrado arriba para verificar tu cuenta")
        except Exception as e:
            print(f"⚠️  Error al reenviar email: {e}")
            print("💡 Usa el código mostrado arriba para verificar tu cuenta")

class ForgotPasswordView(TemplateView):
    template_name = 'authentication/forgot_password.html'
    
    def post(self, request):
        email = request.POST.get('email', '').strip()
        
        try:
            user = User.objects.get(email=email)
            
            # Invalidar códigos anteriores
            VerificationCode.objects.filter(
                user=user,
                code_type='password_reset',
                is_used=False
            ).update(is_used=True)
            
            # Generar código de recuperación
            code = VerificationCode.generate_code()
            verification = VerificationCode.objects.create(
                user=user,
                code=code,
                code_type='password_reset',
                email=email,
                expires_at=timezone.now() + timedelta(minutes=15)
            )
            
            # Enviar email
            self.send_reset_email(email, code, user.username)
            
            # Guardar email en sesión
            request.session['reset_email'] = email
            
            messages.success(request, 'Se ha enviado un código de recuperación a tu correo.')
            return redirect('authentication:verify_reset_code')
            
        except User.DoesNotExist:
            # Por seguridad, no revelar si el email existe o no
            messages.success(request, 'Si el correo existe, recibirás un código de recuperación.')
            return redirect('authentication:forgot_password')
    
    def send_reset_email(self, email, code, username):
        subject = 'Car2Data - Recuperación de contraseña'
        message = f'''Hola {username},

Has solicitado recuperar tu contraseña.

Tu código de recuperación es: {code}

Este código expira en 15 minutos.

Si no solicitaste este cambio, puedes ignorar este mensaje.

Saludos,
Equipo Car2Data'''
        
        # SIEMPRE mostrar el código en consola para desarrollo
        print(f"\n{'='*50}")
        print(f"🔑 CÓDIGO DE RECUPERACIÓN DE CONTRASEÑA")
        print(f"{'='*50}")
        print(f"Usuario: {username}")
        print(f"Email: {email}")
        print(f"Código: {code}")
        print(f"Expira en: 15 minutos")
        print(f"{'='*50}\n")
        
        try:
            api_key = getattr(settings, "RESEND_API_KEY", "")
            if not settings.DEBUG and api_key:
                resend.api_key = api_key
                from_email = getattr(settings, "RESEND_FROM_EMAIL", "") or settings.DEFAULT_FROM_EMAIL
                resend.Emails.send(
                    {
                        "from": from_email,
                        "to": [email],
                        "subject": subject,
                        "text": message,
                    }
                )
                print("✅ Email de recuperación enviado vía Resend")
            else:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
                print("✅ Email de recuperación enviado exitosamente")
        except SystemExit as e:
            print(f"⚠️  Error crítico al enviar email de recuperación (SystemExit): {e}")
            print("💡 Usa el código mostrado arriba para recuperar tu contraseña")
        except Exception as e:
            print(f"⚠️  Error al enviar email de recuperación: {e}")
            print("💡 Usa el código mostrado arriba para recuperar tu contraseña")

class VerifyResetCodeView(TemplateView):
    template_name = 'authentication/verify_reset_code.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['email'] = self.request.session.get('reset_email', '')
        return context
    
    def post(self, request):
        code = request.POST.get('code', '').strip()
        email = request.session.get('reset_email')
        
        if not email:
            messages.error(request, 'Sesión expirada. Por favor solicita la recuperación nuevamente.')
            return redirect('authentication:forgot_password')
        
        try:
            user = User.objects.get(email=email)
            verification = VerificationCode.objects.filter(
                user=user,
                code=code,
                code_type='password_reset'
            ).first()
            
            if not verification:
                messages.error(request, 'Código incorrecto. Por favor intenta nuevamente.')
                return redirect('authentication:verify_reset_code')
            
            if not verification.is_valid():
                messages.error(request, 'El código ha expirado. Solicita uno nuevo.')
                return redirect('authentication:forgot_password')
            
            # Guardar código verificado en sesión
            request.session['verified_code_id'] = verification.id
            
            return redirect('authentication:reset_password')
            
        except User.DoesNotExist:
            messages.error(request, 'Usuario no encontrado.')
            return redirect('authentication:forgot_password')

class ResetPasswordView(TemplateView):
    template_name = 'authentication/reset_password.html'
    
    def get(self, request):
        if not request.session.get('verified_code_id'):
            messages.error(request, 'Debes verificar el código primero.')
            return redirect('authentication:forgot_password')
        return super().get(request)
    
    def post(self, request):
        verified_code_id = request.session.get('verified_code_id')
        email = request.session.get('reset_email')
        
        if not verified_code_id or not email:
            messages.error(request, 'Sesión expirada. Por favor solicita la recuperación nuevamente.')
            return redirect('authentication:forgot_password')
        
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        
        if password1 != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
            return redirect('authentication:reset_password')
        
        if len(password1) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
            return redirect('authentication:reset_password')
        
        try:
            verification = VerificationCode.objects.get(id=verified_code_id)
            user = verification.user
            
            # Cambiar contraseña
            user.set_password(password1)
            user.save()
            
            # Marcar código como usado
            verification.mark_as_used()
            
            # Limpiar sesión
            del request.session['verified_code_id']
            del request.session['reset_email']
            
            messages.success(request, 'Contraseña restablecida exitosamente. Ahora puedes iniciar sesión.')
            return redirect('authentication:login')
            
        except VerificationCode.DoesNotExist:
            messages.error(request, 'Código de verificación no válido.')
            return redirect('authentication:forgot_password')

class CheckoutView(LoginRequiredMixin, TemplateView):
    """Vista de checkout para upgrade a plan Pro"""
    template_name = 'authentication/checkout_modal.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener la suscripción del usuario
        try:
            subscription = UserSubscription.objects.get(user=self.request.user)
            context['subscription'] = subscription
            context['current_plan'] = subscription.get_plan_display()
            context['plan_name'] = 'Pro'  # Siempre upgrade a Pro
            context['plan_price'] = 19
            context['documents_used'] = subscription.documents_used
            context['documents_limit'] = subscription.get_documents_limit()
        except UserSubscription.DoesNotExist:
            # Si no tiene suscripción, crear una por defecto
            subscription = UserSubscription.objects.create(
                user=self.request.user,
                plan='starter',
                documents_used=0
            )
            context['subscription'] = subscription
            context['current_plan'] = 'Starter'
            context['plan_name'] = 'Pro'
            context['plan_price'] = 19
            context['documents_used'] = 0
            context['documents_limit'] = 3
        
        return context
    
    def post(self, request):
        """Procesar el upgrade a plan Pro"""
        try:
            subscription = UserSubscription.objects.get(user=request.user)
            
            # Aquí iría la integración con Stripe u otro procesador de pagos
            # Por ahora, simulamos un pago exitoso y upgrade
            subscription.plan = 'pro'
            subscription.payment_status = 'completed'
            subscription.save()
            
            messages.success(request, '¡Pago procesado exitosamente! Ahora tienes el plan Pro con 100 documentos/mes.')
            return redirect('documents:dashboard')
            
        except UserSubscription.DoesNotExist:
            messages.error(request, 'No se encontró tu suscripción.')
            return redirect('documents:dashboard')
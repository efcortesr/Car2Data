from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'w-full border border-gray-300 rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-turquoise'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full border border-gray-300 rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-turquoise'}),
            'email': forms.EmailInput(attrs={'class': 'w-full border border-gray-300 rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-turquoise'}),
        }


class CustomUserCreationForm(UserCreationForm):
    """Formulario de registro que incluye el correo electrónico y lo guarda en el usuario."""

    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "")
        if commit:
            user.save()
        return user

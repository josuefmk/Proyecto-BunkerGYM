from django import forms
from .models import Cliente, Producto, PlanPersonalizado
import re

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'nombre',
            'apellido',
            'correo',
            'telefono',
            'rut',
            'mensualidad',
            'plan_personalizado',
            'metodo_pago'
        ]
        labels = {
            'nombre': 'Nombres',
            'apellido': 'Apellidos',
            'correo': 'Email',
            'telefono': 'Teléfono',
            'rut': 'RUT',
            'mensualidad': 'Plan',
            'plan_personalizado': 'Plan Personalizado',
            'metodo_pago': 'Método de pago',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control',
                                                 'placeholder': 'Ej: 9 1234 5678'}),
            'rut': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 12345678-9'
            }),
            'mensualidad': forms.Select(attrs={'class': 'form-control'
            }),
            'plan_personalizado': forms.Select(attrs={'class': 'form-control'}),
            'metodo_pago': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_rut(self):
        rut = self.cleaned_data.get('rut')
        if not rut:
            raise forms.ValidationError("Este campo es obligatorio.")

        if not re.match(r'^\d{7,8}-[\dkK]$', rut):
            raise forms.ValidationError("Formato inválido. Use 12345678-9")

        return rut
class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'descripcion', 'precio_compra', 'precio_venta', 'stock']
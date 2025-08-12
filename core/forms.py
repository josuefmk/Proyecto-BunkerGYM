from datetime import timedelta
from django import forms
from .models import Cliente, Producto, PlanPersonalizado
import re



def validar_rut(rut):
    rut = rut.replace('.', '').upper()
    if not re.match(r'^\d{7,8}-[\dK]$', rut):
        return False

    num, dv = rut.split('-')
    suma = 0
    multiplicador = 2

    for digito in reversed(num):
        suma += int(digito) * multiplicador
        multiplicador += 1
        if multiplicador > 7:
            multiplicador = 2

    resto = suma % 11
    dv_calculado = 11 - resto

    if dv_calculado == 11:
        dv_calculado = '0'
    elif dv_calculado == 10:
        dv_calculado = 'K'
    else:
        dv_calculado = str(dv_calculado)

    return dv == dv_calculado

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'nombre', 'apellido', 'correo', 'telefono', 'rut',
            'mensualidad', 'plan_personalizado', 'metodo_pago', 'fecha_inicio_plan', 'sub_plan'
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
            'fecha_inicio_plan': 'Fecha de inicio'
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'rut': forms.TextInput(attrs={'class': 'form-control'}),
            'mensualidad': forms.Select(attrs={'class': 'form-control'}),
            'plan_personalizado': forms.Select(attrs={'class': 'form-control'}),
            'metodo_pago': forms.Select(attrs={'class': 'form-control'}),
            'fecha_inicio_plan': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'sub_plan': forms.HiddenInput() 
        }

    def clean_rut(self):
        rut = self.cleaned_data.get('rut')
        if not rut:
            raise forms.ValidationError("Este campo es obligatorio.")

        rut = rut.strip().upper()

        # Validar formato
        if not re.match(r'^\d{7,8}-[\dK]$', rut):
            raise forms.ValidationError("Formato inválido. Use 12345678-9")

        # Validar digito verificador
        if not validar_rut(rut):
            raise forms.ValidationError("RUT inválido. Dígito verificador incorrecto.")

        # Validar duplicados 
        if Cliente.objects.filter(rut=rut).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("⚠️ Este RUT ya está registrado.")

        return rut

    def clean_telefono(self):
        telefono = self.cleaned_data.get('telefono')
        if not telefono:
            raise forms.ValidationError("Este campo es obligatorio.")
        if not telefono.isdigit():
            raise forms.ValidationError("El teléfono debe contener solo números.")
        if len(telefono) != 9:
            raise forms.ValidationError("El teléfono debe tener exactamente 9 dígitos.")
        return telefono

    def save(self, commit=True):
        cliente = super().save(commit=False)
        if cliente.fecha_inicio_plan:
            cliente.fecha_fin_plan = cliente.fecha_inicio_plan + timedelta(days=30)
        if commit:
            cliente.save()
        return cliente
class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'descripcion', 'precio_compra', 'precio_venta', 'stock']
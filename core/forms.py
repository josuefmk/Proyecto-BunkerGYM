from datetime import timedelta
from django import forms
from .models import Cliente, Precios, Producto, PlanPersonalizado
import re
from django.utils import timezone



def validar_rut(rut):
 
    try:
      
        rut = rut.replace('.', '').upper().strip()
        
      
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

    except Exception:
 
        return False


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'nombre', 'apellido', 'correo', 'telefono', 'rut',
            'mensualidad', 'planes_personalizados', 'metodo_pago', 'fecha_inicio_plan', 'sub_plan'
        ]
        labels = {
            'nombre': 'Nombres',
            'apellido': 'Apellidos',
            'correo': 'Email',
            'telefono': 'Teléfono',
            'rut': 'RUT',
            'mensualidad': 'Plan',
            'planes_personalizados': 'Planes Personalizados',
            'metodo_pago': 'Método de pago',
            'fecha_inicio_plan': 'Fecha de inicio'
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control',   'placeholder': 'Ej: 9 12345678'}),
            'rut': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingresa RUT sin puntos, con guion. Ej: 12345678-9'
                        }),
            'mensualidad': forms.Select(attrs={'class': 'form-control'}),
            'planes_personalizados': forms.SelectMultiple(attrs={
                'class': 'form-control select2',
                'style': 'width: 100%;'
            }),
            'metodo_pago': forms.Select(attrs={'class': 'form-control'}),
            'fecha_inicio_plan': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'sub_plan': forms.HiddenInput()
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['mensualidad'].empty_label = "Seleccione un plan..."
        choices = [('', 'Seleccione un método de pago...')] + [c for c in self.fields['metodo_pago'].choices if c[0]]
        self.fields['metodo_pago'].choices = choices

        if not self.instance.pk:  # Si es nuevo
            hoy = timezone.localdate().strftime('%Y-%m-%d')
            self.fields['fecha_inicio_plan'].initial = hoy
            self.fields['fecha_inicio_plan'].widget.attrs['value'] = hoy

 
    def clean_planes_personalizados(self):
        planes = self.cleaned_data.get('planes_personalizados')
        if planes.count() > 2:
            raise forms.ValidationError("⚠️ Solo puedes seleccionar máximo 2 planes personalizados.")
        return planes

    def clean_rut(self):
        rut = self.cleaned_data.get('rut')
        if not rut:
            raise forms.ValidationError("Este campo es obligatorio.")
        rut = rut.strip().upper()
        if not re.match(r'^\d{7,8}-[\dK]$', rut):
            raise forms.ValidationError("Formato inválido. Use 12345678-9")
        if not validar_rut(rut):
            raise forms.ValidationError("RUT inválido. Dígito verificador incorrecto.")
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

        if not cliente.fecha_inicio_plan:
            cliente.fecha_inicio_plan = timezone.localdate()

        # Calcular días extra si se necesita
        dias_extra = 0
        hoy = timezone.localdate()
        if cliente.fecha_fin_plan and cliente.fecha_fin_plan > hoy:
            dias_extra = (cliente.fecha_fin_plan - hoy).days

        # Activar plan correctamente
        cliente.activar_plan(fecha_activacion=cliente.fecha_inicio_plan, dias_extra=dias_extra)

        if commit:
            cliente.save()
            self.save_m2m()
        return cliente
    
class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'descripcion', 'precio_compra', 'precio_venta', 'stock']




class PrecioUpdateForm(forms.ModelForm):
    class Meta:
        model = Precios
        fields = ['precio']
        widgets = {
            'precio': forms.NumberInput(attrs={'class': 'input-bonito'}),
        }

class DescuentoUpdateForm(forms.ModelForm):
    class Meta:
        model = Precios
        fields = ['descuento']
        widgets = {
            'descuento': forms.NumberInput(attrs={'class': 'input-bonito'}),
        }
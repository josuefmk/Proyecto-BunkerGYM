from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta 
from datetime import timedelta
from django.utils import timezone
# --------------------------
# Modelo: Administrador
# --------------------------
class Admin(models.Model):
    nombreUsuario = models.CharField(max_length=50, default="usuario")
    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    rut = models.CharField(max_length=12, unique=True)
    password = models.CharField(max_length=128)

    def __str__(self):
        return f'{self.nombre} {self.apellido}'


# --------------------------
# Modelo: Mensualidad (básico)
# --------------------------
class Mensualidad(models.Model):
    OPCIONES = [
        ('Estudiante', 'Estudiante'),
        ('Normal', 'Normal'),
    ]
    tipo = models.CharField(max_length=20, choices=OPCIONES, unique=True)

    def __str__(self):
        return self.tipo


# --------------------------
# Modelo: Plan Personalizado
# --------------------------
class PlanPersonalizado(models.Model):
    nombre_plan = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre_plan


# --------------------------
# Modelo: Cliente
# --------------------------
class Cliente(models.Model):
    METODOS_PAGO = [
        ('efectivo', 'Efectivo'),
        ('debito', 'Débito'),
        ('credito', 'Crédito'),
    ]

    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    rut = models.CharField(max_length=12, unique=True)
    correo = models.EmailField()
    telefono = models.CharField(max_length=15)

    mensualidad = models.ForeignKey(Mensualidad, on_delete=models.SET_NULL, null=True, blank=True)
    plan_personalizado = models.ForeignKey(PlanPersonalizado, on_delete=models.SET_NULL, null=True, blank=True)
    metodo_pago = models.CharField(max_length=10, choices=METODOS_PAGO, null=True, blank=True)
    fecha_inicio_plan = models.DateField(default=timezone.now, null=True, blank=True)

    def calcular_vencimiento(self):
        return self.fecha_inicio_plan + relativedelta(months=1)

    def dias_restantes(self):
        vencimiento = self.calcular_vencimiento()
        hoy = timezone.now().date()
        dias = (vencimiento - hoy).days
        return dias if dias >= 0 else 0



    def __str__(self):
        return f'{self.nombre} {self.apellido}'


class Asistencia(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    fecha = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.cliente.nombre} - {self.fecha.date()}"

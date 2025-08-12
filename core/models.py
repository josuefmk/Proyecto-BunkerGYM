from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta 
from datetime import timedelta,datetime
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
    TIPOS = [
        ('Estudiante', 'Estudiante'),
        ('Normal', 'Normal'),
         ('Adulto Mayor', 'Adulto Mayor'),
    ]
    DURACIONES = [
        ('Mensual', 'Mensual'),
        ('Trimestral', 'Trimestral'),
        ('Anual', 'Anual'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPOS)
    duracion = models.CharField(max_length=20, choices=DURACIONES, default='Mensual')

    class Meta:
        unique_together = ('tipo', 'duracion')

    def __str__(self):
        return f"{self.tipo} + Plan {self.duracion}"
    
# --------------------------
# Modelo: Plan Personalizado
# --------------------------
class PlanPersonalizado(models.Model):
    nombre_plan = models.CharField(max_length=100, unique=True)
    accesos_por_semana = models.IntegerField(default=0)
    def __str__(self):
        return self.nombre_plan


# --------------------------
# Modelo: Cliente
# --------------------------


class Cliente(models.Model):
    METODOS_PAGO = [
        ('Efectivo', 'Efectivo'),
        ('Debito', 'Débito'),
        ('Credito', 'Crédito'),
        ('Transferencia', 'Transferencia'),
    ]
    SUB_PLANES = [
        ('Bronce', 'Bronce (4 Accesos)'),
        ('Hierro', 'Hierro (8 Accesos)'),
        ('Acero', 'Acero (12 Accesos)'),
        ('Titanio', 'Titanio (Acceso Libre)'),
    ]

    ESTADOS_PLAN = [
        ('pendiente', 'Pendiente de activación'),
        ('activo', 'Activo'),
        ('vencido', 'Vencido'),
        ('suspendido', 'Suspendido'),
    ]

    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    rut = models.CharField(max_length=12, unique=True)
    correo = models.EmailField()
    telefono = models.CharField(max_length=15)
    huella_template = models.BinaryField(null=True, blank=True)
    mensualidad = models.ForeignKey('Mensualidad', on_delete=models.SET_NULL, null=True, blank=True)
    plan_personalizado = models.ForeignKey('PlanPersonalizado', on_delete=models.SET_NULL, null=True, blank=True)
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, null=True, blank=True)
    fecha_inicio_plan = models.DateField(null=True, blank=True)
    fecha_fin_plan = models.DateField(null=True, blank=True)
    sub_plan = models.CharField(max_length=20, choices=SUB_PLANES, null=True, blank=True)
    accesos_restantes = models.IntegerField(default=0)
    accesos_semana_restantes = models.IntegerField(default=0)
    ultimo_reset_semana = models.DateField(null=True, blank=True)

    duraciones_a_dias = {
        "Mensual": 30,
        "Trimestral": 90,
        "Anual": 365
    }

    precios = {
        'Normal': {
            'Bronce': 15990,
            'Hierro': 25990,
            'Acero': 32990,
            'Titanio': 44990,
        },
        'Estudiante': {
            'Bronce': 11990,
            'Hierro': 18990,
            'Acero': 22990,
            'Titanio': 31990,
        }
    }

    def save(self, *args, **kwargs):
        if isinstance(self.fecha_inicio_plan, datetime):
            self.fecha_inicio_plan = self.fecha_inicio_plan.date()

        if not self.fecha_inicio_plan:
            self.fecha_inicio_plan = timezone.localdate()

        if not self.fecha_fin_plan:
            dias_total = 30
            if self.mensualidad:
                dias_total = self.duraciones_a_dias.get(self.mensualidad.duracion, 30)
            self.fecha_fin_plan = self.fecha_inicio_plan + timedelta(days=dias_total)

        if self.plan_personalizado and (self.accesos_semana_restantes == 0 or self.accesos_semana_restantes is None):
            self.accesos_semana_restantes = self.plan_personalizado.accesos_por_semana

        super().save(*args, **kwargs)

    @property
    def estado_plan(self):
        hoy = timezone.localdate()
        if self.fecha_fin_plan and self.fecha_fin_plan < hoy:
            return 'vencido'
        elif self.fecha_inicio_plan and self.fecha_inicio_plan > hoy:
            return 'pendiente'
        else:
            return 'activo'

    @property
    def dias_restantes(self):
        hoy = timezone.localdate()
        if self.fecha_inicio_plan and self.fecha_inicio_plan > hoy:
            return (self.fecha_inicio_plan - hoy).days
        vencimiento = self.fecha_fin_plan or (
            self.fecha_inicio_plan + timedelta(days=self.duraciones_a_dias.get(
                self.mensualidad.duracion if self.mensualidad else None, 30))
        )
        return (vencimiento - hoy).days

    def activar_plan(self, fecha_activacion=None, dias_extra=0):
        if fecha_activacion is None:
            fecha_activacion = timezone.localdate()

        self.fecha_inicio_plan = fecha_activacion
        dias_total = self.duraciones_a_dias.get(self.mensualidad.duracion, 30) + dias_extra
        self.fecha_fin_plan = self.fecha_inicio_plan + timedelta(days=dias_total)

        accesos_dict = {
            'Bronce': 4,
            'Hierro': 8,
            'Acero': 12,
            'Titanio': 0
        }
        if self.sub_plan:
            self.accesos_restantes = accesos_dict.get(self.sub_plan, 0)

        super().save()

    @property
    def precio_plan(self):
        if not self.mensualidad or not self.sub_plan:
            return None

        tipo = self.mensualidad.tipo  
        return self.precios.get(tipo, {}).get(self.sub_plan, None)

    def __str__(self):
        return f'{self.nombre} {self.apellido}'




class Asistencia(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    fecha = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.cliente.nombre} - {self.fecha.date()}"






class Producto(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    precio_compra = models.DecimalField(max_digits=10, decimal_places=2)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    stock_inicial = models.PositiveIntegerField(null=True, blank=True) 

    def save(self, *args, **kwargs):
        if self.stock_inicial is None:
            self.stock_inicial = self.stock  
        super().save(*args, **kwargs)

    def valor_total_stock(self):
        return self.stock * self.precio_compra

    def estimado_ganancia(self):
        return self.stock * (self.precio_venta - self.precio_compra)

    def cantidad_vendida(self):
        if self.stock_inicial is not None:
            return self.stock_inicial - self.stock
        return 0

    def ganancia_real(self):
        return self.cantidad_vendida() * (self.precio_venta - self.precio_compra)

    def __str__(self):
        return f"{self.nombre} (Stock: {self.stock})"
    
class Venta(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    fecha_venta = models.DateTimeField(auto_now_add=True)

    def total_venta(self):
        return self.cantidad * self.producto.precio_venta

    def ganancia(self):
        return self.cantidad * (self.producto.precio_venta - self.producto.precio_compra)

    def save(self, *args, **kwargs):
     
        if self.pk is None:  
            if self.cantidad > self.producto.stock:
                raise ValueError("No hay suficiente stock para realizar la venta.")
            self.producto.stock -= self.cantidad
            self.producto.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Venta de {self.cantidad} x {self.producto.nombre}"


class IngresoProducto(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    fecha_ingreso = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk is None:
            self.producto.stock += self.cantidad
            self.producto.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Ingreso de {self.cantidad} x {self.producto.nombre}"
from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta 
from datetime import timedelta,datetime
from django.utils import timezone


SUB_PLANES = [
        ('Bronce', 'Bronce (4 Accesos)'),
        ('Hierro', 'Hierro (8 Accesos)'),
        ('Acero', 'Acero (12 Accesos)'),
        ('Titanio', 'Titanio (Acceso Libre)'),
    ]

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
        ('Pase Diario', 'Pase Diario'), 
    ]
    DURACIONES = [
        ('Mensual', 'Mensual'),
        ('Trimestral', 'Trimestral'),
        ('Anual', 'Anual'),
        ('Semestral', 'Semestral'),
         ('Diario', 'Diario'),  
    ]

    tipo = models.CharField(max_length=20, choices=TIPOS)
    duracion = models.CharField(max_length=20, choices=DURACIONES, default='Mensual')
    sub_plan = models.CharField(max_length=20, choices=SUB_PLANES,null=True, blank=True)
    class Meta:
        unique_together = ('tipo', 'duracion')

    def __str__(self):
        return f"{self.tipo} + Plan {self.duracion}"
    
# --------------------------
# Modelo: Plan Personalizado
# --------------------------
class PlanPersonalizado(models.Model):
    nombre_plan = models.CharField(max_length=100, unique=True)
    accesos_por_mes = models.IntegerField(default=0)
    def __str__(self):
        return self.nombre_plan
    
# --------------------------
# Modelo: Sesiones
# --------------------------
class Sesion(models.Model):
    TIPO_SESION = [
        ('nutricional', 'Asistió Sesión Nutricional'),
        ('kinesiologia', 'Asistió Sesión Kinesiología'),
    ]
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE, related_name="sesiones")
    tipo_sesion = models.CharField(max_length=20, choices=TIPO_SESION)
    fecha = models.DateField()
  
    
    def __str__(self):
        return f"{self.cliente.nombre} - {self.get_tipo_sesion_display()} ({self.fecha})"

# --------------------------
# Modelo: Precios
# --------------------------
class Precios(models.Model):
    TIPOS_PUBLICO = [
        ('Normal', 'Normal'),
        ('Estudiante', 'Estudiante'),
        ('Adulto Mayor', 'Adulto Mayor'),
    ]

    SUB_PLANES = [
        ('Bronce', 'Bronce (4 Accesos)'),
        ('Hierro', 'Hierro (8 Accesos)'),
        ('Acero', 'Acero (12 Accesos)'),
        ('Titanio', 'Titanio (Acceso Libre)'),
    ]

    tipo_publico = models.CharField(max_length=20, choices=TIPOS_PUBLICO)
    sub_plan = models.CharField(max_length=20, choices=SUB_PLANES)
    precio = models.PositiveIntegerField("Precio (CLP)")
    descuento = models.IntegerField(default=0) 
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    precio_final = models.PositiveIntegerField(default=0)
  

    def calcular_precio_final(self):
        return int(self.precio * (1 - self.descuento / 100))

    def save(self, *args, **kwargs):
            self.precio_final = self.calcular_precio_final()
            super().save(*args, **kwargs)

    def __str__(self):
            return f"{self.tipo_publico} - {self.sub_plan}: ${self.precio}"


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

    TIPOS_PUBLICO = [
        ('Normal', 'Normal'),
        ('Estudiante', 'Estudiante'),
        ('AdultoMayor', 'Adulto Mayor'),
    ]

    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    rut = models.CharField(max_length=12, unique=True)
    correo = models.EmailField()
    telefono = models.CharField(max_length=15)
    huella_template = models.BinaryField(null=True, blank=True)
    ultimo_reset_mes = models.DateField(null=True, blank=True)
    mensualidad = models.ForeignKey('Mensualidad', on_delete=models.SET_NULL, null=True, blank=True)
    planes_personalizados = models.ManyToManyField('PlanPersonalizado', blank=True)
    plan_personalizado_activo = models.ForeignKey(
        "PlanPersonalizado", null=True, blank=True, on_delete=models.SET_NULL, related_name="clientes_activos"
    )

    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, null=True, blank=True)
    fecha_inicio_plan = models.DateField(null=True, blank=True)
    fecha_fin_plan = models.DateField(null=True, blank=True)

    tipo_publico = models.CharField(max_length=20, choices=TIPOS_PUBLICO, default='Normal')
    sub_plan = models.CharField(max_length=20, choices=SUB_PLANES, null=True, blank=True)

    accesos_restantes = models.FloatField(default=0)
    precio_asignado = models.PositiveIntegerField(null=True, blank=True)

    duraciones_a_dias = {
        "mensual": 30,
        "trimestral": 90,
        "semestral": 180,
        "anual": 365,
    }

    def asignar_precio(self):
        if self.mensualidad and self.sub_plan:
            precio_obj = Precios.objects.filter(
                tipo_publico=self.mensualidad.tipo, sub_plan=self.sub_plan
            ).first()
            if precio_obj:
                self.precio_asignado = precio_obj.precio
            else:
                self.precio_asignado = None
        else:
            self.precio_asignado = None

    def save(self, *args, **kwargs):
        if isinstance(self.fecha_inicio_plan, datetime):
            self.fecha_inicio_plan = self.fecha_inicio_plan.date()

        if not self.fecha_inicio_plan:
            self.fecha_inicio_plan = timezone.localdate()

        dias_total = 30
        if self.mensualidad:
            key = self.mensualidad.duracion.strip().lower()
            if self.mensualidad.tipo.lower() == 'pase diario':
                dias_total = 1
            else:
                dias_total = self.duraciones_a_dias.get(key, 30)

        # 🔹 Solo asignar fecha_fin_plan si no existe
        if not self.fecha_fin_plan:
            self.fecha_fin_plan = self.fecha_inicio_plan + timedelta(days=dias_total)

        super().save(*args, **kwargs)

    @property
    def ultima_sesion_tipo(self):
            if self.sesiones.exists():
                return self.sesiones.last().tipo_sesion
            return ""

    @property
    def estado_plan(self):
        hoy = timezone.localdate()

        # Pase Diario
        if self.mensualidad and self.mensualidad.tipo.lower() == 'pase diario':
            if not self.fecha_fin_plan or self.fecha_fin_plan < hoy or self.fecha_fin_plan == hoy:
                return 'inactivo'
            else:
                return 'activo'

        # Planes normales
        if self.fecha_fin_plan and self.fecha_fin_plan < hoy:
            return 'vencido'
        elif self.fecha_inicio_plan and self.fecha_inicio_plan > hoy:
            return 'pendiente'
        else:
            return 'activo'
    @property
    def dias_restantes(self):
        hoy = timezone.localdate()

        # Para planes que empiezan en el futuro
        if self.fecha_inicio_plan and self.fecha_inicio_plan > hoy:
            return (self.fecha_inicio_plan - hoy).days

        if self.mensualidad:
            key = self.mensualidad.duracion.strip().lower()
            dias_default = self.duraciones_a_dias.get(key, 30)
            if self.mensualidad.tipo.lower() == "pase diario":
                dias_default = 1
        else:
            dias_default = 30

        vencimiento = self.fecha_fin_plan or (self.fecha_inicio_plan + timedelta(days=dias_default))
        return max((vencimiento - hoy).days, 0)

    def activar_plan(self, fecha_activacion=None, dias_extra=0, forzar=False):
        hoy = timezone.localdate()
        
        if fecha_activacion is None:
            if self.fecha_fin_plan and self.fecha_fin_plan > hoy and not forzar:
                fecha_activacion = self.fecha_fin_plan
            else:
                fecha_activacion = hoy

        dias_total = 30
        if self.mensualidad:
            key = self.mensualidad.duracion.strip().lower()

       
            if self.mensualidad.tipo == "Pase Diario":
                dias_total = 1
            else:
                dias_total = self.duraciones_a_dias.get(key, 30)

        dias_total += dias_extra

        self.fecha_inicio_plan = fecha_activacion
        self.fecha_fin_plan = fecha_activacion + timedelta(days=dias_total)

        # accesos
        if self.sub_plan:
            accesos_dict = {'Bronce': 4, 'Hierro': 8, 'Acero': 12, 'Titanio': 0}
            self.accesos_restantes = accesos_dict.get(self.sub_plan, 0)
        elif self.plan_personalizado_activo:
            self.accesos_restantes = self.plan_personalizado_activo.accesos_por_mes

        self.asignar_precio()
        super().save()

    def __str__(self):
        return f"{self.nombre} {self.apellido} - {self.rut}"


class Asistencia(models.Model):
    TIPO_ASISTENCIA_CHOICES = [
        ("subplan", "Subplan"),
        ("plan_personalizado", "Plan Personalizado"),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    fecha = models.DateTimeField(default=timezone.now)
    tipo_asistencia = models.CharField(
        max_length=20,
        choices=TIPO_ASISTENCIA_CHOICES,
        default="subplan"
    )

    def __str__(self):
        return f"{self.cliente.nombre} - {self.fecha.date()} ({self.tipo_asistencia})"






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
    
class HistorialAccion(models.Model):
    ACCIONES = [
        ('crear', 'Crear'),
        ('editar', 'Editar'),
        ('eliminar', 'Eliminar'),
        ('venta', 'Venta'),
        ('asistencia', 'Asistencia'),
        ('renovar', 'Renovación'),
        ('cambio_plan', 'Cambio de Plan'),
        ('stock', 'Stock'),
    ]

    admin = models.ForeignKey('Admin', on_delete=models.SET_NULL, null=True, blank=True)
    accion = models.CharField(max_length=20, choices=ACCIONES)
    modelo_afectado = models.CharField(max_length=100)
    objeto_id = models.PositiveIntegerField(null=True, blank=True)
    descripcion = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
   
        fecha_local = timezone.localtime(self.fecha)
        admin_nombre = f"{self.admin.nombre} {self.admin.apellido}" if self.admin else "Sin admin"
        return f"{fecha_local.strftime('%d-%m-%Y %H:%M:%S')} - {admin_nombre} - {self.accion} - {self.modelo_afectado}"

    @property
    def fecha_chile(self):
 
        return timezone.localtime(self.fecha)

from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta 
from datetime import timedelta,datetime, time
from django.utils import timezone
from django.db.models import Sum
from django.db.models import Q, UniqueConstraint
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
    ROLES = [
        ('Administrador', 'Administrador'),
        ('Kinesiologo', 'Kinesiologo'),
        ('Nutricionista', 'Nutricionista'),
    ]

    nombreUsuario = models.CharField(max_length=50, default="usuario")
    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    rut = models.CharField(max_length=12, unique=True)
    password = models.CharField(max_length=128)
    profesion = models.CharField(max_length=20, choices=ROLES, default='Administrador')  

    def __str__(self):
        return f'{self.nombre} {self.apellido} ({self.profesion})'



# --------------------------
# Modelo: Mensualidad (básico)
# --------------------------
class Mensualidad(models.Model):
    TIPOS = [
            ('Estudiante', 'Estudiante'),
            ('Normal', 'Normal'),
            ('Adulto Mayor', 'Adulto Mayor'),
            ('Pase Diario', 'Pase Diario'),
            ('Gratis', 'Gratis'),
            ('Plan AM Estudiante', 'Plan AM (Estudiante)'),
            ('Plan AM Normal', 'Plan AM (Normal)'),
            ('Plan AM Adulto Mayor', 'Plan AM (Adulto Mayor)'),
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
    coach = models.ForeignKey(
        'NombresProfesionales', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="planes_asignados"
    )

    def __str__(self):
        coach_str = f" - Coach: {self.coach.nombre}" if self.coach else ""
        return f"{self.nombre_plan}{coach_str}"

    
# --------------------------
# Modelo: Sesiones
# --------------------------

class Sesion(models.Model):
    TIPO_SESION = [
        ('nutricional', 'Asistió Sesión Nutricional'),
        ('kinesiologia', 'Asistió Sesión Kinesiología'),
        ('masajista', 'Asistió Sesión Masajista'),
    ]

    # Cliente interno
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE, null=True, blank=True, related_name="sesiones")
    # Cliente externo
    cliente_externo = models.ForeignKey('ClienteExterno', on_delete=models.CASCADE, null=True, blank=True, related_name="sesiones_externas")

    tipo_sesion = models.CharField(max_length=20, choices=TIPO_SESION)
    fecha = models.DateField(default=timezone.now)
    profesional = models.ForeignKey('NombresProfesionales', on_delete=models.SET_NULL, null=True, blank=True, related_name='sesiones')

    def __str__(self):
        cliente_nombre = None
        if self.cliente:
            cliente_nombre = f"{self.cliente.nombre} {self.cliente.apellido}"
        elif self.cliente_externo:
            cliente_nombre = f"{self.cliente_externo.nombre} {self.cliente_externo.apellido}"
        else:
            cliente_nombre = "Cliente desconocido"
        profesional_str = f" - {self.profesional.nombre}" if self.profesional else ""
        return f"{cliente_nombre} - {self.get_tipo_sesion_display()} ({self.fecha}){profesional_str}"



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
        ('Pase Diario', 'Pase Diario'),
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
        ('inactivo', 'Inactivo'),
    ]

    TIPOS_PUBLICO = [
        ('Normal', 'Normal'),
        ('Estudiante', 'Estudiante'),
        ('AdultoMayor', 'Adulto Mayor'),
    ]

    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    rut = models.CharField(max_length=15, unique=True)
    correo = models.EmailField()
    telefono = models.CharField(max_length=15)
    ultimo_reset_mes = models.DateField(null=True, blank=True)

    mensualidad = models.ForeignKey('Mensualidad', on_delete=models.SET_NULL, null=True, blank=True)
    planes_personalizados = models.ManyToManyField('PlanPersonalizado', blank=True)
    plan_personalizado_activo = models.ForeignKey(
        "PlanPersonalizado", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="clientes_activos"
    )

    coach_asignado = models.ForeignKey(
        'NombresProfesionales',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clientes_asignados"
    )

    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, null=True, blank=True)
    fecha_inicio_plan = models.DateField(null=True, blank=True)
    fecha_fin_plan = models.DateField(null=True, blank=True)
    tipo_publico = models.CharField(max_length=20, choices=TIPOS_PUBLICO, default='Normal')
    sub_plan = models.CharField(max_length=20, choices=SUB_PLANES, null=True, blank=True)
    
    accesos_subplan_restantes = models.FloatField(default=0)
    accesos_personalizados_restantes = models.FloatField(default=0)
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
            from core.models import Precios
            precio_obj = Precios.objects.filter(
                tipo_publico=self.mensualidad.tipo,
                sub_plan=self.sub_plan
            ).first()
            if precio_obj:
                self.precio_asignado = precio_obj.precio
            else:
                self.precio_asignado = None
        else:
            self.precio_asignado = None

    @property
    def estado_plan(self):
        hoy = timezone.localdate()

        # Pase Diario
        if self.mensualidad and self.mensualidad.tipo.lower() == 'pase diario':
            if not self.fecha_fin_plan or self.fecha_fin_plan < hoy:
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
        tolerancia_vencido = 1

        # Duración base del plan
        dias_total = 30
        if self.mensualidad:
            key = self.mensualidad.duracion.strip().lower()
            if self.mensualidad.tipo.lower() == "pase diario":
                dias_total = 1
            else:
                dias_total = self.duraciones_a_dias.get(key, 30)

        # === Determinar si se extiende o reinicia ===
        if (
            self.fecha_fin_plan
            and (self.fecha_fin_plan + timedelta(days=tolerancia_vencido)) >= hoy
            and not forzar
        ):
            #  Extiende plan activo (no vencido)
            self.fecha_inicio_plan = self.fecha_inicio_plan or hoy
            self.fecha_fin_plan = self.fecha_fin_plan + timedelta(days=dias_total + dias_extra)
            tipo_accion = "extensión"
        else:
            #  Reinicia plan vencido o forzado
            fecha_activacion = fecha_activacion or hoy
            self.fecha_inicio_plan = fecha_activacion
            self.fecha_fin_plan = fecha_activacion + timedelta(days=dias_total + dias_extra)
            tipo_accion = "reinicio"

        # === Asignar accesos según subplan o plan personalizado ===
        if self.sub_plan:
            accesos_dict = {"Bronce": 4, "Hierro": 8, "Acero": 12, "Titanio": 0}
            nuevos_accesos = accesos_dict.get(self.sub_plan, 0)

            if self.sub_plan == "Titanio":
                # Titanio tiene acceso ilimitado
                self.accesos_subplan_restantes = float("inf")
            else:
                if tipo_accion == "extensión" and not forzar:
                    #  Sumar accesos (acumulación)
                    self.accesos_subplan_restantes = (self.accesos_subplan_restantes or 0) + nuevos_accesos
                else:
                    #  Reinicio: nuevo ciclo con accesos frescos
                    self.accesos_subplan_restantes = nuevos_accesos

            # Reiniciar personalizados
            self.accesos_personalizados_restantes = 0

        elif self.plan_personalizado_activo:
            # Plan personalizado
            self.accesos_personalizados_restantes = self.plan_personalizado_activo.accesos_por_mes
            self.accesos_subplan_restantes = 0

        # === Actualizar campo general de accesos ===
        self.accesos_restantes = max(self.accesos_subplan_restantes or 0, self.accesos_personalizados_restantes or 0)

        # === Asignar precio actualizado ===
        self.asignar_precio()

        # === Guardar cambios ===
        super().save()

        return tipo_accion

    class Meta:
        ordering = ["nombre", "apellido"]

    def __str__(self):
        return f"{self.nombre} {self.apellido} - {self.rut}" 
    
class Asistencia(models.Model):
    TIPO_ASISTENCIA_CHOICES = [
        ("subplan", "Subplan"),
        ("plan_personalizado", "Plan Personalizado"),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    plan_personalizado = models.ForeignKey(
        "PlanPersonalizado", null=True, blank=True, on_delete=models.SET_NULL
    )
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
        # Suma todas las cantidades vendidas en el modelo Venta para este producto
        ventas_total = self.venta_set.aggregate(total=Sum('cantidad'))['total']
        return ventas_total or 0

    def ganancia_real(self):
        return self.cantidad_vendida() * (self.precio_venta - self.precio_compra)

    def __str__(self):
        return f"{self.nombre} (Stock: {self.stock})"


class Venta(models.Model):
    METODOS_PAGO = [
        ('Efectivo', 'Efectivo'),
        ('Debito', 'Débito'),
        ('Credito', 'Crédito'),
        ('Transferencia', 'Transferencia'),
    ]

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO) 
    fecha = models.DateTimeField(auto_now_add=True) 

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
        return f"Venta de {self.cantidad} x {self.producto.nombre} ({self.metodo_pago})"


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





class NombresProfesionales(models.Model):
            NombreProfesion = [
            ('Kinesiologo', 'Kinesiologo'),
            ('Nutricionista', 'Nutricionista'),
            ('Coach', 'Coach'),
            ('Masajista', 'Masajista')
        ]
            nombre = models.CharField(max_length=50)
            apellido = models.CharField(max_length=50)
            profesion = models.CharField(max_length=20, choices=NombreProfesion) 
            def __str__(self):
                return self.nombre
    
class ClienteExterno(models.Model):
            nombre = models.CharField(max_length=50)
            apellido = models.CharField(max_length=50)
            rut = models.CharField(max_length=15, unique=True)
            tipo_atencion = models.CharField(
                max_length=20,
                choices=[
                    ('Kinesiología', 'Kinesiología'),
                    ('Nutrición', 'Nutrición'),
                    ('Masajista', 'Masajista'),
                    ('Ambos', 'Ambos'),
                ]
            )

            def __str__(self):
                return f"{self.nombre} {self.apellido} ({self.rut})"
            




class AgendaProfesional(models.Model):
    BOX_CHOICES = [
        ('Box 1', 'Box 1 - Kinesiología'),
        ('Box 2', 'Box 2 - Nutrición'),
    ]

    profesional = models.ForeignKey('NombresProfesionales', on_delete=models.CASCADE, related_name='agendas')
    box = models.CharField(max_length=20, choices=BOX_CHOICES)
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    disponible = models.BooleanField(default=True)
    cliente = models.ForeignKey('Cliente', on_delete=models.SET_NULL, null=True, blank=True)
    cliente_externo = models.ForeignKey('ClienteExterno', on_delete=models.SET_NULL, null=True, blank=True)
    comentario = models.TextField(blank=True, null=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['fecha', 'hora_inicio']
  

    def __str__(self):
        return f"{self.box} - {self.profesional.nombre} {self.profesional.apellido} ({self.fecha} {self.hora_inicio})"

    def save(self, *args, **kwargs):
        profesion = getattr(self.profesional, 'profesion', '').strip().lower()


        if profesion in ['kinesiólogo', 'kinesiologo', 'nutricionista']:
            existe = AgendaProfesional.objects.filter(
                box=self.box,
                fecha=self.fecha,
                hora_inicio=self.hora_inicio
            ).exclude(id=self.id).exists()

            if existe:
                raise ValueError(
                    f"El {self.box} ya está ocupado en esa fecha y hora ({self.fecha} {self.hora_inicio})."
                )

        super().save(*args, **kwargs)

    def crear_sesion_si_corresponde(self):
        if not self.disponible and (self.cliente or self.cliente_externo):
            tipo = 'nutricional' if self.box == 'Box 1' else 'kinesiologia'

            Sesion.objects.create(
                cliente=self.cliente,
                cliente_externo=self.cliente_externo,
                tipo_sesion=tipo,
                fecha=self.fecha,
                profesional=self.profesional
            )

    def registrar_accion(self, accion, admin=None):
        descripcion = f"{accion.capitalize()} agenda: {self.box} {self.fecha} {self.hora_inicio}-{self.hora_fin}"
        HistorialAccion.objects.create(
            admin=admin,
            accion=accion,
            modelo_afectado='AgendaProfesional',
            objeto_id=self.id,
            descripcion=descripcion
        )
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
        ('Efectivo', 'Efectivo'),
        ('Debito', 'Débito'),
        ('Credito', 'Crédito'),
        ('Transferencia', 'Transferencia'),
    ]

    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    rut = models.CharField(max_length=12, unique=True)
    correo = models.EmailField()
    telefono = models.CharField(max_length=15)

    mensualidad = models.ForeignKey(Mensualidad, on_delete=models.SET_NULL, null=True, blank=True)
    plan_personalizado = models.ForeignKey(PlanPersonalizado, on_delete=models.SET_NULL, null=True, blank=True)
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, null=True, blank=True)
    fecha_inicio_plan = models.DateField(default=timezone.now, null=True, blank=True)
    fecha_fin_plan = models.DateField(null=True, blank=True)  

    def calcular_vencimiento(self):
        if self.fecha_fin_plan:
            return self.fecha_fin_plan
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
from django.contrib import admin
from .models import Cliente, Mensualidad, PlanPersonalizado,Admin,Producto,Venta,Asistencia,Precios

admin.site.register(Cliente)
admin.site.register(Mensualidad)
admin.site.register(PlanPersonalizado)
admin.site.register(Admin)
admin.site.register(Producto)
admin.site.register(Venta)
admin.site.register(Asistencia)
admin.site.register(Precios)
from datetime import timedelta
from django.utils import timezone
from core.models import Cliente

def actualizar_accesos_mensuales():
    hoy = timezone.now().date()
    
    accesos_dict = {
        'Bronce': 4,
        'Hierro': 8,
        'Acero': 12,
    }

    for cliente in Cliente.objects.filter(sub_plan__in=accesos_dict.keys()):
        if not cliente.ultimo_reset_mes:
            cliente.ultimo_reset_mes = hoy
            cliente.save()
            continue

        dias_transcurridos = (hoy - cliente.ultimo_reset_mes).days

        if dias_transcurridos >= 30:
            nuevos_accesos = accesos_dict.get(cliente.sub_plan, 0)
            cliente.accesos_restantes += nuevos_accesos

            cliente.ultimo_reset_mes = hoy
            cliente.save()

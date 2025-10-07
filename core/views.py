
import re
from time import time
from django.shortcuts import render, redirect
from django.utils import timezone
from psycopg import logger
from pyparsing import wraps
from .models import Cliente, Asistencia, Admin, Mensualidad, PlanPersonalizado, Precios,Producto, Sesion, Venta
from .forms import ClienteForm, DescuentoUpdateForm, PrecioUpdateForm,ProductoForm
from datetime import date, datetime, time,timedelta
from dateutil.relativedelta import relativedelta
import pytz
from django.utils.timezone import localdate
from django.db.models import F, ExpressionWrapper, FloatField
import json
from django.db.models.functions import TruncMonth
from django.db.models import Count, Sum, Avg, F, Q, ExpressionWrapper, FloatField
from django.utils.timezone import now
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseRedirect, HttpResponseServerError
from django.http import JsonResponse
from django.contrib import messages
import calendar
from collections import defaultdict
from django.template.loader import render_to_string
import locale
from django.core.mail import EmailMessage
from xhtml2pdf import pisa
import io
from django.core.paginator import Paginator
from .utils import validar_rut, validar_correo, validar_telefono

from .models import HistorialAccion

def registrar_historial(admin, accion, modelo, objeto_id=None, descripcion=""):
    HistorialAccion.objects.create(
        admin=admin,
        accion=accion,
        modelo_afectado=modelo,
        objeto_id=objeto_id,
        descripcion=descripcion
    )

def safe_view(view_func):

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error en {view_func.__name__}: {str(e)}", exc_info=True)
            return HttpResponseServerError("Ha ocurrido un error inesperado. Informa el problema al desarrollador :( )")
    return wrapper

# ===========================
# LOGIN PERSONALIZADO (con Admin)
# ===========================
@safe_view
def login_admin(request):
    if request.method == 'POST':
        rut_input = request.POST.get('rut', '')
        password = request.POST.get('password', '')

    
        rut_limpio = rut_input.replace('.', '').replace('-', '').upper()

     
        admin = Admin.objects.filter(rut__iexact=rut_limpio, password=password).first()

        if admin:
            request.session['admin_id'] = admin.id
            return redirect('index')
        else:
            request.session['login_error'] = 'Credenciales inválidas'
            return redirect('login')  
    else:
        error = request.session.pop('login_error', None)
        return render(request, 'core/home.html', {'error': error})

def logout_admin(request):
    request.session.flush()
    return redirect('login')



def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        admin_id = request.session.get('admin_id')
        if not admin_id:
            return redirect('login')
        try:
            request.admin = Admin.objects.get(id=admin_id)
        except Admin.DoesNotExist:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper



@admin_required
def index(request):
    return render(request, 'core/index.html')

@admin_required
def registro_cliente(request):
    mensaje = None
    cliente_creado = None

    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente_creado = form.save(commit=False)
            accesos_dict = {
                'Bronce': 4,
                'Hierro': 8,
                'Acero': 12,
                'Titanio': 9999  # acceso libre
            }
            cliente_creado.accesos_restantes = accesos_dict.get(cliente_creado.sub_plan, 0)
            cliente_creado.save()
            registrar_historial(
            request.admin,
            "crear",
            "Cliente",
            cliente_creado.id,
            f"Creó cliente {cliente_creado.nombre} {cliente_creado.apellido}"
            )      
            form.save_m2m()
            
            # Enviar contrato por correo
            enviar_contrato_correo(cliente_creado)
            
            mensaje = f"✅ El Cliente {cliente_creado.nombre} {cliente_creado.apellido} ha sido creado correctamente."
            form = ClienteForm()
    else:
        form = ClienteForm()

    return render(request, 'core/RegistroCliente.html', {
        'form': form,
        'mensaje': mensaje,
        'cliente': cliente_creado,
    })


def enviar_contrato_correo(cliente):

    try:
        locale.setlocale(locale.LC_TIME, "es_ES.utf8")
    except:
        pass

    hoy = date.today()
    fecha_envio = hoy.strftime("%d de %B de %Y") 

    html = render_to_string('core/contrato_gym.html', {
        'cliente': cliente,
        'fecha_envio': fecha_envio
    })

    pdf_file = io.BytesIO()
    pisa_status = pisa.CreatePDF(html.encode('utf-8'), dest=pdf_file, encoding='utf-8')
    if pisa_status.err:
        return False

    pdf_file.seek(0)
    nombre_pdf = f'Contrato_{cliente.nombre}_{cliente.apellido}.pdf'

    correo = EmailMessage(
        subject='📄 Contrato de Suscripción - Bunker Gym',
        body=f'Hola {cliente.nombre},\n\nAdjunto encontrarás tu contrato de suscripción al gimnasio.\n\n¡Bienvenido a Bunker Gym! 💪',
        from_email='bunkergymchile@gmail.com',
        to=[cliente.correo],
    )
    correo.attach(nombre_pdf, pdf_file.read(), 'application/pdf')
    correo.send()

    return True

@admin_required
def activar_plan_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == 'POST':
        fecha_activacion = request.POST.get('fecha_activacion')
        if fecha_activacion:
            fecha_activacion = timezone.datetime.strptime(fecha_activacion, '%Y-%m-%d').date()
        else:
            fecha_activacion = timezone.localdate()

        cliente.activar_plan(fecha_activacion)
        messages.success(request, f'Plan activado para {cliente.nombre} desde {fecha_activacion}')
        return redirect('listaClientes')

    return render(request, 'core/activarPlan.html', {
        'cliente': cliente,
        'fecha_hoy': timezone.localdate()
    })


@admin_required
def asistencia_cliente(request):
    contexto = {
        "mostrar_modal": False,
        "planes_personalizados": None,
        "plan_libre": False,
        "plan_full": False,
        "rut_invalido": False,
        "asistencia_ya_registrada": False,
        "plan_vencido": False,
        "sin_accesos": False,
        "pase_diario_inactivo": False,
    }

    if request.method == "POST":
        rut = request.POST.get("rut")
        confirmar = request.POST.get("confirmar")

        cliente = Cliente.objects.filter(rut=rut).first()
        if not cliente:
            contexto["rut_invalido"] = True
            return render(request, "core/AsistenciaCliente.html", contexto)

        hoy = timezone.localdate()

        # Bloquear si es Pase Diario inactivo
        if (
            cliente.mensualidad
            and cliente.mensualidad.tipo.lower() == "pase diario"
            and cliente.estado_plan == "inactivo"
        ):
            contexto["pase_diario_inactivo"] = True
            contexto["cliente"] = cliente
            return render(request, "core/AsistenciaCliente.html", contexto)

        # Validar plan vencido
        if cliente.estado_plan == "vencido":
            contexto["plan_vencido"] = True
            return render(request, "core/AsistenciaCliente.html", contexto)

        # Activar plan pendiente
        if cliente.estado_plan == "pendiente":
            if not cliente.fecha_inicio_plan or cliente.fecha_inicio_plan > hoy:
                cliente.activar_plan(fecha_activacion=hoy, forzar=True)

        # Manejo de planes personalizados
        if cliente.planes_personalizados.exists():
            if cliente.planes_personalizados.count() > 1 and not confirmar:
                contexto["planes_personalizados"] = cliente.planes_personalizados.all()
                contexto["cliente"] = cliente
                return render(request, "core/AsistenciaCliente.html", contexto)

            if confirmar:
                plan_id = request.POST.get("plan_personalizado")
                cliente.plan_personalizado_activo = cliente.planes_personalizados.filter(id=plan_id).first()
            else:
                cliente.plan_personalizado_activo = cliente.planes_personalizados.first()
            cliente.save()
        else:
            cliente.plan_personalizado_activo = None
            cliente.save()

        plan_activo = cliente.plan_personalizado_activo
        plan_libre = False
        plan_full = False

        # Detectar si plan es libre o full
        if plan_activo:
            if plan_activo.nombre_plan in ["Plan libre semi personalizado", "Plan libre personalizado"]:
                plan_libre = True
            elif plan_activo.accesos_por_mes == 0:
                plan_full = True

        accesos_restantes_subplan = None
        accesos_restantes_personalizado = None
        tipo_asistencia = None

        if plan_activo and (plan_activo.accesos_por_mes > 0 or plan_libre or plan_full):
                usados_mes_personalizado = Asistencia.objects.filter(
                    cliente=cliente,
                    fecha__date__month=hoy.month,
                    fecha__date__year=hoy.year,
                    tipo_asistencia="plan_personalizado"
                ).count()
                if plan_libre or plan_full:
                    accesos_restantes_personalizado = float("inf")
                else:
                    accesos_restantes_personalizado = max(plan_activo.accesos_por_mes - usados_mes_personalizado, 0)
                    accesos_restantes_personalizado = int(accesos_restantes_personalizado)
                tipo_asistencia = "plan_personalizado"

            # Calcular accesos SubPlan
        usados_subplan = 0  # inicializar para evitar UnboundLocalError
        if cliente.sub_plan and not tipo_asistencia:
                if cliente.sub_plan == "Titanio" or (cliente.mensualidad and cliente.mensualidad.tipo == "Gratis + Plan Mensual"):
                    accesos_restantes_subplan = float("inf")
                else:
                    accesos_dict = {"Bronce": 4, "Hierro": 8, "Acero": 12}
                    usados_subplan = Asistencia.objects.filter(
                        cliente=cliente,
                        fecha__date__gte=cliente.fecha_inicio_plan,
                        fecha__date__lte=cliente.fecha_fin_plan,
                        tipo_asistencia="subplan"
                    ).count()
                    accesos_calculados = max((cliente.accesos_restantes or 0) - usados_subplan, 0)
                    accesos_restantes_subplan = int(accesos_calculados)
                tipo_asistencia = "subplan"
        # Guardar accesos restantes
        if tipo_asistencia == "plan_personalizado" and accesos_restantes_personalizado is not None:
            cliente.accesos_restantes = accesos_restantes_personalizado
        elif tipo_asistencia == "subplan" and accesos_restantes_subplan is not None:
            cliente.accesos_restantes = accesos_restantes_subplan
        cliente.save()

        # Verificar accesos disponibles
        accesos_disponibles = False
        if (
            plan_libre
            or plan_full
            or cliente.sub_plan == "Titanio"
            or (cliente.mensualidad and cliente.mensualidad.tipo.lower() == "pase diario")
            or (cliente.mensualidad and cliente.mensualidad.tipo == "Gratis + Plan Mensual")
        ):
            accesos_disponibles = True
        elif cliente.accesos_restantes > 0:
            accesos_disponibles = True

        if not accesos_disponibles:
            contexto["sin_accesos"] = True
            contexto["cliente"] = cliente
            return render(request, "core/AsistenciaCliente.html", contexto)

        # Verificar asistencia del día
        if Asistencia.objects.filter(cliente=cliente, fecha__date=hoy).exists():
            contexto["asistencia_ya_registrada"] = True
            contexto["cliente"] = cliente
            return render(request, "core/AsistenciaCliente.html", contexto)

        # Registrar asistencia
        Asistencia.objects.create(cliente=cliente, tipo_asistencia=tipo_asistencia or "subplan")
        registrar_historial(
            request.admin,
            "asistencia",
            "Cliente",
            cliente.id,
            f"Registró asistencia de {cliente.nombre} {cliente.apellido}"
        )

        if cliente.mensualidad and cliente.mensualidad.tipo.lower() == "pase diario":
            cliente.fecha_fin_plan = hoy
            cliente.save()

        # Si es Gratis + Plan Mensual, mostrar en el modal como Titanio
        sub_plan_para_modal = cliente.sub_plan
        if cliente.mensualidad and cliente.mensualidad.tipo == "Gratis + Plan Mensual":
            sub_plan_para_modal = "Titanio (por plan Gratis + Plan Mensual)"

        contexto.update({
            "mostrar_modal": True,
            "cliente": cliente,
            "vencimiento_plan": cliente.fecha_fin_plan,
            "plan_libre": plan_libre,
            "plan_full": plan_full,
            "accesos_restantes_subplan": accesos_restantes_subplan,
            "accesos_restantes_personalizado": accesos_restantes_personalizado,
            "sub_plan_mostrar": sub_plan_para_modal,
        })

        return render(request, "core/AsistenciaCliente.html", contexto)

    return render(request, "core/AsistenciaCliente.html", contexto)
@admin_required
def listaCliente(request):
    hoy = timezone.localdate()
    asistencias_hoy = Asistencia.objects.filter(
        fecha__date=hoy
    ).select_related('cliente').order_by('-fecha')

    datos_clientes = []
    zona_chile = pytz.timezone('America/Santiago')

    for asistencia in asistencias_hoy:
        cliente = asistencia.cliente
        fecha_chilena = asistencia.fecha.astimezone(zona_chile)

        datos_clientes.append({
            'cliente': cliente,
            'hora_ingreso': fecha_chilena.strftime('%H:%M:%S'),
            'tipo_plan': cliente.mensualidad.tipo if cliente.mensualidad else (
                cliente.plan_personalizado_activo.nombre_plan if cliente.plan_personalizado_activo else '—'
            ),
            'vencimiento_plan': f"{cliente.dias_restantes} días restantes" if cliente.fecha_inicio_plan else '—',
        })

    return render(request, 'core/listaCliente.html', {'datos_clientes': datos_clientes})


@admin_required
def listaCliente_json(request):
    hoy = timezone.localdate()
    asistencias_hoy = Asistencia.objects.filter(
        fecha__date=hoy
    ).select_related('cliente').order_by('-fecha')
    zona_chile = pytz.timezone('America/Santiago')

    datos_clientes = []
    for asistencia in asistencias_hoy:
        cliente = asistencia.cliente
        fecha_chilena = asistencia.fecha.astimezone(zona_chile)

        datos_clientes.append({
            'nombre': f"{cliente.nombre} {cliente.apellido}",
            'rut': cliente.rut,
            'hora_ingreso': fecha_chilena.strftime('%H:%M:%S'),
            'tipo_plan': cliente.mensualidad.tipo if cliente.mensualidad else (
                cliente.plan_personalizado_activo.nombre_plan if cliente.plan_personalizado_activo else '—'
            ),
            'vencimiento_plan': f"{cliente.dias_restantes} días restantes" if cliente.fecha_inicio_plan else '—',
        })

    return JsonResponse({'datos_clientes': datos_clientes})

@admin_required
def renovarCliente(request):
    rut_buscado = request.POST.get('rut') or request.GET.get('rut', '')
    cliente_renovado = None

    # Procesar renovación por POST
    if request.method == 'POST' and 'renovar_rut' in request.POST:
        rut_renovar = request.POST.get('renovar_rut')
        metodo_pago = request.POST.get('metodo_pago')
        nuevo_plan_id = request.POST.get('nuevo_plan')
        nuevo_sub_plan = request.POST.get('nuevo_sub_plan')

        cliente_renovado = Cliente.objects.filter(rut=rut_renovar).first()
        if not cliente_renovado:
            messages.error(request, "Cliente no encontrado.")
            return redirect("renovarCliente")

        cliente_renovado.metodo_pago = metodo_pago
        plan_anterior = cliente_renovado.mensualidad_id

        # Asignar nuevo plan si hay
        if nuevo_plan_id:
            mensualidad_obj = Mensualidad.objects.get(pk=nuevo_plan_id)
            cliente_renovado.mensualidad = mensualidad_obj
            cliente_renovado.tipo_publico = mensualidad_obj.tipo

        # Asignar subplan solo si el nuevo plan no es Pase Diario
        if nuevo_sub_plan and (not cliente_renovado.mensualidad or cliente_renovado.mensualidad.tipo.lower() != "pase diario"):
            cliente_renovado.sub_plan = nuevo_sub_plan
        else:
            cliente_renovado.sub_plan = None

        hoy = timezone.localdate()

        # Pase diario
        if cliente_renovado.mensualidad and cliente_renovado.mensualidad.tipo.lower() == "pase diario":
            cliente_renovado.fecha_inicio_plan = hoy
            cliente_renovado.fecha_fin_plan = hoy + timedelta(days=1)
            cliente_renovado.accesos_restantes = 1
            cliente_renovado.asignar_precio()
            cliente_renovado.save()

            registrar_historial(
                request.admin,
                "renovar",
                "Cliente",
                cliente_renovado.id,
                f"Renovó Pase Diario para {cliente_renovado.nombre} {cliente_renovado.apellido}"
            )

            enviar_contrato_correo(cliente_renovado)

            messages.success(
                request,
                f"El Cliente {cliente_renovado.nombre} {cliente_renovado.apellido} ha renovado su Pase Diario por 1 día."
            )
        else:
            # Plan normal (mensual, titanio, etc.)
            dias_extra = 0
            if cliente_renovado.fecha_fin_plan:
                dias_extra = max((cliente_renovado.fecha_fin_plan - hoy).days, 0)

            cliente_renovado.activar_plan(fecha_activacion=hoy, dias_extra=dias_extra, forzar=False)
            cliente_renovado.save()
            cliente_renovado.asignar_precio()

            registrar_historial(
                request.admin,
                "renovar",
                "Cliente",
                cliente_renovado.id,
                f"Renovó plan {cliente_renovado.sub_plan} para {cliente_renovado.nombre} {cliente_renovado.apellido}"
            )

            enviar_contrato_correo(cliente_renovado)

            messages.success(
                request,
                f"El Cliente {cliente_renovado.nombre} {cliente_renovado.apellido} ha renovado su plan correctamente."
            )

    
        rut_buscado = rut_renovar

    hoy = timezone.localdate()

 
    filtro_tipo = request.GET.get("filtro_tipo", "")
  

    if rut_buscado:
        clientes = Cliente.objects.filter(
            Q(rut__icontains=rut_buscado) |
            Q(nombre__icontains=rut_buscado) |
            Q(apellido__icontains=rut_buscado)
        ).prefetch_related("planes_personalizados", "mensualidad")
    else:
        clientes = Cliente.objects.filter(
            Q(fecha_fin_plan__gte=hoy - timedelta(days=100)) |
            Q(fecha_fin_plan__isnull=True)
        ).prefetch_related("planes_personalizados", "mensualidad")

    # Filtrado adicional según tipo
    if filtro_tipo == "gratis":
        clientes = clientes.filter(mensualidad__tipo="Gratis")
    elif filtro_tipo == "pase_diario":
        clientes = clientes.filter(mensualidad__tipo="Pase Diario")
    elif filtro_tipo == "inscritos":
        clientes = [
            c for c in clientes 
            if c.estado_plan in ("activo", "pendiente") 
            and (not c.mensualidad or c.mensualidad.tipo not in ["Gratis", "Pase Diario"])
     ]
    
    tipos_mensualidad = Mensualidad.objects.all()

    paginator = Paginator(clientes, 20)
    page_number = request.GET.get("page")
    clientes_page = paginator.get_page(page_number)

    return render(request, 'core/renovarCliente.html', {
        'clientes': clientes_page,
        "today": hoy,
        'rut_buscado': rut_buscado,
        'planes_personalizados': PlanPersonalizado.objects.all(),
        'tipos_mensualidad': tipos_mensualidad,
         "filtro_tipo": filtro_tipo,
    })

def registrar_sesion(request):
    if request.method == "POST":
        rut = request.POST.get('rut_cliente')
        tipo_sesion = request.POST.get('tipo_sesion')
        fecha = request.POST.get('fecha_sesion')

        cliente = Cliente.objects.filter(rut=rut).first()
        if not cliente:
            messages.error(request, "Cliente no encontrado.")
        elif cliente.sub_plan != 'Titanio':
            messages.error(request, "Solo clientes con SubPlan Titanio pueden registrar sesiones.")
        elif not tipo_sesion or not fecha:
            messages.error(request, "Debe seleccionar tipo de sesión y fecha.")
        else:
    
            Sesion.objects.create(
                cliente=cliente,
                tipo_sesion=tipo_sesion,
                fecha=fecha
            )

            cliente.ultima_sesion_tipo = tipo_sesion
            cliente.ultima_sesion_fecha = now().date()
            cliente.save()

            messages.success(request, f"Sesión {tipo_sesion} registrada para {cliente.nombre} {cliente.apellido}.")

    return redirect('renovarCliente')


@admin_required
def cambiar_sub_plan(request):
    if request.method == 'POST':
        rut_cliente = request.POST.get('rut_cliente')
        nuevo_sub_plan = request.POST.get('nuevo_sub_plan')

        cliente = Cliente.objects.filter(rut=rut_cliente).first()
        if cliente:
            cliente.sub_plan = nuevo_sub_plan

        
            accesos_dict = {
                'Bronce': 4,
                'Hierro': 8,
                'Acero': 12,
                'Titanio': 9999  # acceso libre
            }
            cliente.accesos_restantes = accesos_dict.get(nuevo_sub_plan, 0)

            cliente.save()
            registrar_historial(
            request.admin,
            "cambio_plan",
            "Cliente",
            cliente.id,
            f"Cambió sub plan a {nuevo_sub_plan} para {cliente.nombre} {cliente.apellido}"
        )
            messages.success(request, f"SubPlan de {cliente.nombre} actualizado a {nuevo_sub_plan}.")

    return redirect(f'{reverse("renovarCliente")}?rut={rut_cliente}')


@admin_required
def historial_cliente(request):
    rut = request.GET.get('rut') or request.POST.get('rut')
    year = request.GET.get('year')
    month = request.GET.get('month')

    zona_chile = pytz.timezone('America/Santiago')
    now = timezone.localtime()

    # Validar año y mes
    try:
        year = int(year)
    except (TypeError, ValueError):
        year = now.year
    try:
        month = int(month)
    except (TypeError, ValueError):
        month = now.month

    # Localización para nombres de meses
    try:
        locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')

    current_month_name = datetime(year, month, 1).strftime('%B').capitalize()

    cliente = None
    rut_invalido = False
    asistencias_dict = {}
    sesiones_dict = {}

    # Generar lista de días del mes para calendario
    first_weekday, num_days = calendar.monthrange(year, month)
    dias_mes = [None] * ((first_weekday + 1) % 7) + list(range(1, num_days + 1))

    if rut:
        try:
            cliente = Cliente.objects.get(rut=rut)

            # Rangos de fechas para el mes
            inicio_mes = datetime(year, month, 1).date()
            fin_mes = datetime(year, month, num_days).date()

            asistencias = Asistencia.objects.filter(
                cliente=cliente,
                fecha__gte=inicio_mes,
                fecha__lte=fin_mes
            ).order_by('fecha')

            asistencias_temp = defaultdict(list)
            for a in asistencias:
                # Si fecha tiene hora (DateTimeField), convertir a hora Chile
                if hasattr(a.fecha, 'hour'):
                    fecha_local = timezone.localtime(a.fecha, zona_chile)
                    dia = fecha_local.day
                    hora = fecha_local.strftime("%H:%M:%S")
                else:  
                    dia = a.fecha.day
                    hora = "Entrada"
                asistencias_temp[dia].append(hora)
            asistencias_dict = dict(asistencias_temp)

            sesiones = Sesion.objects.filter(
                cliente=cliente,
                fecha__gte=inicio_mes,
                fecha__lte=fin_mes
            ).order_by('fecha')

            sesiones_temp = defaultdict(list)
            for s in sesiones:
                dia = s.fecha.day
                tipo = s.get_tipo_sesion_display()
                sesiones_temp[dia].append(tipo)  # solo tipo, sin hora
            sesiones_dict = dict(sesiones_temp)

        except Cliente.DoesNotExist:
            rut_invalido = True

    context = {
        'cliente': cliente,
        'rut_invalido': rut_invalido,
        'dias_mes': dias_mes,
        'current_year': year,
        'current_month': month,
        'current_month_name': current_month_name,
        'asistencias_dict': asistencias_dict,
        'sesiones_dict': sesiones_dict,
        'rut': rut or '',
    }

    # Respuesta AJAX
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html_calendario = ''
        if cliente:
            html_calendario = render_to_string('core/calendario_parcial.html', context, request=request)
        html_cliente = render_to_string('core/cliente_info.html', context, request=request)
        return JsonResponse({
            'calendario': html_calendario,
            'cliente': html_cliente,
            'asistencias': asistencias_dict,
            'sesiones': sesiones_dict,
            'rut_invalido': rut_invalido,
        })

    return render(request, 'core/historial_cliente.html', context)

@admin_required
def modificar_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            # Guardamos solo los campos básicos
            cliente.nombre = form.cleaned_data['nombre'].upper()
            cliente.apellido = form.cleaned_data['apellido'].upper()
            cliente.rut = form.cleaned_data['rut']
            cliente.correo = form.cleaned_data['correo']
            cliente.telefono = form.cleaned_data['telefono']
            cliente.save(update_fields=['nombre','apellido','rut','correo','telefono'])

            registrar_historial(
                request.admin,
                "editar",
                "Cliente",
                cliente.id,
                f"Modificó cliente {cliente.nombre} {cliente.apellido}"
            )
            messages.success(request, "✅ Cliente modificado exitosamente.")
            return redirect('renovarCliente')
        else:
            for error in form.errors.values():
                messages.error(request, f"❌ {error}")

    else:
        form = ClienteForm(instance=cliente)

    return render(request, 'core/modificar_cliente.html', {'cliente': cliente, 'form': form})

@admin_required
def eliminar_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == 'POST':
        cliente.delete()
        registrar_historial(
    request.admin,
    "eliminar",
    "Cliente",
    cliente.id,
    f"Eliminó cliente {cliente.nombre} {cliente.apellido}"
    )   
        messages.success(request, f"🗑️ Cliente eliminado correctamente.")
    else:
        messages.error(request, "Método no permitido.")

    return redirect('renovarCliente')

@admin_required
def agregar_meses_plan(request):
    if request.method == 'POST':
        rut = request.POST.get('rut_cliente')
        meses = int(request.POST.get('meses', 0))

        cliente = Cliente.objects.filter(rut=rut).first()
        if cliente and meses > 0:
            hoy = timezone.now().date()

    
            if cliente.fecha_fin_plan and cliente.fecha_fin_plan > hoy:
                inicio = cliente.fecha_fin_plan
            elif cliente.fecha_inicio_plan and cliente.fecha_inicio_plan > hoy:
                inicio = cliente.fecha_inicio_plan
            else:
                inicio = hoy
                if not cliente.fecha_inicio_plan or cliente.fecha_inicio_plan < hoy:
                    cliente.fecha_inicio_plan = hoy

            nueva_fecha = inicio + relativedelta(months=meses)
            cliente.fecha_fin_plan = nueva_fecha
            cliente.save()

        return redirect('renovarCliente')

@admin_required
def panel_precios(request):
    precios = Precios.objects.all()
    forms_list = []

    if request.method == 'POST':
        action = request.POST.get("action")
        precio_id = request.POST.get("precio_id")
        precio_obj = Precios.objects.get(id=precio_id)

        if action == "update_precio":
            form = PrecioUpdateForm(request.POST, prefix=f"precio_{precio_id}", instance=precio_obj)
            if form.is_valid():
                precio_base = form.cleaned_data["precio"]
                precio_obj.precio = precio_base
                precio_obj.precio_final = int(precio_base * (1 - (precio_obj.descuento or 0) / 100))
                precio_obj.save()
                messages.success(request, f"Precio actualizado para {precio_obj.sub_plan}")

        elif action == "update_descuento":
            form = DescuentoUpdateForm(request.POST, prefix=f"descuento_{precio_id}", instance=precio_obj)
            if form.is_valid():
                descuento = form.cleaned_data["descuento"]
                precio_obj.descuento = descuento
                precio_obj.precio_final = int(precio_obj.precio * (1 - (descuento or 0) / 100))
                precio_obj.save()
                messages.success(request, f"Descuento actualizado para {precio_obj.sub_plan}")

        return redirect("panel_precios")


    for precio in precios:
        form_precio = PrecioUpdateForm(prefix=f"precio_{precio.id}", instance=precio)
        form_descuento = DescuentoUpdateForm(prefix=f"descuento_{precio.id}", instance=precio)
        forms_list.append((precio, form_precio, form_descuento))

    return render(request, "core/panel_precios.html", {"forms_list": forms_list})

@admin_required
def cambiar_tipo_plan_mensual(request):
    if request.method == 'POST':
        rut_cliente = request.POST.get('rut_cliente')
        nuevo_plan_id = request.POST.get('nuevo_plan')

        cliente = Cliente.objects.filter(rut=rut_cliente).first()
        if cliente and nuevo_plan_id:
            cliente.mensualidad_id = nuevo_plan_id
            cliente.save()


        return redirect(f'{reverse("renovarCliente")}?rut={rut_cliente}')
    
@admin_required
def cambiar_planes_personalizados(request):
    if request.method == 'POST':
        rut_cliente = request.POST.get('rut_cliente')
        planes_ids = request.POST.getlist("nuevo_planes_personalizados") 

        cliente = Cliente.objects.filter(rut=rut_cliente).first()  

        if cliente:
            if len(planes_ids) > 2:
                messages.error(request, "Solo puedes elegir máximo 2 planes personalizados.")
            else:
                cliente.planes_personalizados.set(planes_ids)  
                messages.success(request, "Planes personalizados actualizados correctamente.")
        else:
            messages.error(request, "Cliente no encontrado.")
        
    return redirect('renovarCliente')

@admin_required
def renovar_plan_personalizado(request):
    if request.method == 'POST':
        rut_cliente = request.POST.get('rut_cliente')

        try:
            cliente = Cliente.objects.get(rut=rut_cliente)
        except Cliente.DoesNotExist:
            messages.error(request, "Cliente no encontrado.")
            return redirect('renovarCliente')

        if not cliente.planes_personalizados.exists():
            messages.error(request, "El cliente no tiene un plan personalizado asignado.")
            return redirect('renovarCliente')

        hoy = timezone.localdate()
        plan = cliente.planes_personalizados.first()

  
        cliente.accesos_restantes = plan.accesos_por_mes
        cliente.fecha_inicio_plan = hoy
        cliente.fecha_fin_plan = hoy + timedelta(days=30)
        cliente.ultimo_reset_mes = hoy
        cliente.save()

        messages.success(request, f"Plan personalizado renovado para {cliente.nombre} {cliente.apellido}")
        return redirect('renovarCliente')

    return redirect('renovarCliente')

@admin_required

def productos(request):
    productos = Producto.objects.all().order_by("nombre")
    producto_seleccionado = request.session.pop('producto_seleccionado', None)

    return render(request, 'core/productos.html', {
        'productos': productos,
        'producto_seleccionado': producto_seleccionado
    })


@admin_required
def registrar_venta(request):
    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        cantidad = request.POST.get('cantidad')
        metodo_pago = request.POST.get('metodo_pago')

        try:
            cantidad = int(cantidad)
        except (ValueError, TypeError):
            messages.error(request, "⚠️ La cantidad debe ser un número entero.")
            return redirect('productos')

        producto = Producto.objects.filter(id=producto_id).first()
        if not producto:
            messages.error(request, "❌ Producto no encontrado.")
            return redirect('productos')

        if cantidad <= 0:
            messages.error(request, "⚠️ La cantidad debe ser mayor a 0.")
            return redirect('productos')

        if cantidad > producto.stock:
            messages.error(
                request,
                f"❌ No quedan unidades suficientes de '{producto.nombre}'."
            )
            return redirect('productos')

        if metodo_pago not in dict(Venta.METODOS_PAGO).keys():
            messages.error(request, "⚠️ Seleccione un método de pago válido.")
            return redirect('productos')

        # Guardar la venta con método de pago
        Venta.objects.create(
            producto=producto,
            cantidad=cantidad,
            metodo_pago=metodo_pago
        )

        registrar_historial(
            request.admin,
            "venta",
            "Producto",
            producto.id,
            f"Vendió {cantidad} unidades de {producto.nombre} con {metodo_pago}"
        )

        messages.success(
            request,
            f"✅ Venta registrada: {cantidad} unidad(es) de '{producto.nombre}' "
            f"con {metodo_pago}. Stock restante: {producto.stock}"
        )

        request.session['producto_seleccionado'] = producto.id

    return redirect('productos')

@admin_required
def historial_ventas(request):
    ventas = Venta.objects.select_related("producto").order_by("-fecha")
    return render(request, "core/historial_ventas.html", {"ventas": ventas})

@admin_required
def agregar_producto(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            producto = form.save()
            registrar_historial(
                request.admin,
                "crear",
                "Producto",
                producto.id,
                f"Agregó producto {producto.nombre}"
            )
            messages.success(request, 'Producto agregado correctamente.')
            return redirect('productos')
        else:
            messages.error(request, 'Corrige los errores del formulario.')
    else:
        form = ProductoForm()

    return render(request, 'core/agregar_producto.html', {'form': form})


@admin_required
def editar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        precio_compra = request.POST.get('precio_compra')
        precio_venta = request.POST.get('precio_venta')
        stock_inicial = request.POST.get('stock_inicial')
        stock = request.POST.get('stock')

        if not nombre or not precio_compra or not precio_venta or not stock_inicial or not stock:
            messages.error(request, "⚠️ Todos los campos obligatorios deben estar completos.")
        else:
            try:
                producto.nombre = nombre
                producto.descripcion = descripcion
                producto.precio_compra = precio_compra
                producto.precio_venta = precio_venta
                producto.stock_inicial = stock_inicial
                producto.stock = stock
                producto.save()
                registrar_historial(
                    request.admin,
                    "editar",
                    "Producto",
                    producto.id,
                    f"Editó producto {producto.nombre}"
                )
                messages.success(request, "✅ Producto modificado exitosamente.")
                return redirect('productos')
            except Exception as e:
                messages.error(request, f"❌ Error al modificar el producto: {str(e)}")

    return render(request, 'core/editar_producto.html', {'producto': producto})
@admin_required
def eliminar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)

    if request.method == 'POST':
        producto.delete()
        registrar_historial(
        request.admin,
        "eliminar",
        "Producto",
        producto.id,
        f"Eliminó producto {producto.nombre}"
    )
        messages.success(request, "🗑️ Producto eliminado correctamente.")
    else:
        messages.error(request, "Método no permitido.")

    return redirect('productos')

def dashboard(request):
    hoy = localdate()
    inicio_mes = hoy.replace(day=1)

   # Excluir planes Gratis y Diario
    clientes_filtrados = Cliente.objects.exclude(
        Q(mensualidad__tipo="Gratis") | Q(mensualidad__tipo="Pase Diario")
    )

    # Total clientes (sin Gratis ni Diario)
    total_clientes = clientes_filtrados.count()

    # Clientes activos este mes
    clientes_activos_mes = (
            Asistencia.objects
            .filter(
                fecha__gte=inicio_mes,
                cliente__in=clientes_filtrados
            )
            .values('cliente')
            .distinct()
            .count()
        )

    # Clientes nuevos este mes
    clientes_nuevos_mes = clientes_filtrados.filter(
        fecha_inicio_plan__gte=inicio_mes
    ).count()

    # Últimos 6 meses
    seis_meses_antes = hoy - timedelta(days=180)

    # Nuevos clientes por mes
    clientes_mes_qs = (
        Cliente.objects
        .filter(fecha_inicio_plan__gte=seis_meses_antes)
        .annotate(month=TruncMonth('fecha_inicio_plan'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    nuevos_clientes_mes = {item['month'].strftime('%Y-%m'): item['count'] for item in clientes_mes_qs}

    # Clientes por tipo de plan por mes
    clientes_por_plan = (
        Cliente.objects
        .filter(fecha_inicio_plan__gte=seis_meses_antes)
        .annotate(month=TruncMonth('fecha_inicio_plan'))
        .values('month')
        .annotate(
            estudiante_count=Count('id', filter=Q(mensualidad__tipo='Estudiante')),
            normal_count=Count('id', filter=Q(mensualidad__tipo='Normal')),
        )
        .order_by('month')
    )
    clientes_plan_data = {}
    for item in clientes_por_plan:
        month = item['month'].strftime('%Y-%m')
        clientes_plan_data[month] = {
            "estudiante": item['estudiante_count'],
            "normal": item['normal_count'],
        }

    # Últimas 10 ventas
    ultimas_ventas = (
        Venta.objects
        .select_related('producto')
        .order_by('-fecha')[:10]
        .values('fecha', 'producto__nombre', 'cantidad', 'producto__precio_venta')
    )

    # Ranking asistencia
    ranking_asistencia_qs = (
        Asistencia.objects
        .values('cliente__nombre', 'cliente__apellido')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad')[:10]
    )
    ranking_asistencia = [
        {
            "nombre": f"{item['cliente__nombre']} {item['cliente__apellido']}",
            "cantidad": item['cantidad']
        }
        for item in ranking_asistencia_qs
    ]

    # Productos más vendidos
    productos_vendidos_qs = (
        Venta.objects
        .values('producto__nombre')
        .annotate(total_vendidos=Sum('cantidad'))
        .order_by('-total_vendidos')[:10]
    )
    productos_vendidos = [
        {"nombre": item['producto__nombre'], "cantidad": item['total_vendidos']}
        for item in productos_vendidos_qs
    ]

    # Stock actual
    productos = Producto.objects.all().values('nombre', 'stock')

    # Ingresos por ventas por mes
    ventas_mes_qs = (
        Venta.objects
        .filter(fecha__gte=seis_meses_antes)
        .annotate(month=TruncMonth('fecha'))
        .values('month')
        .annotate(
            ingresos=Sum(
                ExpressionWrapper(
                    F('cantidad') * F('producto__precio_venta'),
                    output_field=FloatField()
                )
            )
        )
        .order_by('month')
    )
    ingresos_mes = {item['month'].strftime('%Y-%m'): item['ingresos'] or 0 for item in ventas_mes_qs}

    # Top planes personalizados 
    top_planes_personalizados_qs = (
        Cliente.objects
        .filter(planes_personalizados__isnull=False)
        .values('planes_personalizados__nombre_plan')
        .annotate(total=Count('id'))
        .order_by('-total')[:5]
    )
    top_planes_personalizados = [
        {
            "nombre": item['planes_personalizados__nombre_plan'],
            "total": item['total']
        }
        for item in top_planes_personalizados_qs
    ]

    # Precio promedio por sub-plan
    precios_plan_qs = Precios.objects.values('sub_plan').annotate(promedio=Avg('precio'))
    precios_plan_data = {p['sub_plan']: p['promedio'] for p in precios_plan_qs}

    # Clientes por tipo de público y sub-plan
    clientes_tipo_subplan = {}
    for tipo in Cliente.TIPOS_PUBLICO:
        subplanes_dict = {}
        for sp in Cliente.SUB_PLANES:
            count = Cliente.objects.filter(tipo_publico=tipo[0], sub_plan=sp[0]).count()
            subplanes_dict[sp[0]] = count
        clientes_tipo_subplan[tipo[0]] = subplanes_dict

    # Ingresos estimados por plan
    ingresos_plan_data = {}
    for mensualidad in Mensualidad.objects.all():
        clientes = Cliente.objects.filter(mensualidad=mensualidad)
        ingresos_plan_data[str(mensualidad)] = sum(c.precio_asignado or 0 for c in clientes)

    # Accesos restantes por sub-plan
    accesos_restantes_data = {}
    for sp in Cliente.SUB_PLANES:
        clientes = Cliente.objects.filter(sub_plan=sp[0])
        if clientes.exists():
            accesos_restantes_data[sp[0]] = round(clientes.aggregate(avg=Avg('accesos_restantes'))['avg'],1)
        else:
            accesos_restantes_data[sp[0]] = 0
    # Clientes por plan
    planes_count_qs = (
        Cliente.objects
        .values('mensualidad__tipo')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    planes_count = {p['mensualidad__tipo']: p['total'] for p in planes_count_qs}
    context = {
        "total_clientes": total_clientes,
        "clientes_activos_mes": clientes_activos_mes,
        "clientes_nuevos_mes": clientes_nuevos_mes,
        "nuevos_clientes_mes": json.dumps(nuevos_clientes_mes),
        "ranking_asistencia": json.dumps(ranking_asistencia),
        "productos_vendidos": json.dumps(productos_vendidos),
        "productos": productos,
        "ultimas_ventas": ultimas_ventas,
        "ingresos_mes": json.dumps(ingresos_mes),
        "clientes_plan_data": json.dumps(clientes_plan_data),
        "top_planes_personalizados": json.dumps(top_planes_personalizados),
        "precios_plan_data": json.dumps(precios_plan_data),
        "clientes_tipo_subplan": json.dumps(clientes_tipo_subplan),
        "ingresos_plan_data": json.dumps(ingresos_plan_data),
        "accesos_restantes_data": json.dumps(accesos_restantes_data),
         "planes_count": json.dumps(planes_count),
    }

    return render(request, "core/dashboard.html", context)

def asistencia_kine_nutri(request):
    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        cliente_id = request.POST.get("cliente_id")
        tipo_sesion = request.POST.get("tipo_sesion")

        if cliente_id and tipo_sesion:
            cliente = get_object_or_404(Cliente, id=cliente_id)
            sesion = Sesion.objects.create(
                cliente=cliente,
                tipo_sesion=tipo_sesion,
                fecha=timezone.localdate()
            )
            return JsonResponse({
                "success": True,
                "cliente": f"{cliente.nombre} {cliente.apellido}",
                "tipo": sesion.get_tipo_sesion_display(),
                "fecha": sesion.fecha.strftime("%d/%m/%Y")
            })
        return JsonResponse({"success": False}, status=400)

    clientes = Cliente.objects.all().order_by("nombre")
    sesiones = Sesion.objects.order_by("-fecha")[:10]

    return render(request, "core/asistencia_kine_nutri.html", {
        "clientes": clientes,
        "sesiones": sesiones
    })
# ===========================
# REDIRECCIÓN INICIAL
# ===========================
def home(request):
    return redirect('login')



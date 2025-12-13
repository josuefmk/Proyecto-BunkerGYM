
import logging
import re
from time import time
from timeit import Timer
from django.shortcuts import render, redirect
from django.utils import timezone
from psycopg import logger
from pyparsing import wraps
from .models import AgendaProfesional, Cliente, Asistencia, Admin, Mensualidad, NombresProfesionales, PlanPersonalizado, Precios,Producto, Sesion, Venta, ClienteExterno
from .forms import ClienteExternoForm, ClienteForm, ClientePaseDiarioForm, DescuentoUpdateForm, PrecioUpdateForm,ProductoForm
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
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseServerError
from django.http import JsonResponse
from django.contrib import messages
import calendar
from django.urls import reverse
from collections import defaultdict
from django.template.loader import render_to_string
import locale
from django.core.mail import EmailMessage
from xhtml2pdf import pisa
import io
from django.core.paginator import Paginator
from django.views.decorators.cache import never_cache
from .models import HistorialAccion


def registrar_historial(admin, accion, modelo, objeto_id=None, descripcion=""):
    HistorialAccion.objects.create(
        admin=admin,
        accion=accion,
        modelo_afectado=modelo,
        objeto_id=objeto_id,
        descripcion=descripcion
    )

logger = logging.getLogger(__name__)

def safe_view(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error en {view_func.__name__}: {str(e)}", exc_info=True)
            return HttpResponseServerError("Ha ocurrido un error inesperado. Informa el problema al desarrollador :( )")
    return wrapper

def role_required(allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user_role = None
            username = None

         
            admin_id = request.session.get('admin_id')
            if admin_id:
                try:
                    request.user_obj = get_object_or_404(Admin, id=admin_id)
                    user_role = request.user_obj.profesion.strip().capitalize() if request.user_obj.profesion else None
                    username = request.user_obj.nombre
                except Admin.DoesNotExist:
                    request.session.flush()
                    return redirect('login')
            else:
                
                usuario_id = request.session.get('usuario_id')
                if usuario_id:
                    try:
                        request.user_obj = get_object_or_404(User, id=usuario_id)
                        user_role = request.user_obj.rol.strip().capitalize() if request.user_obj.rol else None
                        username = request.user_obj.nombre
                    except User.DoesNotExist:
                        request.session.flush()
                        return redirect('login')
                else:
                    return redirect('login')

         
            if user_role not in allowed_roles:
                if user_role == 'Administrador':
                    return redirect('index')
                elif user_role in ['Kinesiologo', 'Nutricionista', 'Masajista']:
                    return redirect('agendar_hora_box')
                elif user_role == 'Coach':
                    return redirect('agenda_pf')
                else:
                    request.session.flush()
                    return redirect('login')

            
            response = view_func(request, *args, **kwargs)
            if hasattr(response, 'context_data'):
                response.context_data['username'] = username
            return response

        return wrapper
    return decorator

@safe_view
def login_admin(request):
    if request.method == 'POST':
        rut = request.POST.get('rut', '').replace('.', '').replace('-', '').upper()
        password = request.POST.get('password', '')

        try:
            admin = Admin.objects.get(rut=rut, password=password)
        except Admin.DoesNotExist:
            return render(request, 'core/home.html', {'error': 'Credenciales incorrectas'})

        # Guardar info en sesión
        request.session['admin_id'] = admin.id
        request.session['admin_nombre'] = admin.nombre
        request.session['admin_profesion'] = admin.profesion

        # Redirigir según rol
        if admin.profesion == 'Administrador':
            return redirect('index')
        elif admin.profesion in ['Kinesiologo', 'Nutricionista', 'Masajista']:
            return redirect('agendar_hora_box')
        elif admin.profesion == 'Coach':
            return redirect('agenda_pf')
        else:
            request.session.flush()
            return render(request, 'core/home.html', {'error': 'Rol no reconocido'})

    return render(request, 'core/home.html')


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

        # Si no es admin, lo redirijo a su vista correspondiente
        if request.admin.profesion != 'Administrador':
            return redirect('home')  
        
        return view_func(request, *args, **kwargs)
    return wrapper




@role_required(['Administrador'])
def index(request):

    return render(request, 'core/index.html', {'username': request.user_obj.nombre})

@role_required(['Administrador'])
@never_cache
def registro_cliente(request):
    mensaje = None
    cliente_creado = None
    coaches = NombresProfesionales.objects.filter(profesion='Coach')
    if request.method == 'POST':
        form = ClienteForm(request.POST)
    
        if form.is_valid():
            # Guardar cliente sin commit para modificar campos
            cliente_creado = form.save(commit=False)

     
            accesos_dict = {
                'Bronce': 4,
                'Hierro': 8,
                'Acero': 12,
                'Titanio': 9999  # acceso libre
            }
            cliente_creado.accesos_restantes = accesos_dict.get(cliente_creado.sub_plan, 0)

    
            # Guardar el cliente
            cliente_creado.save()

            form.save_m2m()

            # Registrar historial
            registrar_historial(
                request.user_obj,
                "crear",
                "Cliente",
                cliente_creado.id,
                f"Creó cliente {cliente_creado.nombre} {cliente_creado.apellido}"
            )

            # Enviar contrato por correo
            enviar_contrato_correo(cliente_creado)

            mensaje = f"✅ El Cliente {cliente_creado.nombre} {cliente_creado.apellido} ha sido creado correctamente."
            form = ClienteForm()  # Limpiar formulario
    else:
        form = ClienteForm()

    return render(request, 'core/RegistroCliente.html', {
        'form': form,
        'mensaje': mensaje,
        'cliente': cliente_creado,
        'coaches': coaches 
    })

@role_required(['Administrador'])
@never_cache
def registro_pase_diario(request):
    mensaje = None

    if request.method == 'POST':
        form = ClientePaseDiarioForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            cliente.activar_plan() 
            registrar_historial(
                request.user_obj,
                "crear",
                "Cliente (Pase Diario)",
                cliente.id,
                f"Creó cliente Pase Diario {cliente.nombre} {cliente.apellido}"
            )
            mensaje = f"✅ Cliente {cliente.nombre} {cliente.apellido} registrado como Pase Diario."
            form = ClientePaseDiarioForm()
    else:
        form = ClientePaseDiarioForm()

    return render(request, 'core/registropasediario.html', {
        'form': form,
        'mensaje': mensaje
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

@role_required(['Administrador'])
@never_cache
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

@role_required(['Administrador'])
@never_cache
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

        # === Validar pase diario inactivo ===
        if (
            cliente.mensualidad
            and cliente.mensualidad.tipo.lower() == "pase diario"
            and cliente.estado_plan == "inactivo"
        ):
            contexto["pase_diario_inactivo"] = True
            contexto["cliente"] = cliente
            return render(request, "core/AsistenciaCliente.html", contexto)

        # === Plan vencido ===
        if cliente.estado_plan == "vencido":
            contexto["plan_vencido"] = True
            return render(request, "core/AsistenciaCliente.html", contexto)

        # === Activar plan pendiente si corresponde ===
        if cliente.estado_plan == "pendiente":
            if not cliente.fecha_inicio_plan or cliente.fecha_inicio_plan > hoy:
                cliente.activar_plan(fecha_activacion=hoy, forzar=True)

        # === Renovación mensual en función de la fecha de inicio del plan ===
        if (
            cliente.sub_plan in ["Bronce", "Hierro", "Acero"]
            and cliente.mensualidad
            and cliente.mensualidad.duracion.lower() in ["trimestral", "semestral", "anual"]
            and cliente.fecha_inicio_plan
        ):
            accesos_dict = {"Bronce": 4, "Hierro": 8, "Acero": 12}
            accesos_mensuales = accesos_dict.get(cliente.sub_plan, 0)

            if cliente.ultimo_reset_mes:
                proximo_reset = cliente.ultimo_reset_mes + relativedelta(months=1)
            else:
                proximo_reset = cliente.fecha_inicio_plan + relativedelta(months=1)

            if hoy >= proximo_reset:
                if cliente.estado_plan == "activo":
                    cliente.accesos_subplan_restantes += accesos_mensuales

                cliente.ultimo_reset_mes = hoy
                cliente.save(update_fields=["accesos_subplan_restantes", "ultimo_reset_mes"])

        # === Manejo de planes personalizados ===
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

        if plan_activo:
            if plan_activo.nombre_plan in ["Plan libre semi personalizado", "Plan libre personalizado"]:
                plan_libre = True
            elif plan_activo.accesos_por_mes == 0:
                plan_full = True

        accesos_restantes_personalizado = None
        accesos_restantes_subplan = None
        tipo_asistencia = None

        # === Calcular tipo de asistencia y accesos personalizados ===
        if plan_activo:
            if plan_libre or plan_full:
                tipo_asistencia = "subplan"
                accesos_restantes_personalizado = float("inf")
            else:
                fecha_inicio_conteo = cliente.ultimo_reset_mes or cliente.fecha_inicio_plan
                usados_mes_personalizado = Asistencia.objects.filter(
                    cliente=cliente,
                    fecha__gte=fecha_inicio_conteo,
                    tipo_asistencia="plan_personalizado"
                ).count()
                accesos_restantes_personalizado = max(plan_activo.accesos_por_mes - usados_mes_personalizado, 0)
                tipo_asistencia = "plan_personalizado"

        # === Calcular accesos de subplan ===
        if cliente.sub_plan and not tipo_asistencia:
            if cliente.sub_plan == "Titanio" or (
                cliente.mensualidad and cliente.mensualidad.tipo == "Gratis + Plan Mensual"
            ):
                accesos_restantes_subplan = float("inf")
            else:
                accesos_dict = {"Bronce": 4, "Hierro": 8, "Acero": 12}
                accesos_totales = accesos_dict.get(cliente.sub_plan, 0)

                if (
                    cliente.fecha_inicio_plan == hoy
                    or (cliente.accesos_subplan_restantes and cliente.accesos_subplan_restantes > 0)
                ):
                    accesos_restantes_subplan = cliente.accesos_subplan_restantes
                else:
                    usados_subplan = Asistencia.objects.filter(
                        cliente=cliente,
                        fecha__gte=cliente.fecha_inicio_plan,
                        fecha__lte=cliente.fecha_fin_plan,
                        tipo_asistencia="subplan"
                    ).count()
                    accesos_restantes_subplan = max(accesos_totales - usados_subplan, 0)

                tipo_asistencia = "subplan"

            if tipo_asistencia == "plan_personalizado" and accesos_restantes_personalizado is not None:
                cliente.accesos_personalizados_restantes = accesos_restantes_personalizado
            elif tipo_asistencia == "subplan" and accesos_restantes_subplan is not None:
                cliente.accesos_subplan_restantes = accesos_restantes_subplan

            cliente.accesos_restantes = max(
                cliente.accesos_subplan_restantes or 0,
                cliente.accesos_personalizados_restantes or 0
            )
            cliente.save(update_fields=[
                "accesos_personalizados_restantes",
                "accesos_subplan_restantes",
                "accesos_restantes"
            ])

        # === Verificar accesos disponibles ===
        accesos_disponibles = (
            plan_libre
            or plan_full
            or cliente.sub_plan == "Titanio"
            or (cliente.mensualidad and cliente.mensualidad.tipo.lower() == "pase diario")
            or (cliente.mensualidad and cliente.mensualidad.tipo == "Gratis + Plan Mensual")
            or cliente.accesos_personalizados_restantes > 0
            or cliente.accesos_subplan_restantes > 0
        )

        if not accesos_disponibles:
            contexto["sin_accesos"] = True
            contexto["cliente"] = cliente
            return render(request, "core/AsistenciaCliente.html", contexto)

        # === Evitar doble asistencia el mismo día ===
        inicio_dia = timezone.make_aware(datetime.combine(hoy, time.min))
        fin_dia = timezone.make_aware(datetime.combine(hoy, time.max))
        if Asistencia.objects.filter(cliente=cliente, fecha__range=(inicio_dia, fin_dia)).exists():
            contexto["asistencia_ya_registrada"] = True
            contexto["cliente"] = cliente
            return render(request, "core/AsistenciaCliente.html", contexto)

        # === Validar horario AM ===
        if cliente.mensualidad and cliente.mensualidad.tipo:
            tipo_mensualidad = cliente.mensualidad.tipo.strip().upper()
            if tipo_mensualidad in ["AM ESTUDIANTE", "AM NORMAL", "AM ADULTO MAYOR"]:
                ahora = timezone.localtime().time()
                inicio = time(6, 30)
                fin = time(13, 0)
                if not (inicio <= ahora <= fin):
                    contexto["mensaje_error"] = (
                        "El ingreso de asistencia para su plan solo está permitido entre las 6:30 AM y las 13:00 PM."
                    )
                    contexto["cliente"] = cliente
                    return render(request, "core/AsistenciaCliente.html", contexto)

        # === Registrar asistencia ===
        if not tipo_asistencia and cliente.mensualidad and cliente.mensualidad.tipo.lower() == "pase diario":
            tipo_asistencia = "pase_diario"

        if not tipo_asistencia:
            tipo_asistencia = "subplan"  # valor por defecto

        Asistencia.objects.create(
            cliente=cliente,
            fecha=timezone.now(),
            tipo_asistencia=tipo_asistencia
        )

        # === Descontar accesos ===
        if tipo_asistencia == "subplan":
            if cliente.sub_plan not in ["Titanio"] and cliente.accesos_subplan_restantes > 0:
                cliente.accesos_subplan_restantes -= 1
        elif tipo_asistencia == "plan_personalizado":
            if not plan_libre and not plan_full and cliente.accesos_personalizados_restantes > 0:
                cliente.accesos_personalizados_restantes -= 1
            if cliente.sub_plan not in ["Titanio"] and cliente.accesos_subplan_restantes > 0:
                cliente.accesos_subplan_restantes -= 1
        elif cliente.mensualidad and cliente.mensualidad.tipo.lower() == "pase diario":
            cliente.accesos_subplan_restantes = 0
            cliente.accesos_personalizados_restantes = 0
            cliente.accesos_restantes = 0
            cliente.fecha_fin_plan = hoy

        cliente.accesos_restantes = max(
            cliente.accesos_subplan_restantes or 0,
            cliente.accesos_personalizados_restantes or 0
        )
        cliente.save(update_fields=[
            "accesos_subplan_restantes",
            "accesos_personalizados_restantes",
            "accesos_restantes",
            "fecha_fin_plan"
        ])

        registrar_historial(
            request.user_obj,
            "asistencia",
            "Cliente",
            cliente.id,
            f"Registró asistencia de {cliente.nombre} {cliente.apellido}"
        )

        sub_plan_para_modal = cliente.sub_plan
        if cliente.mensualidad and cliente.mensualidad.tipo == "Gratis + Plan Mensual":
            sub_plan_para_modal = "Titanio (por plan Gratis + Plan Mensual)"

        contexto.update({
            "mostrar_modal": True,
            "cliente": cliente,
            "vencimiento_plan": cliente.fecha_fin_plan,
            "plan_libre": plan_libre,
            "plan_full": plan_full,
            "accesos_restantes_subplan": cliente.accesos_subplan_restantes,
            "accesos_restantes_personalizado": cliente.accesos_personalizados_restantes,
            "sub_plan_mostrar": sub_plan_para_modal,
        })

        return render(request, "core/AsistenciaCliente.html", contexto)

    # === Si es GET ===
    contexto["cliente"] = None
    return render(request, "core/AsistenciaCliente.html", contexto)




@role_required(['Administrador'])
@never_cache
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


@role_required(['Administrador'])
@never_cache
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



@role_required(['Administrador'])
@never_cache
def renovarCliente(request):
    hoy = timezone.localdate()

    rut_buscado = request.POST.get('rut') or request.GET.get('rut', '')
    filtro_tipo = request.GET.get("filtro_tipo", "")
    cliente_renovado = None

    if request.method == "POST" and request.POST.get("accion") == "cambiar_tipo_plan":
        rut_cliente = request.POST.get("rut_cliente")
        nuevo_tipo_id = request.POST.get("nuevo_tipo_plan")

        cliente = Cliente.objects.filter(rut=rut_cliente).first()
        if not cliente:
            messages.error(request, "Cliente no encontrado.")
            return redirect(f"{reverse('renovarCliente')}?rut={rut_buscado}")

        if not nuevo_tipo_id:
            messages.warning(request, "Debe seleccionar un tipo de plan válido.")
            return redirect(f"{reverse('renovarCliente')}?rut={rut_cliente}")

        try:
            nuevo_plan = Mensualidad.objects.get(id=nuevo_tipo_id)
        except Mensualidad.DoesNotExist:
            messages.error(request, "El tipo de plan seleccionado no existe.")
            return redirect(f"{reverse('renovarCliente')}?rut={rut_cliente}")

        plan_anterior = cliente.mensualidad.tipo if cliente.mensualidad else "Sin plan"

        cliente.mensualidad = nuevo_plan
        cliente.tipo_publico = nuevo_plan.tipo
        cliente.save()

        registrar_historial(
            request.user_obj,
            "modificar",
            "Cliente",
            cliente.id,
            f"Cambió tipo de plan de '{plan_anterior}' a '{nuevo_plan.tipo}' para {cliente.nombre} {cliente.apellido}"
        )

        messages.success(
            request,
            f"✅ Se cambió correctamente el tipo de plan del cliente {cliente.nombre} {cliente.apellido}."
        )

        return redirect(f"{reverse('renovarCliente')}?rut={rut_cliente}")

  
    if request.method == 'POST' and 'renovar_rut' in request.POST:
        rut_renovar = request.POST.get('renovar_rut')
        metodo_pago = request.POST.get('metodo_pago')
        nuevo_plan_id = request.POST.get('nuevo_plan')
        nuevo_sub_plan = request.POST.get('nuevo_sub_plan')

        cliente_renovado = Cliente.objects.filter(rut=rut_renovar).first()
        if not cliente_renovado:
            messages.error(request, "Cliente no encontrado.")
            return redirect(f"{reverse('renovarCliente')}?rut={rut_buscado}")

        cliente_renovado.metodo_pago = metodo_pago

        # Cambiar plan si hay nuevo
        if nuevo_plan_id:
            mensualidad_obj = Mensualidad.objects.get(pk=nuevo_plan_id)
            cliente_renovado.mensualidad = mensualidad_obj
            cliente_renovado.tipo_publico = mensualidad_obj.tipo

        # Subplan
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
                request.user_obj,
                "renovar",
                "Cliente",
                cliente_renovado.id,
                f"Renovó Pase Diario para {cliente_renovado.nombre} {cliente_renovado.apellido}"
            )

            enviar_contrato_correo(cliente_renovado)

            messages.success(
                request,
                f"El Cliente {cliente_renovado.nombre} {cliente_renovado.apellido} ha renovado su Pase Diario."
            )

        else:
            tipo_accion = cliente_renovado.activar_plan(forzar=False)
            cliente_renovado.save()
            cliente_renovado.asignar_precio()

            registrar_historial(
                request.user_obj,
                "renovar",
                "Cliente",
                cliente_renovado.id,
                f"{'Extendió' if tipo_accion == 'extensión' else 'Reinició'} plan {cliente_renovado.sub_plan} para {cliente_renovado.nombre} {cliente_renovado.apellido}"
            )

            enviar_contrato_correo(cliente_renovado)

            messages.success(
                request,
                f"El Cliente {cliente_renovado.nombre} {cliente_renovado.apellido} ha renovado su plan correctamente."
            )

        # Mantener el filtro del RUT después de renovar
        return redirect(f"{reverse('renovarCliente')}?rut={rut_renovar}")


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

    # Filtro adicional
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


@role_required(['Administrador'])
@never_cache
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


@role_required(['Administrador'])
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
           request.user_obj,
            "cambio_plan",
            "Cliente",
            cliente.id,
            f"Cambió sub plan a {nuevo_sub_plan} para {cliente.nombre} {cliente.apellido}"
        )
            messages.success(request, f"SubPlan de {cliente.nombre} actualizado a {nuevo_sub_plan}.")

    return redirect(f'{reverse("renovarCliente")}?rut={rut_cliente}')


@role_required(['Administrador'])
@never_cache
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

    # Localización de nombres de meses
    try:
        locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')

    current_month_name = datetime(year, month, 1).strftime('%B').capitalize()

    cliente = None
    rut_invalido = False
    asistencias_dict = {}
    sesiones_dict = {}

    ACCESOS_POR_SUBPLAN = {
        'Bronce': 4,
        'Hierro': 8,
        'Acero': 12,
        'Titanio': None,  
    }

    first_weekday, num_days = calendar.monthrange(year, month)
    dias_mes = [None] * ((first_weekday + 1) % 7) + list(range(1, num_days + 1))

    total_subplan = 0
    restantes_subplan = 0
    total_personalizado = 0
    restantes_personalizado = 0
    total_accesos_permitidos = 0
    accesos_restantes = 0
    fecha_fin_plan = None 

    if rut:
        try:
            cliente = Cliente.objects.get(rut=rut)
            inicio_mes = datetime(year, month, 1).date()
            fin_mes = datetime(year, month, num_days).date()

            #  Asistencias 
            asistencias = Asistencia.objects.filter(
                cliente=cliente,
                fecha__gte=inicio_mes,
                fecha__lte=fin_mes
            ).order_by('fecha')

            asistencias_temp = defaultdict(list)
            for a in asistencias:
                dia = a.fecha.day
                hora = a.fecha.strftime("%H:%M:%S") if hasattr(a.fecha, 'hour') else "Entrada"
                asistencias_temp[dia].append(hora)
            asistencias_dict = dict(asistencias_temp)

            #  Sesiones 
            sesiones = Sesion.objects.filter(
                cliente=cliente,
                fecha__gte=inicio_mes,
                fecha__lte=fin_mes
            ).order_by('fecha')

            sesiones_temp = defaultdict(list)
            for s in sesiones:
                dia = s.fecha.day
                tipo = s.get_tipo_sesion_display()
                sesiones_temp[dia].append(tipo)
            sesiones_dict = dict(sesiones_temp)

            # subplan 
            total_subplan = ACCESOS_POR_SUBPLAN.get(cliente.sub_plan, 0)
            restantes_subplan = cliente.accesos_subplan_restantes or 0

            fecha_fin_plan = getattr(cliente, 'fecha_fin_plan', None)

            #  Plan personalizado 
            if cliente.plan_personalizado_activo:
                total_personalizado = cliente.plan_personalizado_activo.accesos_por_mes or 0
                restantes_personalizado = cliente.accesos_personalizados_restantes or 0

            # Totales combinados
            if cliente.sub_plan == "Titanio":
                total_accesos_permitidos = None  # acceso libre
                accesos_restantes = None
            else:
                total_accesos_permitidos = (total_subplan or 0) + (total_personalizado or 0)
                accesos_restantes = (restantes_subplan or 0) + (restantes_personalizado or 0)

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
        'total_subplan': total_subplan,
        'restantes_subplan': restantes_subplan,
        'total_personalizado': total_personalizado,
        'restantes_personalizado': restantes_personalizado,
        'total_accesos_permitidos': total_accesos_permitidos,
        'accesos_restantes': accesos_restantes,
        'fecha_fin_plan': fecha_fin_plan,  
    }

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



@role_required(['Administrador'])
@never_cache
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
                request.user_obj,
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

@role_required(['Administrador'])
@never_cache
def eliminar_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == 'POST':
        cliente.delete()
        registrar_historial(
    request.user_obj,
    "eliminar",
    "Cliente",
    cliente.id,
    f"Eliminó cliente {cliente.nombre} {cliente.apellido}"
    )   
        messages.success(request, f"🗑️ Cliente eliminado correctamente.")
    else:
        messages.error(request, "Método no permitido.")

    return redirect('renovarCliente')

@role_required(['Administrador'])
@never_cache
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
@role_required(['Administrador'])
@never_cache
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

@role_required(['Administrador'])
@never_cache
def cambiar_tipo_plan_mensual(request):
    if request.method == 'POST':
        rut_cliente = request.POST.get('rut_cliente')
        nuevo_plan_id = request.POST.get('nuevo_plan')

        cliente = Cliente.objects.filter(rut=rut_cliente).first()
        if cliente and nuevo_plan_id:
            cliente.mensualidad_id = nuevo_plan_id
            cliente.save()


        return redirect(f'{reverse("renovarCliente")}?rut={rut_cliente}')
    
@role_required(['Administrador'])
@never_cache
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

@role_required(['Administrador'])
@never_cache
def renovar_plan_personalizado(request):
    if request.method == 'POST':
        rut_cliente = request.POST.get('rut_cliente')

        try:
            cliente = Cliente.objects.get(rut=rut_cliente)
        except Cliente.DoesNotExist:
            messages.error(request, "Cliente no encontrado.")
            return redirect('renovarCliente')

        # Verificar que tenga al menos un plan personalizado
        if not cliente.planes_personalizados.exists():
            messages.error(request, "El cliente no tiene un plan personalizado asignado.")
            return redirect('renovarCliente')

        hoy = timezone.localdate()
        plan = cliente.planes_personalizados.first()

        # Renovar solo accesos personalizados, sin tocar fechas
        if plan.accesos_por_mes > 0:
            cliente.accesos_personalizados_restantes = plan.accesos_por_mes
            cliente.accesos_restantes = plan.accesos_por_mes
        else:
            # Si es un plan libre o sin límite
            cliente.accesos_personalizados_restantes = float('inf')
            cliente.accesos_restantes = float('inf')

        # Guardar solo los campos relevantes
        cliente.ultimo_reset_mes = hoy
        cliente.save(update_fields=[
            'accesos_personalizados_restantes',
            'accesos_restantes',
            'ultimo_reset_mes'
        ])

        # Registrar acción en historial
        registrar_historial(
            request.user_obj,
            "renovar",
            "Cliente",
            cliente.id,
            f"Renovó plan personalizado '{plan.nombre_plan}' para {cliente.nombre} {cliente.apellido}"
        )

        messages.success(
            request,
            f"✅ Plan personalizado '{plan.nombre_plan}' renovado para {cliente.nombre} {cliente.apellido}."
        )

        return redirect('renovarCliente')

    # Si no es POST, redirigir
    return redirect('renovarCliente')


@role_required(['Administrador'])
@never_cache
def productos(request):
    productos = Producto.objects.all().order_by("nombre")
    producto_seleccionado = request.session.pop('producto_seleccionado', None)

    return render(request, 'core/productos.html', {
        'productos': productos,
        'producto_seleccionado': producto_seleccionado
    })


@role_required(['Administrador'])
@never_cache
def registrar_venta(request):
    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        cantidad = request.POST.get('cantidad')
        metodo_pago = request.POST.get('metodo_pago')

 
        admin_id = request.session.get('admin_id')
        admin = Admin.objects.get(id=admin_id)

        # Validación cantidad
        try:
            cantidad = int(cantidad)
        except:
            messages.error(request, "⚠️ La cantidad debe ser un número entero.")
            return redirect('productos')

        producto = Producto.objects.filter(id=producto_id).first()
        if not producto:
            messages.error(request, "❌ Producto no encontrado.")
            return redirect('productos')

        if cantidad <= 0:
            messages.error(request, "⚠️ La cantidad debe ser mayor a 0.")
            return redirect('productos')

        # Esta validación sí la dejamos
        if cantidad > producto.stock:
            messages.error(
                request,
                f"❌ No quedan suficientes unidades de '{producto.nombre}'."
            )
            return redirect('productos')

        if metodo_pago not in dict(Venta.METODOS_PAGO).keys():
            messages.error(request, "⚠️ Seleccione un método de pago válido.")
            return redirect('productos')

        # Crear la venta — el modelo restará el stock
        venta = Venta.objects.create(
            producto=producto,
            cantidad=cantidad,
            metodo_pago=metodo_pago,
            admin=admin
        )

        registrar_historial(
            request.user_obj,
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

        return redirect('productos')

    return redirect('productos')




@role_required(['Administrador'])
@never_cache
def agregar_stock(request):
    productos = Producto.objects.all().order_by("nombre")

    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        cantidad = request.POST.get('cantidad')
        accion = request.POST.get('accion', 'sumar')  

        try:
            cantidad = int(cantidad)
            if cantidad <= 0:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, "⚠️ La cantidad debe ser un número válido mayor que 0.")
            return redirect('agregar_stock')

        producto = Producto.objects.filter(id=producto_id).first()
        if not producto:
            messages.error(request, "❌ Producto no encontrado.")
            return redirect('agregar_stock')

        # Lógica para sumar o restar stock sin afectar ventas
        if accion == 'restar':
            if cantidad > producto.stock:
                messages.error(request, f"⚠️ No se puede restar más de lo que hay en stock ({producto.stock}).")
                return redirect('agregar_stock')
            producto.stock -= cantidad
            mensaje_accion = f"restó {cantidad} unidades"
        else:
            producto.stock += cantidad
            mensaje_accion = f"agregó {cantidad} unidades"

        producto.save()

        registrar_historial(
            request.user_obj,
            "modificar",
            "Producto",
            producto.id,
            f"{mensaje_accion} al stock de {producto.nombre}"
        )

        messages.success(
            request,
            f"✅ Se {mensaje_accion} al stock de '{producto.nombre}'. Stock actual: {producto.stock}."
        )
        return redirect('agregar_stock')

    return render(request, 'core/agregar_stock.html', {'productos': productos})


@role_required(['Administrador'])
@never_cache
def historial_ventas(request):
    ventas = Venta.objects.select_related("producto").order_by("-fecha")
    return render(request, "core/historial_ventas.html", {"ventas": ventas})

@role_required(['Administrador'])
@never_cache
def agregar_producto(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            producto = form.save()
            registrar_historial(
                request.user_obj,
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


@role_required(['Administrador'])
@never_cache
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
                   request.user_obj,
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

@role_required(['Administrador'])
@never_cache
def eliminar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)

    if request.method == 'POST':
        producto.delete()
        registrar_historial(
        request.user_obj,
        "eliminar",
        "Producto",
        producto.id,
        f"Eliminó producto {producto.nombre}"
    )
        messages.success(request, "🗑️ Producto eliminado correctamente.")
    else:
        messages.error(request, "Método no permitido.")

    return redirect('productos')

@role_required(['Administrador'])
@never_cache
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
    fecha_limite = hoy - timedelta(days=5)

    clientes_activos_mes = (
        Asistencia.objects
        .filter(
            fecha__gte=inicio_mes,
            cliente__in=clientes_filtrados,
    
            cliente__fecha_fin_plan__gte=fecha_limite
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


@role_required(['Administrador'])
@never_cache
def asistencia_kine_nutri(request):
  
    if request.method == "POST" and request.headers.get("x-requested-with", "").lower() == "xmlhttprequest":
        cliente_id = request.POST.get("cliente_id")
        tipo_sesion = request.POST.get("tipo_sesion")
        profesional_id = request.POST.get("profesional_id")
        tipo_objeto = request.POST.get("tipo_objeto")

        try:
            if cliente_id and tipo_sesion and profesional_id and tipo_objeto:
                profesional = get_object_or_404(NombresProfesionales, id=profesional_id)

                if tipo_objeto == "interno":
                    cliente = get_object_or_404(Cliente, id=cliente_id)
                    sesion = Sesion.objects.create(
                        cliente=cliente,
                        tipo_sesion=tipo_sesion,
                        fecha=timezone.localdate(),
                        profesional=profesional
                    )
                    cliente_nombre = f"{cliente.nombre} {cliente.apellido}"
                else:
                    cliente_externo = get_object_or_404(ClienteExterno, id=cliente_id)
                    sesion = Sesion.objects.create(
                        cliente_externo=cliente_externo,
                        tipo_sesion=tipo_sesion,
                        fecha=timezone.localdate(),
                        profesional=profesional
                    )
                    cliente_nombre = f"{cliente_externo.nombre} {cliente_externo.apellido}"

                return JsonResponse({
                    "success": True,
                    "cliente": cliente_nombre,
                    "tipo": sesion.get_tipo_sesion_display(),
                    "profesional": f"{profesional.nombre} {profesional.apellido}",
                    "fecha": sesion.fecha.strftime("%d/%m/%Y")
                })
            else:
                return JsonResponse({"success": False, "error": "Datos incompletos"}, status=400)

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    # --- Renderizar página ---
    clientes_internos = list(
        Cliente.objects.filter(tipo_publico__isnull=False)
        .exclude(tipo_publico__icontains="Pase Diario")
    )
    for c in clientes_internos:
        c.tipo_objeto = "interno"

    clientes_externos = list(ClienteExterno.objects.all())
    for c in clientes_externos:
        c.tipo_objeto = "externo"

    clientes = sorted(clientes_internos + clientes_externos, key=lambda c: c.nombre.lower())


    nutricionistas_qs = NombresProfesionales.objects.filter(profesion__icontains="nutricion")
    kinesiologos_qs = NombresProfesionales.objects.filter(profesion__icontains="kine")
    masajistas_qs = NombresProfesionales.objects.filter(profesion__icontains="masaj")

    nutricionistas = list(nutricionistas_qs.values("id", "nombre", "apellido"))
    kinesiologos = list(kinesiologos_qs.values("id", "nombre", "apellido"))
    masajistas = list(masajistas_qs.values("id", "nombre", "apellido"))

    sesiones = Sesion.objects.select_related("profesional").order_by("-fecha")[:20]

    return render(request, "core/asistencia_kine_nutri.html", {
        "clientes": clientes,
        "sesiones": sesiones,
        "nutricionistas": nutricionistas,
        "kinesiologos": kinesiologos,
        "masajistas": masajistas,
    })



@role_required(['Administrador'])
@never_cache
def registrar_cliente_externo(request):
    if request.method == 'POST':
        form = ClienteExternoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Cliente externo registrado correctamente.')
            form = ClienteExternoForm()  
        else:
        
            messages.error(request, '❌ Por favor corrige los errores del formulario.')
    else:
        form = ClienteExternoForm()

    return render(request, 'core/registrar_cliente_externo.html', {'form': form})




@role_required(['Kinesiologo', 'Nutricionista', 'Masajista', 'Administrador'])
@never_cache
def agendar_hora_box(request):
    usuario = getattr(request, 'user_obj', None)
    if not usuario:
        return JsonResponse({'error': 'Usuario no autenticado'}, status=403)

    profesion = getattr(usuario, 'profesion', None)
    if not profesion:
        return JsonResponse({'error': 'Usuario sin profesión definida'}, status=403)

    profesional = NombresProfesionales.objects.filter(
        nombre__iexact=usuario.nombre.strip(),
        apellido__iexact=usuario.apellido.strip(),
        profesion=profesion
    ).first()


    if request.path.endswith('/listar/'):
        eventos = []

        if profesion == 'Administrador':
            sesiones = AgendaProfesional.objects.all()
        elif profesion in ['Nutricionista', 'Masajista']:
            sesiones = AgendaProfesional.objects.filter(box='Box 1')
        elif profesion == 'Kinesiologo':
            sesiones = AgendaProfesional.objects.filter(box='Box 2')
        else:
            sesiones = []

        for s in sesiones:
            if s.profesional == profesional:
                title = f"{s.box} - {'Disponible' if s.disponible else 'Tu bloque'}"
                color = '#87CEFA'
            else:
                title = f"{s.box} - {'Disponible' if s.disponible else f'Ocupado por {s.profesional.nombre}'}"
                color = '#1E90FF' if s.box == 'Box 1' else '#28a745'

            puede_editar = profesion == 'Administrador' or s.profesional == profesional

            eventos.append({
                'id': s.id,
                'title': title,
                'start': f'{s.fecha}T{s.hora_inicio}',
                'end': f'{s.fecha}T{s.hora_fin}',
                'disponible': s.disponible,
                'profesional_id': s.profesional.id,
                'box': s.box,
                'backgroundColor': color,
                'extendedProps': {'puede_editar': puede_editar}
            })
        return JsonResponse(eventos, safe=False)
    #  CREAR BLOQUE 
    if request.method == 'POST':
        try:
            fecha = request.POST.get('fecha')
            hora_inicio = request.POST.get('hora_inicio')
            hora_fin = request.POST.get('hora_fin')
            box = request.POST.get('box')
            profesional_id = request.POST.get('profesional_id')

            if profesion == 'Nutricionista' and box != 'Box 1':
                return JsonResponse({'error': 'Los nutricionistas solo pueden crear en Box 1.'}, status=403)
            if profesion == 'Masajista' and box != 'Box 1':
                return JsonResponse({'error': 'Los masajistas solo pueden crear en Box 1.'}, status=403)
            if profesion == 'Kinesiologo' and box != 'Box 2':
                return JsonResponse({'error': 'Los kinesiólogos solo pueden crear en Box 2.'}, status=403)

            
            if profesion == 'Administrador' and profesional_id:
                profesional = NombresProfesionales.objects.filter(id=profesional_id).first()
            elif not profesional:
                return JsonResponse({'error': 'No se encontró el profesional vinculado.'}, status=400)

            fecha_dt = datetime.strptime(fecha, '%Y-%m-%d').date()
            hora_inicio_obj = datetime.strptime(hora_inicio, '%H:%M').time()
            hora_fin_obj = datetime.strptime(hora_fin, '%H:%M').time()

            existe_bloque = AgendaProfesional.objects.filter(
                box=box,
                fecha=fecha_dt,
                hora_inicio=hora_inicio_obj
            ).exists()

            if existe_bloque:
                return JsonResponse({'error': f'Ya existe un bloque en {box} a las {hora_inicio}.'}, status=400)

            AgendaProfesional.objects.create(
                profesional=profesional,
                fecha=fecha_dt,
                hora_inicio=hora_inicio_obj,
                hora_fin=hora_fin_obj,
                box=box,
                disponible=True
            )

            return JsonResponse({'mensaje': f'Bloque creado correctamente en {box}.'})

        except IntegrityError:
            return JsonResponse({'error': 'Bloque duplicado. Intenta con otro horario.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'Error inesperado: {str(e)}'}, status=500)

    #  ELIMINAR BLOQUE 
    if '/eliminar/' in request.path:
        bloque_id = request.path.split('/')[-2]
        bloque = AgendaProfesional.objects.filter(id=bloque_id).first()
        if not bloque:
            return JsonResponse({'error': 'Bloque no encontrado.'}, status=404)

        if profesion != 'Administrador' and bloque.profesional != profesional:
            return JsonResponse({'error': 'No puedes eliminar bloques de otro profesional.'}, status=403)

        bloque.delete()
        return JsonResponse({'status': 'ok'})

    return render(request, 'core/agendar_hora_box.html', {
        'profesional': profesional,
        'profesionales': NombresProfesionales.objects.all() if profesion == 'Administrador' else [],
        'usuario_profesion': profesion
    })



@safe_view
@role_required(['Kinesiologo', 'Nutricionista', 'Masajista', 'Administrador'])
@csrf_exempt
def listar_agendas(request):
    admin_id = request.session.get('admin_id')
    admin = get_object_or_404(Admin, id=admin_id)

    profesional = NombresProfesionales.objects.filter(
        Q(nombre__icontains=admin.nombre.strip()) &
        Q(apellido__icontains=admin.apellido.strip()) &
        Q(profesion__in=['Kinesiologo', 'Nutricionista', 'Masajista'])
    ).first()

    if admin.profesion == 'Administrador':
        agendas = AgendaProfesional.objects.filter(profesional__profesion__in=['Kinesiologo', 'Nutricionista', 'Masajista'])
    elif admin.profesion in ['Kinesiologo', 'Nutricionista', 'Masajista']:
        agendas = AgendaProfesional.objects.filter(profesional__profesion__in=['Kinesiologo', 'Nutricionista', 'Masajista'])
    else:
        return JsonResponse({'error': 'No autorizado'}, status=403)

    if admin.profesion in ['Nutricionista', 'Masajista']:
        agendas = agendas.filter(box='Box 1')
    elif admin.profesion == 'Kinesiologo':
        agendas = agendas.filter(box='Box 2')

    eventos = []
    for a in agendas:
        if a.profesional == profesional:
            titulo = f"{a.box} - {'Disponible' if a.disponible else 'Tu bloque'}"
            color = '#87CEFA'
        else:
            titulo = f"{a.box} - {'Disponible' if a.disponible else f'Ocupado por {a.profesional.nombre}'}"
            color = '#dc3545' if not a.disponible else ('#1E90FF' if a.box == 'Box 1' else '#28a745')

        puede_editar = admin.profesion == 'Administrador' or a.profesional == profesional

        eventos.append({
            'id': a.id,
            'title': titulo,
            'start': f"{a.fecha}T{a.hora_inicio.strftime('%H:%M:%S')}",
            'end': f"{a.fecha}T{a.hora_fin.strftime('%H:%M:%S')}",
            'color': color,
            'editable': puede_editar,
            'extendedProps': {
                'disponible': a.disponible,
                'fecha': str(a.fecha),
                'hora_inicio': a.hora_inicio.strftime('%H:%M:%S'),
                'hora_fin': a.hora_fin.strftime('%H:%M:%S'),
                'puede_editar': puede_editar
            }
        })

    return JsonResponse(eventos, safe=False)


@safe_view
@role_required(['Kinesiologo', 'Nutricionista', 'Masajista', 'Administrador'])
@csrf_exempt
def cambiar_estado_agenda(request, agenda_id):
    agenda = get_object_or_404(AgendaProfesional, id=agenda_id)

    admin_id = request.session.get('admin_id')
    admin = Admin.objects.filter(id=admin_id).first()

    profesional = NombresProfesionales.objects.filter(
        nombre__iexact=admin.nombre.strip(),
        apellido__iexact=admin.apellido.strip(),
        profesion=admin.profesion
    ).first()

    if profesional and agenda.profesional != profesional and admin.profesion != 'Administrador':
        return JsonResponse({'error': 'No autorizado para modificar esta agenda.'}, status=403)

    agenda.disponible = not agenda.disponible

    if not agenda.disponible:
        rut = request.GET.get('rut')
        cliente = Cliente.objects.filter(rut=rut).first()
        cliente_externo = ClienteExterno.objects.filter(rut=rut).first() if not cliente else None
        agenda.cliente = cliente
        agenda.cliente_externo = cliente_externo
        agenda.crear_sesion_si_corresponde()
    else:
        agenda.cliente = None
        agenda.cliente_externo = None

    agenda.save()
    agenda.registrar_accion('editar', admin=admin)

    return JsonResponse({
        'id': agenda.id,
        'disponible': agenda.disponible,
        'color': '#2ECC71' if agenda.disponible else '#E74C3C',
        'mensaje': 'Estado actualizado correctamente.'
    })


@safe_view
@role_required(['Kinesiologo', 'Nutricionista', 'Masajista', 'Administrador'])
@csrf_exempt
def eliminar_agenda(request, agenda_id):
    agenda = get_object_or_404(AgendaProfesional, id=agenda_id)

    admin_id = request.session.get('admin_id')
    admin = Admin.objects.filter(id=admin_id).first()

    profesional = NombresProfesionales.objects.filter(
        nombre__iexact=admin.nombre.strip(),
        apellido__iexact=admin.apellido.strip(),
        profesion=admin.profesion
    ).first()

    if agenda.profesional != profesional and admin.profesion != 'Administrador':
        return JsonResponse({'error': 'No autorizado para eliminar esta agenda.'}, status=403)

    agenda.registrar_accion('eliminar', admin=admin)
    agenda.delete()
    return JsonResponse({'status': 'ok', 'mensaje': 'Bloque eliminado correctamente.'})



@safe_view
@role_required(['Coach', 'Administrador'])
def agenda_pf(request):
    usuario = getattr(request, 'user_obj', None)
    if not usuario:
        return JsonResponse({'error': 'Usuario no autenticado'}, status=403)

    usuario_profesion = getattr(usuario, 'profesion', None)
    if not usuario_profesion:
        return JsonResponse({'error': 'Usuario sin profesión definida'}, status=403)

    profesional = None
    clientes = []
    profesionales_disponibles = []

    if usuario_profesion == 'Administrador':
        clientes = Cliente.objects.filter(plan_personalizado_activo__isnull=False)
        profesionales_disponibles = NombresProfesionales.objects.filter(profesion='Coach')

    elif usuario_profesion == 'Coach':
        profesional = NombresProfesionales.objects.filter(
            nombre__iexact=usuario.nombre.strip(),
            apellido__iexact=usuario.apellido.strip(),
            profesion='Coach'
        ).first()
        if profesional:
            clientes = Cliente.objects.filter(
                coach_asignado=profesional,
                plan_personalizado_activo__isnull=False
            )
        else:
            return JsonResponse({'error': 'No se encontró el profesional vinculado.'}, status=400)

    # Listado de eventos
    if request.path.endswith('/listar/'):
        eventos = []

        if usuario_profesion == 'Administrador':
            sesiones = AgendaProfesional.objects.filter(profesional__profesion='Coach')
        elif usuario_profesion == 'Coach' and profesional:
            sesiones = AgendaProfesional.objects.filter(profesional=profesional)
        else:
            sesiones = []

        for s in sesiones:
            eventos.append({
                'id': s.id,
                'title': f'{s.cliente.nombre} {s.cliente.apellido}',
                'start': f'{s.fecha}T{s.hora_inicio}',
                'end': f'{s.fecha}T{s.hora_fin}',
                'estado': getattr(s, 'estado', 'agendado')
            })

        return JsonResponse(eventos, safe=False)

    # Crear sesión
    if request.method == 'POST':
        try:
            cliente_id = request.POST.get('cliente_id')
            fecha = request.POST.get('fecha')
            hora_inicio = request.POST.get('hora_inicio')
            hora_fin = request.POST.get('hora_fin')

            if usuario_profesion == 'Administrador':
                profesional_id = request.POST.get('profesional_id')
                profesional = NombresProfesionales.objects.filter(id=profesional_id, profesion='Coach').first()
                if not profesional:
                    return JsonResponse({'error': 'Debe seleccionar un profesional válido.'}, status=400)
            else:
                if not profesional:
                    return JsonResponse({'error': 'No se encontró el profesional vinculado.'}, status=400)

            cliente = Cliente.objects.filter(id=cliente_id).first()
            if not cliente:
                return JsonResponse({'error': 'Cliente no encontrado.'}, status=404)

            fecha_dt = datetime.strptime(fecha, '%Y-%m-%d').date()
            hora_inicio_obj = datetime.strptime(hora_inicio, '%H:%M').time()
            hora_fin_obj = datetime.strptime(hora_fin, '%H:%M').time()

            AgendaProfesional.objects.create(
                profesional=profesional,
                cliente=cliente,
                fecha=fecha_dt,
                hora_inicio=hora_inicio_obj,
                hora_fin=hora_fin_obj,
                disponible=False
            )

            return JsonResponse({'mensaje': f'Sesión agendada con {cliente.nombre} {cliente.apellido}.'})

        except Exception as e:
            return JsonResponse({'error': f'Ocurrió un error inesperado: {str(e)}'}, status=500)

    return render(request, 'core/agenda_pf.html', {
        'profesional': profesional,
        'clientes': clientes,
        'profesionales_disponibles': profesionales_disponibles,
        'usuario_profesion': usuario_profesion
    })



# MARCAR NO ASISTIÓ
@csrf_exempt
@safe_view
@role_required(['Coach', 'Administrador'])
def marcar_no_asistio(request, agenda_id):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    agenda = get_object_or_404(AgendaProfesional, id=agenda_id)
    cliente = agenda.cliente

    if not cliente:
        return JsonResponse({"error": "Esta sesión no tiene cliente asignado"}, status=400)

    plan_activo = cliente.plan_personalizado_activo
    descuento_realizado = False

    if plan_activo and cliente.accesos_personalizados_restantes > 0:
        cliente.accesos_personalizados_restantes -= 1
        descuento_realizado = True

    # Actualizamos accesos generales
    cliente.accesos_restantes = max(
        cliente.accesos_personalizados_restantes or 0,
        cliente.accesos_subplan_restantes or 0
    )
    cliente.save(update_fields=["accesos_personalizados_restantes", "accesos_restantes"])

    agenda.comentario = (agenda.comentario or '') + " | Marcado NO ASISTIÓ"
    agenda.save(update_fields=['comentario'])

    return JsonResponse({
        "mensaje": "Acceso descontado correctamente." if descuento_realizado else "No se pudo descontar acceso.",
        "descuento_realizado": descuento_realizado
    })



@safe_view
@role_required(['Coach', 'Administrador'])
def listar_agenda_pf(request):
    usuario = getattr(request, 'user_obj', None)
    if not usuario:
        return JsonResponse({'error': 'Usuario no autenticado'}, status=403)

    usuario_profesion = getattr(usuario, 'profesion', None)
    if not usuario_profesion:
        return JsonResponse({'error': 'Usuario sin profesión definida'}, status=403)

    if usuario_profesion == 'Administrador':
        sesiones = AgendaProfesional.objects.select_related('profesional', 'cliente').filter(profesional__profesion='Coach')
    elif usuario_profesion == 'Coach':
        profesional = NombresProfesionales.objects.filter(
            nombre__iexact=usuario.nombre.strip(),
            apellido__iexact=usuario.apellido.strip(),
            profesion='Coach'
        ).first()
        if not profesional:
            return JsonResponse({'error': 'No se encontró profesional vinculado'}, status=400)
        sesiones = AgendaProfesional.objects.select_related('profesional', 'cliente').filter(profesional=profesional)
    else:
        return JsonResponse({'error': f'Rol no autorizado: {usuario_profesion}'}, status=403)

    colores = [
        "#1E90FF", "#FF4500", "#32CD32", "#FFD700", "#8A2BE2",
        "#FF1493", "#20B2AA", "#DC143C", "#FF8C00", "#00CED1"
    ]
    color_por_coach = {}
    eventos = []

    for a in sesiones:
        if not a.cliente or not a.profesional:
            continue

        coach_nombre = f"{a.profesional.nombre} {a.profesional.apellido}"

        if coach_nombre not in color_por_coach:
            color_por_coach[coach_nombre] = colores[len(color_por_coach) % len(colores)]
        color = color_por_coach[coach_nombre]

        estado = "Agendado"
        if a.comentario and "NO ASISTIÓ" in a.comentario.upper():
            estado = "No asistió"
            color = "#ffc107"

        start_time = a.hora_inicio.strftime('%H:%M:%S')
        end_time = a.hora_fin.strftime('%H:%M:%S')

        title = f"{a.cliente.nombre} {a.cliente.apellido}"
        if usuario_profesion == 'Administrador':
            title += f" ({coach_nombre})"
        if estado == "No asistió":
            title += " ⚠️"

        eventos.append({
            'id': a.id,
            'title': title,
            'start': f"{a.fecha}T{start_time}",
            'end': f"{a.fecha}T{end_time}",
            'color': color,
            'extendedProps': {
                'estado': estado.lower().replace(" ", "_"),
                'cliente_id': a.cliente.id,
                'profesional_id': a.profesional.id,
                'coach': coach_nombre,
                'hora_inicio': start_time,
                'hora_fin': end_time,
            }
        })

    return JsonResponse(eventos, safe=False)


# ELIMINAR SESIÓN
@safe_view
@role_required(['Coach', 'Administrador'])
def eliminar_agenda_pf(request, agenda_id):
    AgendaProfesional.objects.filter(id=agenda_id).delete()
    return JsonResponse({'mensaje': 'Sesión eliminada.'})

# ===========================
# REDIRECCIÓN INICIAL
# ===========================
@safe_view
def home(request):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login')
    admin = get_object_or_404(Admin, id=admin_id)
    if admin.profesion in ['Kinesiologo', 'Nutricionista']:
        return redirect('agendar_hora_box')
    return redirect('index')


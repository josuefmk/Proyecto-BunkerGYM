from django.shortcuts import render, redirect
from django.utils import timezone
from .models import Cliente, Asistencia, Admin
from .forms import ClienteForm
from datetime import datetime
from dateutil.relativedelta import relativedelta

# ===========================
# LOGIN PERSONALIZADO (con Admin)
# ===========================
def login_admin(request):
    if request.method == 'POST':
        rut = request.POST.get('rut')
        password = request.POST.get('password')
        admin = Admin.objects.filter(rut=rut, password=password).first()
        if admin:
            request.session['admin_id'] = admin.id
            return redirect('index')
        else:
            request.session['login_error'] = 'Credenciales inválidas'
            return redirect('login')  # PRG Pattern
    else:
        error = request.session.pop('login_error', None)
        return render(request, 'core/home.html', {'error': error})


def logout_admin(request):
    request.session.flush()
    return redirect('login')


# ===========================
# DECORADOR PARA PROTEGER VISTAS SOLO ADMIN
# ===========================
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


# ===========================
# VISTAS PROTEGIDAS
# ===========================
@admin_required
def index(request):
    hoy = timezone.now().date()
    asistencias_hoy = Asistencia.objects.filter(fecha__date=hoy).select_related('cliente')
    datos_clientes = []

    for asistencia in asistencias_hoy:
        cliente = asistencia.cliente
        datos_clientes.append({
            'cliente': cliente,
            'hora_ingreso': asistencia.fecha.strftime('%H:%M:%S'),
            'tipo_plan': cliente.mensualidad.tipo if cliente.mensualidad else (
                cliente.plan_personalizado.nombre_plan if cliente.plan_personalizado else '—'
            ),
            'vencimiento_plan': f"{cliente.dias_restantes()} días restantes" if cliente.fecha_inicio_plan else '—',
        })

    return render(request, 'core/index.html', {'datos_clientes': datos_clientes})


@admin_required
def registro_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('index')  # PRG aplicado aquí también
    else:
        form = ClienteForm()
    return render(request, 'core/registroCliente.html', {'form': form})


@admin_required
def asistencia_cliente(request):
    if request.method == "POST":
        rut = request.POST.get('rut')
        cliente = Cliente.objects.filter(rut=rut).first()

        if cliente:
            hoy = timezone.now().date()
            ya_registrado = Asistencia.objects.filter(cliente=cliente, fecha__date=hoy).exists()

            if ya_registrado:
                request.session['asistencia_ya_registrada'] = True
                return redirect('asistencia_cliente')

            Asistencia.objects.create(cliente=cliente)

            if cliente.fecha_inicio_plan:
                vencimiento = cliente.fecha_inicio_plan + relativedelta(months=1)
                dias_restantes = (vencimiento - hoy).days
            else:
                vencimiento = None
                dias_restantes = None

            request.session['mostrar_modal'] = True
            request.session['cliente_id'] = cliente.id
            request.session['vencimiento_plan'] = vencimiento.isoformat() if vencimiento else ''
            request.session['dias_restantes'] = dias_restantes

            return redirect('asistencia_cliente')
        else:
            request.session['rut_invalido'] = True
            return redirect('asistencia_cliente')

    # GET
    mostrar_modal = request.session.pop('mostrar_modal', False)
    asistencia_ya_registrada = request.session.pop('asistencia_ya_registrada', False)
    rut_invalido = request.session.pop('rut_invalido', False)

    cliente_id = request.session.pop('cliente_id', None)
    venc_str = request.session.pop('vencimiento_plan', '')
    dias_restantes = request.session.pop('dias_restantes', None)

    cliente = Cliente.objects.filter(id=cliente_id).first() if cliente_id else None
    vencimiento_plan = datetime.fromisoformat(venc_str) if venc_str else None

    context = {
        'mostrar_modal': mostrar_modal,
        'asistencia_ya_registrada': asistencia_ya_registrada,
        'rut_invalido': rut_invalido,
        'cliente': cliente,
        'vencimiento_plan': vencimiento_plan,
        'dias_restantes': dias_restantes,
    }

    return render(request, 'core/AsistenciaCliente.html', context)


# ===========================
# REDIRECCIÓN INICIAL
# ===========================
def home(request):
    return redirect('login')

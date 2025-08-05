from django.shortcuts import render, redirect
from django.utils import timezone
from .models import Cliente, Asistencia, Admin, PlanPersonalizado,Producto, Venta
from .forms import ClienteForm,ProductoForm
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz
from django.utils.timezone import localdate
from django.db.models import F, ExpressionWrapper, FloatField
from datetime import timedelta
import json
from django.db.models import Count, Sum,Q,F,Func
from django.utils.timezone import now
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.contrib import messages
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

    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            mensaje = f"✅ El cliente {cliente.nombre} ha sido creado correctamente."
            form = ClienteForm()  # Limpiador
    else:
        form = ClienteForm()

    return render(request, 'core/registroCliente.html', {'form': form, 'mensaje': mensaje})

@admin_required
def asistencia_cliente(request):
    if request.method == "POST":
        rut = request.POST.get('rut')
        cliente = Cliente.objects.filter(rut=rut).first()

        if cliente:
            hoy = timezone.localdate()
            ya_registrado = Asistencia.objects.filter(cliente=cliente, fecha__date=hoy).exists()

            if ya_registrado:
                request.session['asistencia_ya_registrada'] = True
                return redirect('asistencia_cliente')
            Asistencia.objects.create(cliente=cliente)

            vencimiento = cliente.calcular_vencimiento()
            dias_restantes = cliente.dias_restantes()

            request.session['mostrar_modal'] = True
            request.session['cliente_id'] = cliente.id
            request.session['vencimiento_plan'] = vencimiento.isoformat() if vencimiento else ''
            request.session['dias_restantes'] = dias_restantes

            return redirect('asistencia_cliente')
        else:
            request.session['rut_invalido'] = True
            return redirect('asistencia_cliente')

  
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




@admin_required
def listaCliente(request):
    hoy = timezone.localdate()
    asistencias_hoy = Asistencia.objects.filter(fecha__date=hoy).select_related('cliente').order_by('-fecha')

    datos_clientes = []


    zona_chile = pytz.timezone('America/Santiago')

    for asistencia in asistencias_hoy:
        cliente = asistencia.cliente

      
        fecha_chilena = asistencia.fecha.astimezone(zona_chile)

        datos_clientes.append({
            'cliente': cliente,
            'hora_ingreso': fecha_chilena.strftime('%H:%M:%S'),
            'tipo_plan': cliente.mensualidad.tipo if cliente.mensualidad else (
                cliente.plan_personalizado.nombre_plan if cliente.plan_personalizado else '—'
            ),
            'vencimiento_plan': f"{cliente.dias_restantes()} días restantes" if cliente.fecha_inicio_plan else '—',
        })

    return render(request, 'core/listaCliente.html', {'datos_clientes': datos_clientes})

@admin_required
def listaCliente_json(request):
    hoy = timezone.localdate()
    asistencias_hoy = Asistencia.objects.filter(fecha__date=hoy).select_related('cliente').order_by('-fecha')
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
                cliente.plan_personalizado.nombre_plan if cliente.plan_personalizado else '—'
            ),
            'vencimiento_plan': f"{cliente.dias_restantes()} días restantes" if cliente.fecha_inicio_plan else '—',
        })

    return JsonResponse({'datos_clientes': datos_clientes})

@admin_required
def renovarCliente(request):
    rut_buscado = request.POST.get('rut') or request.GET.get('rut', '')
    cliente_renovado = None

    if request.method == 'POST':
        if 'renovar_rut' in request.POST:
            rut_renovar = request.POST.get('renovar_rut')
            metodo_pago = request.POST.get('metodo_pago')
            cliente_renovado = Cliente.objects.filter(rut=rut_renovar).first()
            if cliente_renovado:
                cliente_renovado.fecha_inicio_plan = timezone.now().date()
                cliente_renovado.metodo_pago = metodo_pago
                cliente_renovado.save()
                messages.success(request, f"El Cliente {cliente_renovado.nombre} {cliente_renovado.apellido} ({cliente_renovado.rut}) ha sido renovado correctamente.")
                rut_buscado = rut_renovar

        elif 'rut' in request.POST:
            rut_buscado = request.POST.get('rut')

    clientes = Cliente.objects.filter(rut__icontains=rut_buscado) if rut_buscado else Cliente.objects.all()

    return render(request, 'core/renovarCliente.html', {
        'clientes': clientes,
        'rut_buscado': rut_buscado,
        'planes_personalizados': PlanPersonalizado.objects.all(),
        'tipos_mensualidad': ['Estudiante', 'Normal']
    })
@admin_required
def modificar_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        apellido = request.POST.get('apellido')
        rut = request.POST.get('rut')
        correo = request.POST.get('correo')
        telefono = request.POST.get('telefono')

        if not nombre or not apellido or not rut or not correo or not telefono:
            messages.error(request, "⚠️ Todos los campos obligatorios deben estar completos.")
        else:
            try:
                cliente.nombre = nombre
                cliente.apellido = apellido
                cliente.rut = rut
                cliente.correo = correo
                cliente.telefono = telefono
                cliente.save()
                messages.success(request, "✅ Cliente modificado exitosamente.")
                return redirect('renovarCliente')  
            except Exception as e:
                messages.error(request, f"❌ Error al modificar el cliente: {str(e)}")

    return render(request, 'core/modificar_cliente.html', {'cliente': cliente})

@admin_required
def eliminar_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == 'POST':
        cliente.delete()
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
        if cliente:
            hoy = timezone.now().date()
            inicio = cliente.fecha_fin_plan or cliente.fecha_inicio_plan or hoy
            nueva_fecha = inicio + relativedelta(months=meses)

            cliente.fecha_fin_plan = nueva_fecha
            cliente.save()

        return redirect('renovarCliente')


@admin_required
def cambiar_tipo_plan_mensual(request):
    if request.method == 'POST':
        rut = request.POST.get('rut_cliente')
        nuevo_plan = request.POST.get('nuevo_plan')
        cliente = Cliente.objects.filter(rut=rut).first()
        if cliente:
            from .models import Mensualidad
            mensualidad = Mensualidad.objects.filter(tipo=nuevo_plan).first()
            if mensualidad:
                cliente.mensualidad = mensualidad
                cliente.save()
        # Redirige con el RUT como parámetro GET
        return HttpResponseRedirect(reverse('renovarCliente') + f'?rut={rut}')
    return redirect('renovarCliente')


@admin_required
def cambiar_plan_personalizado(request):
    if request.method == 'POST':
        rut = request.POST.get('rut_cliente')
        nuevo_plan = request.POST.get('nuevo_plan')

        cliente = Cliente.objects.filter(rut=rut).first()
        if cliente and nuevo_plan:
            from .models import PlanPersonalizado
            try:
                plan = PlanPersonalizado.objects.get(id=int(nuevo_plan))
                cliente.plan_personalizado = plan
                cliente.save()
            except (PlanPersonalizado.DoesNotExist, ValueError):
                pass

        return HttpResponseRedirect(reverse('renovarCliente') + f'?rut={rut}')
    return redirect('renovarCliente')

def productos(request):
    productos = Producto.objects.all()

    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        cantidad = int(request.POST.get('cantidad'))

        producto = Producto.objects.get(id=producto_id)

        if cantidad > producto.stock:
            messages.error(request, "No hay suficiente stock.")
        else:
            Venta.objects.create(producto=producto, cantidad=cantidad)
            messages.success(request, "Venta registrada exitosamente.")

        return redirect('productos')  

    return render(request, 'core/productos.html', {'productos': productos})




@admin_required
def agregar_producto(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto agregado correctamente.')
            return redirect('productos')
        else:
            messages.error(request, 'Corrige los errores del formulario.')
    else:
        form = ProductoForm()

    return render(request, 'core/agregar_producto.html', {'form': form})


def registrar_venta(request):
    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        cantidad = int(request.POST.get('cantidad'))

        producto = Producto.objects.get(id=producto_id)

        if producto.stock <= 0:
            messages.error(request, f"❌ No quedan unidades del producto '{producto.nombre}'.")
            return redirect('productos')  #

        if cantidad > producto.stock:
            messages.error(request, f"❌ Solo quedan {producto.stock} unidades de '{producto.nombre}'.")
            return redirect('productos')

        producto.stock -= cantidad
        producto.save()
        messages.success(request, f"✅ Venta registrada para '{producto.nombre}', stock actualizado.")
        return redirect('productos')
    
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
        messages.success(request, "🗑️ Producto eliminado correctamente.")
    else:
        messages.error(request, "Método no permitido.")

    return redirect('productos')

@admin_required
def dashboard(request):
    hoy = localdate()
    inicio_mes = hoy.replace(day=1)

    # Total clientes activos
    total_clientes = Cliente.objects.count()

    # Clientes activos del mes
    clientes_activos_mes = (
        Asistencia.objects
        .filter(fecha__gte=inicio_mes)
        .values('cliente')
        .distinct()
        .count()
    )
    clientes_nuevos_mes = Cliente.objects.filter(fecha_inicio_plan__gte=inicio_mes).count()

    # Últimos 6 meses
    hoy = now().date()
    seis_meses_antes = hoy - timedelta(days=180)

    # Nuevos clientes por mes
    clientes_mes_qs = (
        Cliente.objects
        .filter(fecha_inicio_plan__gte=seis_meses_antes)
        .extra(select={'month': "strftime('%%Y-%%m', fecha_inicio_plan)"})
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    nuevos_clientes_mes = {item['month']: item['count'] for item in clientes_mes_qs}

    # Clientes por tipo de plan por mes
    clientes_por_plan = (
        Cliente.objects
        .filter(fecha_inicio_plan__gte=seis_meses_antes)
        .extra(select={'month': "strftime('%%Y-%%m', fecha_inicio_plan)"})
        .values('month')
      .annotate(
            estudiante_count=Count('id', filter=Q(mensualidad__tipo='Estudiante')),
            normal_count=Count('id', filter=Q(mensualidad__tipo='Normal')),
 
        )
                .order_by('month')
    )
    clientes_plan_data = {}
    for item in clientes_por_plan:
        month = item['month']
        clientes_plan_data[month] = {
        "estudiante": item['estudiante_count'],
        "normal": item['normal_count'],
    }

    # Últimas 10 ventas
    ultimas_ventas = (
        Venta.objects
        .select_related('producto')
        .order_by('-fecha_venta')[:10]
        .values('fecha_venta', 'producto__nombre', 'cantidad', 'producto__precio_venta')
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

    # Ingresos por ventas
    ventas_mes_qs = (
        Venta.objects
        .filter(fecha_venta__gte=seis_meses_antes)
        .extra(select={'month': "strftime('%%Y-%%m', fecha_venta)"})
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

    top_planes_personalizados_qs = (
    Cliente.objects
    .filter(plan_personalizado__isnull=False)
    .values('plan_personalizado__nombre_plan')
    .annotate(total=Count('id'))
    .order_by('-total')[:5]
)

    top_planes_personalizados = [
    {
        "nombre": item['plan_personalizado__nombre_plan'],
        "total": item['total']
    }
    for item in top_planes_personalizados_qs
]
    ingresos_mes = {item['month']: item['ingresos'] or 0 for item in ventas_mes_qs}

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
    }

    return render(request, "core/dashboard.html", context)

# ===========================
# REDIRECCIÓN INICIAL
# ===========================
def home(request):
    return redirect('login')

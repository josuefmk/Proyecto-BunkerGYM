from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('', views.home, name='home'),

    # Protegidas
    path('index/', views.index, name='index'),
    path('registro/', views.registro_cliente, name='registro_cliente'),
    path('asistencia/', views.asistencia_cliente, name='asistencia_cliente'),
    path('lista/', views.listaCliente, name='listaCliente'),
    path('listaCliente/json/', views.listaCliente_json, name='listaCliente_json'),
    path('renovar/', views.renovarCliente, name='renovarCliente'),
    path('historialCliente/', views.historial_cliente, name='historial_cliente'),
    path('cambiar-tipo-plan-mensual/', views.cambiar_tipo_plan_mensual, name='cambiar_tipo_plan_mensual'),
    path('cambiar-plans-personalizados/', views.cambiar_planes_personalizados, name='cambiar_planes_personalizados'),
    path('renovar-plan-personalizado/', views.renovar_plan_personalizado, name='renovar_plan_personalizado'),
    path("cambiar-subplan/", views.cambiar_sub_plan, name="cambiar_sub_plan"),
    path('registrar_sesion/', views.registrar_sesion, name='registrar_sesion'),
    path('productos/', views.productos, name='productos'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('productos/agregar/', views.agregar_producto, name='agregar_producto'),
    path('precios/panel/', views.panel_precios, name='panel_precios'),
    path('productos/registrar-venta/', views.registrar_venta, name='registrar_venta'),
    path('editar_producto/<int:producto_id>/', views.editar_producto, name='editar_producto'),
    path('eliminar_producto/<int:producto_id>/', views.eliminar_producto, name='eliminar_producto'),
    path('agregar-meses-plan/', views.agregar_meses_plan, name='agregar_meses_plan'),
    path('eliminar-cliente/<int:cliente_id>/', views.eliminar_cliente, name='eliminar_cliente'),
    path('modificar-cliente/<int:cliente_id>/', views.modificar_cliente, name='modificar_cliente'),
    #path('api/registrar_asistencia/', views.api_registrar_asistencia, name='api_registrar_asistencia'),

    # Login y logout
    path('login/', views.login_admin, name='login'),
    path('logout/', views.logout_admin, name='logout'),
]

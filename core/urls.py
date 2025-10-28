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
    path("historial_ventas/", views.historial_ventas, name="historial_ventas"),
    path('editar_producto/<int:producto_id>/', views.editar_producto, name='editar_producto'),
    path('eliminar_producto/<int:producto_id>/', views.eliminar_producto, name='eliminar_producto'),
    path('agregar-meses-plan/', views.agregar_meses_plan, name='agregar_meses_plan'),
    path('eliminar-cliente/<int:cliente_id>/', views.eliminar_cliente, name='eliminar_cliente'),
    path('modificar-cliente/<int:cliente_id>/', views.modificar_cliente, name='modificar_cliente'),
    path('asistencia_kine_nutri/', views.asistencia_kine_nutri, name='asistencia_kine_nutri'),
    path('registrar_cliente_externo/', views.registrar_cliente_externo, name='registrar_cliente_externo'),
    path('agregar_stock/', views.agregar_stock, name='agregar_stock'),
   path('agendar_hora_box/', views.agendar_hora_box, name='agendar_hora_box'),
    path('agendar_hora_box/listar/', views.listar_agendas, name='listar_agendas'),
    path('agendar_hora_box/<int:agenda_id>/cambiar_estado/', views.cambiar_estado_agenda, name='cambiar_estado_agenda'),
    path('agendar_hora_box/<int:agenda_id>/eliminar/', views.eliminar_agenda, name='eliminar_agenda'),
    path('registro_pase_diario/', views.registro_pase_diario, name='registro_pase_diario'),
    path('agenda_pf/', views.agenda_pf, name='agenda_pf'),
 path('agenda_pf/<int:agenda_id>/no_asistio/', views.marcar_no_asistio, name='marcar_no_asistio'),
     path('agenda_pf/listar/', views.listar_agenda_pf, name='listar_agenda_pf'),
         path('agenda_pf/<int:agenda_id>/eliminar/', views.eliminar_agenda_pf, name='eliminar_agenda_pf'),
    #path('api/registrar_asistencia/', views.api_registrar_asistencia, name='api_registrar_asistencia')

    # Login y logout
    path('login/', views.login_admin, name='login'),
    path('logout/', views.logout_admin, name='logout'),
]

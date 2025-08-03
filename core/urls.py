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
    path('cambiar-tipo-plan-mensual/', views.cambiar_tipo_plan_mensual, name='cambiar_tipo_plan_mensual'),
    path('cambiar-plan-personalizado/', views.cambiar_plan_personalizado, name='cambiar_plan_personalizado'),
    path('productos/', views.productos, name='productos'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('productos/agregar/', views.agregar_producto, name='agregar_producto'),
    path('editar_producto/<int:producto_id>/', views.editar_producto, name='editar_producto'),
    path('eliminar_producto/<int:producto_id>/', views.eliminar_producto, name='eliminar_producto'),

    # Login y logout
    path('login/', views.login_admin, name='login'),
    path('logout/', views.logout_admin, name='logout'),
]

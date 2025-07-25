from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('', views.home, name='home'),

    # Protegidas
    path('index/', views.index, name='index'),
    path('registro/', views.registro_cliente, name='registro_cliente'),
    path('asistencia/', views.asistencia_cliente, name='asistencia_cliente'),

    # Login y logout

path('login/', views.login_admin, name='login'),
path('logout/', views.logout_admin, name='logout'),
]

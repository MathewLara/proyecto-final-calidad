from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoriaViewSet, VideojuegoViewSet, 
    UsuarioViewSet, ReservaViewSet, VentaViewSet
)

router = DefaultRouter()
router.register(r'categorias', CategoriaViewSet)
router.register(r'videojuegos', VideojuegoViewSet)
router.register(r'usuarios', UsuarioViewSet)
router.register(r'reservas', ReservaViewSet)
router.register(r'ventas', VentaViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
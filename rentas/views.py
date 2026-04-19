from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from .models import Categoria, Videojuego, Usuario, Reserva, Venta
from .serializers import (
    CategoriaSerializer, VideojuegoSerializer, 
    UsuarioSerializer, ReservaSerializer, VentaSerializer
)
from rest_framework.decorators import action
from django.utils import timezone
from datetime import timedelta
import random

class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    # Replicamos tu [HttpDelete("{id}")]
    def destroy(self, request, *args, **kwargs):
        instancia = self.get_object()
        instancia.activo = False # O instancia.is_active = False para el Usuario
        instancia.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # Replicamos tu [HttpPut("activar/{id}")]
    @action(detail=True, methods=['put'])
    def activar(self, request, pk=None):
        instancia = self.get_object()
        instancia.activo = True
        instancia.save()
        return Response({"mensaje": "Reactivado con éxito."})

class VideojuegoViewSet(viewsets.ModelViewSet):
    queryset = Videojuego.objects.all()
    serializer_class = VideojuegoSerializer
    # Replicamos tu [HttpDelete("{id}")]
    def destroy(self, request, *args, **kwargs):
        instancia = self.get_object()
        instancia.activo = False # O instancia.is_active = False para el Usuario
        instancia.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # Replicamos tu [HttpPut("activar/{id}")]
    @action(detail=True, methods=['put'])
    def activar(self, request, pk=None):
        instancia = self.get_object()
        instancia.activo = True
        instancia.save()
        return Response({"mensaje": "Reactivado con éxito."})

class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer

class ReservaViewSet(viewsets.ModelViewSet):
    queryset = Reserva.objects.all()
    serializer_class = ReservaSerializer

    # Sobreescribimos el guardado para replicar tu lógica de C#
    def perform_create(self, serializer):
        videojuego = serializer.validated_data['videojuego']
        cantidad = serializer.validated_data['cantidad']
        
        # 1. Descontar Stock
        videojuego.stock -= cantidad
        videojuego.save()

        # 2. Generar Código y Fechas
        codigo_generado = f"RES-{random.randint(1000, 9999)}"
        fecha_expiracion = timezone.now() + timedelta(hours=24)

        # Guardamos inyectando estos datos automáticos
        serializer.save(
            codigo_reserva=codigo_generado,
            fecha_expiracion=fecha_expiracion,
            estado="Pendiente"
        )

    # Replicamos tu [HttpPut("cancelar/{id}")]
    @action(detail=True, methods=['put'])
    def cancelar(self, request, pk=None):
        reserva = self.get_object()
        
        if reserva.estado != "Pendiente":
            return Response({"error": "Solo se pueden cancelar reservas pendientes."}, status=status.HTTP_400_BAD_REQUEST)

        # Restaurar stock
        videojuego = reserva.videojuego
        videojuego.stock += reserva.cantidad
        videojuego.save()

        # Cambiar estado
        reserva.estado = "Cancelada"
        reserva.save()

        return Response({"mensaje": "Reserva cancelada y stock restaurado."})

class VentaViewSet(viewsets.ModelViewSet):
    queryset = Venta.objects.all()
    serializer_class = VentaSerializer
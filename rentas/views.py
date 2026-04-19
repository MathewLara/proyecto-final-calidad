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
from django.db.models import Sum
from django.utils.timezone import make_aware
import datetime
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

    # 1. INTERCEPTAMOS EL BOTÓN "DESACTIVAR" (Soft Delete)
    def destroy(self, request, *args, **kwargs):
        usuario = self.get_object()
        usuario.is_active = False # Usamos is_active porque así lo pide el modelo de Django
        usuario.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # 2. CREAMOS EL BOTÓN "REACTIVAR"
    @action(detail=True, methods=['put'])
    def activar(self, request, pk=None):
        usuario = self.get_object()
        usuario.is_active = True
        usuario.save()
        return Response({"mensaje": "Usuario reactivado con éxito."}, status=status.HTTP_200_OK)

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
    

    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        try:
            # 1. Obtenemos el inicio y fin del día actual de forma manual
            hoy = timezone.now().date()
            inicio_dia = make_aware(datetime.datetime.combine(hoy, datetime.time.min))
            fin_dia = make_aware(datetime.datetime.combine(hoy, datetime.time.max))
            
            # 2. Sumamos el dinero (Histórico total)
            total_ganancias = Venta.objects.aggregate(Sum('total'))['total__sum'] or 0
            
            # 3. Contamos ventas usando un rango (range), que es 100% compatible con SQLite
            ventas_hoy = Venta.objects.filter(fecha_venta__range=(inicio_dia, fin_dia)).count()
            
            # 4. Stock bajo
            poco_stock = Videojuego.objects.filter(stock__lt=5, activo=True).values('titulo', 'stock')
            
            return Response({
                "total_ganancias": float(total_ganancias),
                "ventas_hoy": ventas_hoy,
                "poco_stock": list(poco_stock)
            })
        except Exception as e:
            print(f"Error en stats: {e}")
            return Response({"error": str(e)}, status=500)
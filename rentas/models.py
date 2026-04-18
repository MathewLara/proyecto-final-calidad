from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser

class Categoria(models.Model):
    # Django agrega el campo 'id' automáticamente, no necesitas declararlo
    nombre = models.CharField(max_length=50, help_text="El nombre no puede exceder los 50 caracteres.")
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

class Videojuego(models.Model):
    titulo = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=500)
    precio = models.DecimalField(max_digits=18, decimal_places=2)
    stock = models.IntegerField()
    url_imagen = models.URLField(max_length=500, null=True, blank=True)
    fecha_lanzamiento = models.DateField()
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='videojuegos')
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.titulo

class Usuario(AbstractUser):
    # AbstractUser ya trae: username, password, email, first_name, last_name, is_active
    # Solo agregamos lo que no tiene:
    rol = models.CharField(max_length=50, default="Vendedor")

    def __str__(self):
        return self.username

class Reserva(models.Model):
    codigo_reserva = models.CharField(max_length=50, null=True, blank=True)
    cliente_nombre = models.CharField(max_length=100)
    
    # NUEVO CAMPO: Necesario para tu validación de pytest
    cliente_cedula = models.CharField(max_length=10, help_text="Cédula ecuatoriana de 10 dígitos")
    
    cliente_contacto = models.CharField(max_length=100)
    fecha_reserva = models.DateTimeField(default=timezone.now)
    fecha_expiracion = models.DateTimeField()
    estado = models.CharField(max_length=50, default="Pendiente")
    videojuego = models.ForeignKey(Videojuego, on_delete=models.PROTECT, related_name='reservas')
    cantidad = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"Reserva {self.codigo_reserva} - {self.cliente_nombre}"

class Venta(models.Model):
    fecha_venta = models.DateTimeField(default=timezone.now)
    total = models.DecimalField(max_digits=18, decimal_places=2)
    codigo_reserva = models.CharField(max_length=50, null=True, blank=True)
    cliente_nombre = models.CharField(max_length=100)
    
    # NUEVO CAMPO: Para mantener coherencia en la facturación
    cliente_cedula = models.CharField(max_length=10)
    
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='ventas')

    def __str__(self):
        return f"Venta {self.id} - {self.cliente_nombre}"

class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='detalles')
    videojuego = models.ForeignKey(Videojuego, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=18, decimal_places=2)

    def __str__(self):
        return f"Detalle de Venta {self.venta.id} - {self.videojuego.titulo}"
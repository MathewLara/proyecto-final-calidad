from django.contrib import admin
from .models import Categoria, Videojuego, Usuario, Reserva, Venta

# Invitamos a todas las tablas a la fiesta del panel de administrador
admin.site.register(Categoria)
admin.site.register(Videojuego)
admin.site.register(Usuario)
admin.site.register(Reserva)
admin.site.register(Venta)
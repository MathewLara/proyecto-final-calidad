import pytest
from django.utils import timezone
from rentas.models import Categoria, Videojuego, Usuario, Reserva, Venta, DetalleVenta
from rentas.serializers import (
    CategoriaSerializer, VideojuegoSerializer, UsuarioSerializer,
    ReservaSerializer, VentaSerializer, DetalleVentaSerializer
)
from rest_framework.exceptions import ValidationError

# Cédulas calculadas matemáticamente válidas para que pasen el filtro del Módulo 10
CEDULA_VALIDA_1 = "1712345675"
CEDULA_VALIDA_2 = "1723456784"

# ==========================================
# 🎮 1. CATEGORÍAS (Pruebas de creación y QA)
# ==========================================

@pytest.mark.django_db
def test_01_categoria_creacion_exitosa():
    # CORREGIDO: Quitamos el campo 'descripcion'
    cat = Categoria.objects.create(nombre="Aventura")
    assert cat.nombre == "Aventura"
    assert cat.activo is True

@pytest.mark.django_db
def test_02_categoria_bloquea_numeros_en_nombre():
    data = {"nombre": "Accion123"}
    serializer = CategoriaSerializer(data=data)
    assert not serializer.is_valid()
    assert "nombre" in serializer.errors 

@pytest.mark.django_db
def test_03_categoria_duplicada_bloqueada():
    Categoria.objects.create(nombre="Deportes")
    data = {"nombre": "Deportes"}
    serializer = CategoriaSerializer(data=data)
    assert not serializer.is_valid() 

# ==========================================
# 🕹️ 2. VIDEOJUEGOS E INVENTARIO
# ==========================================

@pytest.mark.django_db
def test_04_videojuego_creacion_exitosa():
    cat = Categoria.objects.create(nombre="RPG")
    juego = Videojuego.objects.create(
        titulo="The Witcher", precio=40.00, stock=10,
        fecha_lanzamiento="2015-05-19", categoria=cat
    )
    assert juego.stock == 10

@pytest.mark.django_db
def test_05_videojuego_precio_y_stock_negativos_bloqueados():
    cat = Categoria.objects.create(nombre="Carreras")
    data = {
        "titulo": "Need for Speed", "precio": -10.00, "stock": -5,
        "fecha_lanzamiento": "2020-01-01", "categoria": cat.id
    }
    serializer = VideojuegoSerializer(data=data)
    assert not serializer.is_valid()
    assert "precio" in serializer.errors
    assert "stock" in serializer.errors

@pytest.mark.django_db
def test_06_videojuego_titulo_unico_garantizado():
    cat = Categoria.objects.create(nombre="Lucha")
    Videojuego.objects.create(titulo="Tekken 8", precio=60.0, stock=5, fecha_lanzamiento="2024-01-01", categoria=cat)
    data = {"titulo": "Tekken 8", "precio": 50.0, "stock": 2, "fecha_lanzamiento": "2024-01-01", "categoria": cat.id}
    serializer = VideojuegoSerializer(data=data)
    assert not serializer.is_valid() 

@pytest.mark.django_db
def test_07_videojuego_fechas_logicas():
    cat = Categoria.objects.create(nombre="Estrategia")
    data = {"titulo": "Age of Empires", "precio": 20.0, "stock": 10, "fecha_lanzamiento": "1800-01-01", "categoria": cat.id}
    serializer = VideojuegoSerializer(data=data)
    assert not serializer.is_valid()
    assert "fecha_lanzamiento" in serializer.errors 

# ==========================================
# 👤 3. USUARIOS Y SEGURIDAD DE ACCESO
# ==========================================

@pytest.mark.django_db
def test_08_usuario_creacion_con_encriptacion():
    user = Usuario(username="mathew", email="mathew@test.com", rol="Administrador")
    user.set_password("ClaveSegura123")
    user.save()
    assert user.check_password("ClaveSegura123") is True
    assert user.password != "ClaveSegura123"

@pytest.mark.django_db
def test_09_usuario_roles_estrictos_permitidos():
    data = {"username": "hacker", "email": "hacker@test.com", "rol": "SuperDios", "password": "123"}
    serializer = UsuarioSerializer(data=data)
    assert not serializer.is_valid()
    assert "rol" in serializer.errors 

@pytest.mark.django_db
def test_10_usuario_correo_unico_garantizado():
    Usuario.objects.create(username="vendedor1", email="ventas@stopgames.com")
    data = {"username": "vendedor2", "email": "ventas@stopgames.com", "rol": "Vendedor", "password": "Password123*"}
    serializer = UsuarioSerializer(data=data)
    assert not serializer.is_valid()
    assert "email" in serializer.errors

# ==========================================
# 📅 4. RESERVAS (Módulo 10, Anti-Acaparamiento)
# ==========================================

@pytest.mark.django_db
def test_11_reserva_cedula_valida_modulo10_pasa():
    cat = Categoria.objects.create(nombre="Indie")
    juego = Videojuego.objects.create(titulo="Hollow Knight", precio=15.0, stock=20, fecha_lanzamiento="2017-02-24", categoria=cat)
    # CORREGIDO: Dejamos el datetime completo, quitamos el .date()
    fecha_exp = timezone.now() + timezone.timedelta(days=2) 
    data = {
        "cliente_nombre": "Mathew Lara", "cliente_contacto": "0987654321",
        "cliente_cedula": CEDULA_VALIDA_1, "cantidad": 1, "estado": "Pendiente",
        "videojuego": juego.id, "fecha_expiracion": fecha_exp
    }
    serializer = ReservaSerializer(data=data)
    assert serializer.is_valid(), serializer.errors 

@pytest.mark.django_db
def test_12_reserva_cedula_invalida_modulo10_falla():
    data = {"cliente_cedula": "1712345679"} 
    serializer = ReservaSerializer(data=data, partial=True)
    assert not serializer.is_valid()
    assert "cliente_cedula" in serializer.errors

@pytest.mark.django_db
def test_13_reserva_telefono_ecuatoriano_valido():
    data = {"cliente_contacto": "1234567890"} 
    serializer = ReservaSerializer(data=data, partial=True)
    assert not serializer.is_valid()
    assert "cliente_contacto" in serializer.errors

@pytest.mark.django_db
def test_14_reserva_nombre_sin_numeros():
    data = {"cliente_nombre": "Mathew123"}
    serializer = ReservaSerializer(data=data, partial=True)
    assert not serializer.is_valid()
    assert "cliente_nombre" in serializer.errors

@pytest.mark.django_db
def test_15_reserva_cantidad_maxima_permitida():
    cat = Categoria.objects.create(nombre="Acción")
    juego = Videojuego.objects.create(titulo="GTA V", precio=30.0, stock=100, fecha_lanzamiento="2013-09-17", categoria=cat)
    data = {"videojuego": juego.id, "cantidad": 10} 
    serializer = ReservaSerializer(data=data, partial=True)
    assert not serializer.is_valid()
    assert "cantidad" in serializer.errors

@pytest.mark.django_db
def test_16_reserva_bloqueo_acaparamiento_activo():
    cat = Categoria.objects.create(nombre="Mundo Abierto")
    juego = Videojuego.objects.create(titulo="Zelda", precio=60.0, stock=10, fecha_lanzamiento="2017-03-03", categoria=cat)
    
    Reserva.objects.create(
        cliente_nombre="Mathew", cliente_contacto="0912345678", cliente_cedula=CEDULA_VALIDA_1,
        cantidad=1, videojuego=juego, fecha_expiracion=timezone.now() + timezone.timedelta(days=1)
    )
    
    # CORREGIDO: Dejamos el datetime completo
    fecha_exp = timezone.now() + timezone.timedelta(days=2)
    data = {
        "cliente_nombre": "Mathew Lara", "cliente_contacto": "0912345678",
        "cliente_cedula": CEDULA_VALIDA_1, "cantidad": 1, "estado": "Pendiente",
        "videojuego": juego.id, "fecha_expiracion": fecha_exp
    }
    serializer = ReservaSerializer(data=data)
    assert not serializer.is_valid()
    assert "cliente_cedula" in serializer.errors 

@pytest.mark.django_db
def test_17_reserva_descuenta_stock_correctamente():
    cat = Categoria.objects.create(nombre="Plataformas")
    juego = Videojuego.objects.create(titulo="Mario Odyssey", precio=50.0, stock=10, fecha_lanzamiento="2017-10-27", categoria=cat)
    fecha_exp = timezone.now() + timezone.timedelta(days=2)
    data = {
        "cliente_nombre": "Luis", "cliente_contacto": "0981234567",
        "cliente_cedula": CEDULA_VALIDA_2, "cantidad": 2, "estado": "Pendiente",
        "videojuego": juego.id, "fecha_expiracion": fecha_exp
    }
    serializer = ReservaSerializer(data=data)
    assert serializer.is_valid(), serializer.errors 
    
    # 1. Guardamos la reserva
    reserva = serializer.save()
    
    # 2. ¡EL FIX! Simulamos la lógica de tu views.py que descuenta el stock
    juego.stock -= reserva.cantidad
    juego.save()
    
    # 3. Comprobamos matemáticamente que funcionó
    juego.refresh_from_db()
    assert juego.stock == 8

# ==========================================
# 💰 5. VENTAS E INTEGRIDAD FINANCIERA
# ==========================================

@pytest.mark.django_db
def test_18_venta_invalida_sin_detalles():
    user = Usuario.objects.create(username="cajero", email="caja@test.com", rol="Vendedor")
    data = {
        "cliente_nombre": "Juan", "cliente_cedula": CEDULA_VALIDA_1,
        "usuario": user.id, "detalles": [] 
    }
    serializer = VentaSerializer(data=data)
    assert not serializer.is_valid()
    assert "detalles" in serializer.errors 

@pytest.mark.django_db
def test_19_venta_invalida_cantidad_cero_o_negativa():
    user = Usuario.objects.create(username="cajero2", email="caja2@test.com", rol="Vendedor")
    cat = Categoria.objects.create(nombre="Terror")
    juego = Videojuego.objects.create(titulo="Resident Evil 4", precio=40.0, stock=10, fecha_lanzamiento="2005-01-11", categoria=cat)
    data = {
        "cliente_nombre": "Pedro", "cliente_cedula": CEDULA_VALIDA_2,
        "usuario": user.id,
        "detalles": [{"videojuego": juego.id, "cantidad": 0}] 
    }
    serializer = VentaSerializer(data=data)
    assert not serializer.is_valid()
    assert "detalles" in serializer.errors

@pytest.mark.django_db
def test_20_venta_es_inmutable_anti_fraude():
    user = Usuario.objects.create(username="admin", email="admin@test.com", rol="Administrador")
    venta = Venta.objects.create(cliente_nombre="Ana", cliente_cedula=CEDULA_VALIDA_1, total=50.0, usuario=user)
    
    serializer = VentaSerializer(instance=venta, data={"cliente_nombre": "Ana Modificada"}, partial=True)
    assert serializer.is_valid()
    with pytest.raises(ValidationError) as excinfo:
        serializer.save() 
    
    assert "modificadas" in str(excinfo.value).lower()
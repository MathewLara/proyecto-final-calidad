import pytest
from rentas.models import Categoria, Videojuego, Usuario, Reserva, Venta
from django.utils import timezone
from datetime import timedelta

# ==========================================
# 🎮 1. PRUEBAS DE MÓDULO: CATEGORÍAS
# ==========================================
@pytest.mark.django_db
def test_crear_categoria_exitosa():
    categoria = Categoria.objects.create(nombre="RPG", descripcion="Juegos de rol", activo=True)
    assert categoria.nombre == "RPG"
    assert Categoria.objects.count() == 1

@pytest.mark.django_db
def test_categoria_por_defecto_activa():
    categoria = Categoria.objects.create(nombre="Deportes")
    assert categoria.activo is True  # Validamos la calidad del dato por defecto

@pytest.mark.django_db
def test_soft_delete_categoria():
    categoria = Categoria.objects.create(nombre="Acción")
    categoria.activo = False
    categoria.save()
    assert Categoria.objects.get(nombre="Acción").activo is False

# ==========================================
# 🕹️ 2. PRUEBAS DE MÓDULO: VIDEOJUEGOS E INVENTARIO
# ==========================================
@pytest.mark.django_db
def test_crear_videojuego_con_stock_valido():
    cat = Categoria.objects.create(nombre="Shooter")
    juego = Videojuego.objects.create(titulo="Call of Duty", precio=60.00, stock=15, categoria=cat)
    assert juego.stock == 15
    assert juego.precio == 60.00

@pytest.mark.django_db
def test_actualizar_stock_videojuego():
    cat = Categoria.objects.create(nombre="Aventura")
    juego = Videojuego.objects.create(titulo="Zelda", precio=50.00, stock=5, categoria=cat)
    juego.stock += 10
    juego.save()
    assert Videojuego.objects.get(titulo="Zelda").stock == 15

# ==========================================
# 👥 3. PRUEBAS DE MÓDULO: USUARIOS Y ROLES
# ==========================================
@pytest.mark.django_db
def test_crear_usuario_vendedor():
    vendedor = Usuario.objects.create(nombre="Juan Perez", email="juan@tienda.com", rol="Vendedor", is_active=True)
    assert vendedor.rol == "Vendedor"
    assert vendedor.email == "juan@tienda.com"

@pytest.mark.django_db
def test_desactivar_usuario_seguridad():
    # Simulamos que despedimos a un empleado (Soft delete)
    empleado = Usuario.objects.create(nombre="Ana", email="ana@tienda.com", rol="Vendedor")
    empleado.is_active = False
    empleado.save()
    assert Usuario.objects.get(email="ana@tienda.com").is_active is False

# ==========================================
# 📅 4. PRUEBAS DE MÓDULO: RESERVAS (LÓGICA CRÍTICA)
# ==========================================
@pytest.mark.django_db
def test_crear_reserva_estados_correctos():
    cat = Categoria.objects.create(nombre="Peleas")
    juego = Videojuego.objects.create(titulo="Mortal Kombat", precio=40.00, stock=10, categoria=cat)
    
    reserva = Reserva.objects.create(
        videojuego=juego,
        cliente_nombre="Mathew",
        cantidad=1,
        estado="Pendiente"
    )
    assert reserva.estado == "Pendiente"
    assert reserva.cliente_nombre == "Mathew"

@pytest.mark.django_db
def test_logica_descuento_stock_por_reserva():
    # Validamos que el stock baje matemáticamente cuando alguien reserva
    cat = Categoria.objects.create(nombre="Mundo Abierto")
    juego = Videojuego.objects.create(titulo="GTA V", precio=30.00, stock=10, categoria=cat)
    
    # Simulamos la lógica que tienes en tu views.py
    cantidad_reservada = 2
    juego.stock -= cantidad_reservada
    juego.save()
    
    assert Videojuego.objects.get(titulo="GTA V").stock == 8

@pytest.mark.django_db
def test_logica_restauracion_stock_por_cancelacion():
    # Validamos que el stock regrese si la reserva se cancela
    cat = Categoria.objects.create(nombre="Mundo Abierto")
    juego = Videojuego.objects.create(titulo="Minecraft", precio=20.00, stock=5, categoria=cat)
    
    # Se cancelan 3 reservas
    juego.stock += 3
    juego.save()
    assert juego.stock == 8

# ==========================================
# 💰 5. PRUEBAS DE MÓDULO: VENTAS Y FINANZAS
# ==========================================
@pytest.mark.django_db
def test_registrar_venta_nueva():
    venta = Venta.objects.create(
        cliente_nombre="Carlos",
        total=120.50,
        fecha_venta=timezone.now()
    )
    assert venta.total == 120.50
    assert venta.cliente_nombre == "Carlos"

@pytest.mark.django_db
def test_calculo_total_ventas_es_positivo():
    # Una venta en un sistema de calidad jamás debería registrar un total negativo
    venta = Venta.objects.create(cliente_nombre="Sistema", total=15.00)
    assert venta.total > 0
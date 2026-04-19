from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.password_validation import validate_password
from .models import Categoria, Videojuego, Usuario, Reserva, Venta, DetalleVenta
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.db import transaction
import re

# ─── Función reutilizable ────────────────────────────────────────────────────
def validar_cedula_ecuatoriana(value):
    if not value.isdigit() or len(value) != 10:
        raise serializers.ValidationError("La cédula debe contener exactamente 10 dígitos numéricos.")

    # Regla 1: El código de provincia (primeros 2 dígitos) debe ser entre 01 y 24
    provincia = int(value[0:2])
    if provincia < 1 or provincia > 24:
        raise serializers.ValidationError("El código de provincia de la cédula es inválido.")

    # Regla 2: El tercer dígito para personas naturales debe ser menor a 6
    tercer_digito = int(value[2])
    if tercer_digito >= 6:
        raise serializers.ValidationError("El tercer dígito es inválido para personas naturales.")

    # Regla 3: Algoritmo Módulo 10
    coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    total = 0
    for i in range(9):
        valor = int(value[i]) * coeficientes[i]
        if valor >= 10:
            valor -= 9  # Si el resultado es 10 o más, se le resta 9
        total += valor

    # Cálculo del dígito verificador esperado
    digito_verificador_calculado = 10 - (total % 10)
    if digito_verificador_calculado == 10:
        digito_verificador_calculado = 0

    # Comparar con el último dígito ingresado
    if digito_verificador_calculado != int(value[9]):
        raise serializers.ValidationError("La cédula ingresada no pasó la validación del algoritmo.")

    return value
import re # Asegúrate de importar la librería de expresiones regulares arriba del todo

# ─── Funciones reutilizables de Validación ────────────────────────────────────

def validar_solo_letras(value, campo):
    """Valida que un campo de texto no contenga números ni caracteres raros."""
    value_str = str(value).strip()
    # Regex: Solo letras mayúsculas, minúsculas, tildes, ñ y espacios.
    if not re.match(r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$', value_str):
        raise serializers.ValidationError(f"El {campo} solo debe contener letras. No se aceptan números ni símbolos.")
    
    if len(value_str) < 3:
        raise serializers.ValidationError(f"El {campo} es demasiado corto. Debe tener al menos 3 caracteres.")
    return value_str

def validar_telefono_ecuador(value):
    """Valida que el número sea celular ecuatoriano o teléfono fijo estándar."""
    value_str = str(value).strip()
    # Regex: Exactamente 10 dígitos numéricos y debe empezar con 0 (Ej: 098...)
    if not re.match(r'^0\d{9}$', value_str):
        raise serializers.ValidationError("El número de contacto debe tener exactamente 10 dígitos numéricos y comenzar con '0'.")
    return value_str

def validar_email_estricto(value):
    """Añade una capa de validación extra para la estructura del correo."""
    value_str = str(value).strip()
    if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', value_str):
        raise serializers.ValidationError("El formato del correo electrónico no es válido.")
    return value_str

# ─── Serializers simples ─────────────────────────────────────────────────────

class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = '__all__'

    def validate_nombre(self, value):
        # Buscamos si existe otra categoría con el mismo nombre (ignorando mayúsculas y minúsculas)
        qs = Categoria.objects.filter(nombre__iexact=value)
        
        # Si estamos ACTUALIZANDO, excluimos a esta misma categoría de la búsqueda
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
            
        if qs.exists():
            raise serializers.ValidationError("Ya existe una categoría con este nombre en el sistema.")
        return value


class VideojuegoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.ReadOnlyField(source='categoria.nombre')

    class Meta:
        model = Videojuego
        fields = '__all__'

    def validate_precio(self, value):
        if value <= 0:
            raise serializers.ValidationError("El precio debe ser mayor a 0.")
        return value

    # NUEVO: Validar Fechas Lógicas
    def validate_fecha_lanzamiento(self, value):
        anio_actual = timezone.now().year
        # Un juego no pudo salir antes de la creación de la industria (ej. 1970) ni más allá de 5 años en el futuro.
        if value.year < 1970 or value.year > (anio_actual + 5):
            raise serializers.ValidationError("La fecha de lanzamiento no es lógica. Ingrese un año válido.")
        return value
    
    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("El stock de un videojuego no puede ser un número negativo.")
        
        # Opcional: Una regla de negocio de control de calidad. 
        # Si el stock supera 1000, podría ser un error de dedo.
        if value > 1000:
            raise serializers.ValidationError("El stock ingresado es sospechosamente alto. Verifique el inventario físico.")
            
        return value


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'username', 'email', 'rol', 'is_active', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    # NUEVO: Validar correo con nuestra función estricta
    def validate_email(self, value):
        from .serializers import validar_email_estricto
        email_limpio = validar_email_estricto(value)
        
        # Verificar que el correo no esté siendo usado por OTRO usuario
        qs = Usuario.objects.filter(email__iexact=email_limpio)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
            
        if qs.exists():
            raise serializers.ValidationError("Este correo electrónico ya está registrado por otro usuario.")
            
        return email_limpio
    
    def validate_password(self, value):
        try:
            # Esto exige mínimo 8 caracteres y bloquea contraseñas tontas como "12345678"
            validate_password(value) 
        except serializers.ValidationError as exc:
            raise serializers.ValidationError(str(exc))
        return value
        
    def create(self, validated_data):
        # 1. Creamos el usuario con los datos que mandó Angular
        user = Usuario(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            rol=validated_data.get('rol', 'Vendedor')
        )
        
        # 2. Usamos la herramienta nativa de Django para ENCRIPTAR la contraseña
        user.set_password(validated_data['password']) 
        
        # 3. Guardamos en la base de datos
        user.save()
        return user
    def update(self, instance, validated_data):
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        instance.rol = validated_data.get('rol', instance.rol)
        
        # Si mandamos contraseña nueva, la encripta. Si no, la deja intacta.
        password = validated_data.get('password')
        if password:
            instance.set_password(password)
            
        instance.save()
        return instance


# ─── Reserva ─────────────────────────────────────────────────────────────────

class ReservaSerializer(serializers.ModelSerializer):
    videojuego_titulo = serializers.ReadOnlyField(source='videojuego.titulo')

    class Meta:
        model = Reserva
        fields = '__all__'

    # 1. Validar nombre (solo letras)
    def validate_cliente_nombre(self, value):
        return validar_solo_letras(value, "nombre del cliente")

    # 2. Validar teléfono (10 dígitos, empieza con 0)
    def validate_cliente_contacto(self, value):
        return validar_telefono_ecuador(value)

    # 3. Validar Cédula (Módulo 10)
    def validate_cliente_cedula(self, value):
        return validar_cedula_ecuatoriana(value)

    # 4. Validar que la cantidad tenga sentido lógico
    def validate_cantidad(self, value):
        if value <= 0:
            raise serializers.ValidationError("La cantidad a reservar debe ser de al menos 1.")
        if value > 5:
            raise serializers.ValidationError("Por políticas de la tienda, no se pueden reservar más de 5 unidades por cliente.")
        return value

    def validate_fecha_expiracion(self, value):
        if value < timezone.now():
            raise serializers.ValidationError("La fecha de expiración no puede estar en el pasado.")
        return value

    # 5. VALIDACIÓN GLOBAL (Acaparamiento y Stock)
    def validate(self, data):
        videojuego = data.get('videojuego')
        cantidad = data.get('cantidad')
        cedula = data.get('cliente_cedula')

        if videojuego and cantidad:
            # Regla de Stock
            if not videojuego.activo:
                raise serializers.ValidationError({"videojuego": "Este videojuego no está activo en el sistema."})
            if videojuego.stock < cantidad:
                raise serializers.ValidationError({"cantidad": f"Stock insuficiente. Solo quedan {videojuego.stock} unidades disponibles."})

        # Regla de NO repetición de Cédula (Acaparamiento)
        # Si el usuario ya tiene una reserva PENDIENTE para este MISMO juego, lo bloqueamos.
        if videojuego and cedula:
            reserva_existente = Reserva.objects.filter(
                cliente_cedula=cedula, 
                videojuego=videojuego, 
                estado="Pendiente"
            ).exists()
            
            # Nota: self.instance es None cuando estamos CREANDO, y tiene datos cuando estamos ACTUALIZANDO.
            if self.instance is None and reserva_existente:
                raise serializers.ValidationError({
                    "cliente_cedula": f"El cliente con cédula {cedula} ya tiene una reserva pendiente para el juego '{videojuego.titulo}'."
                })

        return data


# ─── Venta ───────────────────────────────────────────────────────────────────

# 1. Agregamos el título y precio al detalle
class DetalleVentaSerializer(serializers.ModelSerializer):
    videojuego_titulo = serializers.ReadOnlyField(source='videojuego.titulo')
    
    class Meta:
        model = DetalleVenta
        fields = ['videojuego', 'videojuego_titulo', 'cantidad', 'precio_unitario']

# 2. Agregamos el nombre del vendedor a la venta
class VentaSerializer(serializers.ModelSerializer):
    detalles = DetalleVentaSerializer(many=True)
    usuario_nombre = serializers.ReadOnlyField(source='usuario.username') # Para que no diga "Admin" siempre

    class Meta:
        model = Venta
        fields = ['id', 'fecha_venta', 'total', 'codigo_reserva', 'cliente_nombre', 'cliente_cedula', 'usuario', 'usuario_nombre', 'detalles']
        read_only_fields = ['total', 'fecha_venta']
    def validate_cliente_cedula(self, value):
        return validar_cedula_ecuatoriana(value)

    def validate_detalles(self, value):
        if not value or len(value) == 0:
            raise serializers.ValidationError("No se puede procesar una venta sin videojuegos. Añada al menos un producto.")
        return value
        
    def validate_cliente_nombre(self, value):
        from .serializers import validar_solo_letras
        return validar_solo_letras(value, "nombre del cliente")

    def validate_cliente_cedula(self, value):
        from .serializers import validar_cedula_ecuatoriana
        return validar_cedula_ecuatoriana(value)

    def validate_codigo_reserva(self, value):
        if value and not Reserva.objects.filter(codigo_reserva=value).exists():
            raise serializers.ValidationError("Este código de reserva no existe.")
        return value

    # AQUI ESTÁ LA TRADUCCIÓN DE TU LOGICA DE C#
    def create(self, validated_data):
        detalles_data = validated_data.pop('detalles')
        codigo = validated_data.get('codigo_reserva')
        viene_de_reserva = bool(codigo)

        # transaction.atomic() es tu red de seguridad. O se guarda todo, o no se guarda nada.
        with transaction.atomic():
            # 1. Creamos la venta vacía primero (con total 0)
            validated_data['total'] = 0 
            
            # Si viene de reserva, aseguramos los datos del cliente real
            if viene_de_reserva:
                reserva = Reserva.objects.get(codigo_reserva=codigo)
                validated_data['cliente_nombre'] = reserva.cliente_nombre
                validated_data['cliente_cedula'] = reserva.cliente_cedula

            venta = Venta.objects.create(**validated_data)
            total_calculado = 0

            # 2. Procesamos cada detalle (cada juego que está comprando)
            for detalle in detalles_data:
                videojuego = detalle['videojuego']
                cantidad = detalle['cantidad']

                # 3. Validar y descontar stock (solo si NO viene de reserva, porque la reserva ya lo descontó)
                if not viene_de_reserva:
                    if videojuego.stock < cantidad:
                        raise serializers.ValidationError({"detalles": f"Stock insuficiente para {videojuego.titulo}."})
                    videojuego.stock -= cantidad
                    videojuego.save()

                # 4. Crear el detalle y sumar al total
                precio_unitario = videojuego.precio
                DetalleVenta.objects.create(
                    venta=venta,
                    videojuego=videojuego,
                    cantidad=cantidad,
                    precio_unitario=precio_unitario
                )
                total_calculado += (cantidad * precio_unitario)

            # 5. Actualizamos el total de la venta
            venta.total = total_calculado
            venta.save()

            # 6. Si venía de una reserva, la marcamos como Completada
            if viene_de_reserva:
                reserva.estado = "Completada"
                reserva.save()

            return venta
        
class TokenPersonalizadoSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Aquí "inyectamos" tus datos en el payload del token
        token['nombre'] = user.username
        token['email'] = user.email
        token['rol'] = user.rol
        
        return token
from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
from .models import Categoria, Videojuego, Usuario, Reserva, Venta, DetalleVenta
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.db import transaction

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


# ─── Serializers simples ─────────────────────────────────────────────────────

class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = '__all__'


class VideojuegoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.ReadOnlyField(source='categoria.nombre')

    class Meta:
        model = Videojuego
        fields = '__all__'
        # Nueva validación de calidad para el precio
    def validate_precio(self, value):
        if value <= 0:
            raise serializers.ValidationError("El precio debe ser mayor a 0.")
        return value


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'username', 'email', 'rol', 'is_active', 'password']
        extra_kwargs = {'password': {'write_only': True}}

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
    # 1. Agregamos este campo de "solo lectura" que busca el título en el modelo Videojuego
    videojuego_titulo = serializers.ReadOnlyField(source='videojuego.titulo')

    class Meta:
        model = Reserva
        fields = '__all__' # Esto ahora incluirá 'videojuego_titulo'

    def validate_cliente_cedula(self, value):
        return validar_cedula_ecuatoriana(value)

    def validate_cantidad(self, value):
        if value <= 0:
            raise serializers.ValidationError("La cantidad a reservar debe ser de al menos 1.")
        return value

    def validate_fecha_expiracion(self, value):
        if value < timezone.now():
            raise serializers.ValidationError("La fecha de expiración no puede estar en el pasado.")
        return value

    def validate(self, data):
        videojuego = data.get('videojuego')
        cantidad = data.get('cantidad')

        if videojuego and cantidad:
            if not videojuego.activo:
                raise serializers.ValidationError({
                    "videojuego": "Este videojuego no está activo en el sistema."
                })
            if videojuego.stock < cantidad:
                raise serializers.ValidationError({
                    "cantidad": f"Stock insuficiente. Solo quedan {videojuego.stock} unidades disponibles."
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
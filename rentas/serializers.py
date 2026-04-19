from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.password_validation import validate_password
import re
from .models import Categoria, Videojuego, Usuario, Reserva, Venta, DetalleVenta
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

# ─── Funciones reutilizables de Validación (Regex y Módulo 10) ───────────────────

def validar_cedula_ecuatoriana(value):
    if not value.isdigit() or len(value) != 10:
        raise serializers.ValidationError("La cédula debe contener exactamente 10 dígitos numéricos.")
    provincia = int(value[0:2])
    if provincia < 1 or provincia > 24:
        raise serializers.ValidationError("El código de provincia de la cédula es inválido.")
    tercer_digito = int(value[2])
    if tercer_digito >= 6:
        raise serializers.ValidationError("El tercer dígito es inválido para personas naturales.")
    coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    total = 0
    for i in range(9):
        valor = int(value[i]) * coeficientes[i]
        if valor >= 10:
            valor -= 9
        total += valor
    digito_verificador_calculado = 10 - (total % 10)
    if digito_verificador_calculado == 10:
        digito_verificador_calculado = 0
    if digito_verificador_calculado != int(value[9]):
        raise serializers.ValidationError("La cédula ingresada no pasó la validación del algoritmo.")
    return value

def validar_solo_letras(value, campo="campo"):
    """Bloquea números y caracteres especiales. Solo permite letras y espacios."""
    value_str = str(value).strip()
    if not re.match(r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$', value_str):
        raise serializers.ValidationError(f"El {campo} solo debe contener letras. No se aceptan números ni símbolos.")
    if len(value_str) < 3:
        raise serializers.ValidationError(f"El {campo} debe tener al menos 3 caracteres.")
    return value_str

def validar_telefono_ecuador(value):
    """Valida que tenga 10 dígitos y empiece por 0."""
    value_str = str(value).strip()
    if not re.match(r'^0\d{9}$', value_str):
        raise serializers.ValidationError("El teléfono debe tener 10 dígitos numéricos y comenzar con '0'.")
    return value_str

# ─── 1. Categoria (Evitar duplicados al crear o actualizar) ──────────────────────

class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = '__all__'

    def validate_nombre(self, value):
        nombre_limpio = validar_solo_letras(value, "nombre de la categoría")
        qs = Categoria.objects.filter(nombre__iexact=nombre_limpio)
        if self.instance: # Si estamos actualizando, ignoramos esta misma categoría
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe una categoría con este nombre.")
        return nombre_limpio

# ─── 2. Videojuego (Validar stock negativo y fechas locas) ───────────────────────

class VideojuegoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.ReadOnlyField(source='categoria.nombre')

    class Meta:
        model = Videojuego
        fields = '__all__'

    def validate_precio(self, value):
        if value <= 0:
            raise serializers.ValidationError("El precio debe ser mayor a 0.")
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("El stock no puede ser negativo.")
        return value
    
    def validate_titulo(self, value):
        # Buscamos si existe otro juego con el mismo nombre exacto
        qs = Videojuego.objects.filter(titulo__iexact=value)
        if self.instance: # Si estamos actualizando, ignoramos este mismo juego
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un videojuego registrado con este título en el catálogo.")
        return value

    def validate_fecha_lanzamiento(self, value):
        anio_actual = timezone.now().year
        if value.year < 1970 or value.year > (anio_actual + 5):
            raise serializers.ValidationError("La fecha de lanzamiento ingresada es inválida.")
        return value
    
    def validate_titulo(self, value):
        # Buscamos si existe otro juego con el mismo nombre exacto
        qs = Videojuego.objects.filter(titulo__iexact=value)
        if self.instance: # Si estamos actualizando, ignoramos este mismo juego
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un videojuego registrado con este título en el catálogo.")
        return value

# ─── 3. Usuario (Validar correo único y contraseña segura) ───────────────────────

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        # NOTA: Agregué first_name y last_name para que puedas guardar los nombres reales
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'rol', 'is_active', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def validate_rol(self, value):
        roles_permitidos = ["Administrador", "Vendedor"]
        # Capitalizamos la primera letra por si lo mandan en minúsculas (ej. "vendedor" -> "Vendedor")
        rol_formateado = value.capitalize() 
        if rol_formateado not in roles_permitidos:
            raise serializers.ValidationError(f"Rol inválido. Los roles permitidos son: {', '.join(roles_permitidos)}.")
        return rol_formateado

    def validate_first_name(self, value):
        if value: return validar_solo_letras(value, "nombre")
        return value

    def validate_last_name(self, value):
        if value: return validar_solo_letras(value, "apellido")
        return value

    def validate_email(self, value):
        # Verificar que el correo tenga formato válido
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', value):
            raise serializers.ValidationError("El formato del correo no es válido.")
        
        # Verificar que el correo no esté usado por OTRO usuario (para cuando actualices)
        qs = Usuario.objects.filter(email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Este correo ya está registrado por otro usuario.")
        return value

    def validate_password(self, value):
        try:
            validate_password(value) # Exige 8 caracteres mínimo y bloquea claves fáciles
        except serializers.ValidationError as exc:
            raise serializers.ValidationError(str(exc))
        return value

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = Usuario(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

# ─── 4. Reserva (Blindar cliente_nombre, contacto y evitar acaparamiento) ────────

class ReservaSerializer(serializers.ModelSerializer):
    videojuego_titulo = serializers.ReadOnlyField(source='videojuego.titulo')

    class Meta:
        model = Reserva
        fields = '__all__'

    def validate_cliente_nombre(self, value):
        return validar_solo_letras(value, "nombre del cliente")

    def validate_cliente_contacto(self, value):
        return validar_telefono_ecuador(value)

    def validate_cliente_cedula(self, value):
        return validar_cedula_ecuatoriana(value)

    def validate_cantidad(self, value):
        if value <= 0:
            raise serializers.ValidationError("Debe reservar al menos 1 unidad.")
        if value > 5:
            raise serializers.ValidationError("No se pueden reservar más de 5 unidades del mismo juego.")
        return value

    def validate_fecha_expiracion(self, value):
        if value < timezone.now():
            raise serializers.ValidationError("La fecha de expiración no puede estar en el pasado.")
        return value

    def validate(self, data):
        videojuego = data.get('videojuego', getattr(self.instance, 'videojuego', None))
        cantidad = data.get('cantidad', getattr(self.instance, 'cantidad', None))
        cedula = data.get('cliente_cedula', getattr(self.instance, 'cliente_cedula', None))

        if videojuego and cantidad:
            if not videojuego.activo:
                raise serializers.ValidationError({"videojuego": "El videojuego no está activo."})
            
            # Validamos stock solo si están pidiendo MÁS de lo que ya tenían reservado
            cantidad_anterior = getattr(self.instance, 'cantidad', 0) if self.instance else 0
            if cantidad > cantidad_anterior:
                diferencia = cantidad - cantidad_anterior
                if videojuego.stock < diferencia:
                    raise serializers.ValidationError({"cantidad": f"Stock insuficiente para aumentar la reserva. Solo quedan {videojuego.stock} unidades extra."})

        if videojuego and cedula:
            qs = Reserva.objects.filter(cliente_cedula=cedula, videojuego=videojuego, estado="Pendiente")
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"cliente_cedula": "Este cliente ya tiene una reserva pendiente para este juego."})

        return data

# ─── 5. Venta y Detalle (Validar que no haya venta sin productos) ────────────────

class DetalleVentaSerializer(serializers.ModelSerializer):
    videojuego_titulo = serializers.ReadOnlyField(source='videojuego.titulo')
    
    class Meta:
        model = DetalleVenta
        fields = ['videojuego', 'videojuego_titulo', 'cantidad', 'precio_unitario']

    # NUEVO: ¡Nadie puede comprar 0 o cantidades negativas!
    def validate_cantidad(self, value):
        if value <= 0:
            raise serializers.ValidationError("La cantidad de cada producto en la venta debe ser de al menos 1.")
        return value

class VentaSerializer(serializers.ModelSerializer):
    detalles = DetalleVentaSerializer(many=True)
    usuario_nombre = serializers.ReadOnlyField(source='usuario.username')

    class Meta:
        model = Venta
        fields = ['id', 'fecha_venta', 'total', 'codigo_reserva', 'cliente_nombre', 'cliente_cedula', 'usuario', 'usuario_nombre', 'detalles']
        read_only_fields = ['total', 'fecha_venta']

    def validate_cliente_nombre(self, value):
        return validar_solo_letras(value, "nombre del cliente")

    def validate_cliente_cedula(self, value):
        return validar_cedula_ecuatoriana(value)

    def validate_codigo_reserva(self, value):
        if value and not Reserva.objects.filter(codigo_reserva=value).exists():
            raise serializers.ValidationError("Este código de reserva no existe.")
        return value
    
    def update(self, instance, validated_data):
        # Bloqueo total: Una vez que se emite una factura/venta, es inmutable.
        raise serializers.ValidationError("Por normativas de seguridad e integridad financiera, las facturas emitidas no pueden ser modificadas ni actualizadas. Si hay un error, el administrador debe realizar una anulación manual o ajuste en base de datos.")

    def validate_detalles(self, value):
        if not value or len(value) == 0:
            raise serializers.ValidationError("No se puede crear una factura sin productos.")
        return value

    def create(self, validated_data):
        detalles_data = validated_data.pop('detalles')
        codigo = validated_data.get('codigo_reserva')
        viene_de_reserva = bool(codigo)

        with transaction.atomic():
            validated_data['total'] = 0 
            if viene_de_reserva:
                reserva = Reserva.objects.get(codigo_reserva=codigo)
                validated_data['cliente_nombre'] = reserva.cliente_nombre
                validated_data['cliente_cedula'] = reserva.cliente_cedula

            venta = Venta.objects.create(**validated_data)
            total_calculado = 0

            for detalle in detalles_data:
                videojuego = detalle['videojuego']
                cantidad = detalle['cantidad']

                if not viene_de_reserva:
                    if videojuego.stock < cantidad:
                        raise serializers.ValidationError({"detalles": f"Stock insuficiente para {videojuego.titulo}."})
                    videojuego.stock -= cantidad
                    videojuego.save()

                precio_unitario = videojuego.precio
                DetalleVenta.objects.create(venta=venta, videojuego=videojuego, cantidad=cantidad, precio_unitario=precio_unitario)
                total_calculado += (cantidad * precio_unitario)

            venta.total = total_calculado
            venta.save()

            if viene_de_reserva:
                reserva.estado = "Completada"
                reserva.save()

            return venta
        
class TokenPersonalizadoSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['nombre'] = user.username
        token['email'] = user.email
        token['rol'] = user.rol
        return token
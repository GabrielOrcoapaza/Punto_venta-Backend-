import graphene
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from graphene_django.types import ErrorType

from apps.hrmn.models import ClientSupplier, Subsidiary
from apps.products.models import Product
from apps.sales.models import Purchase, Sales, DetailSales
from .types import (
    RegisterUserInput, LoginUserInput,
    RegisterUserPayload, LoginUserPayload, LogoutUserPayload,
    AuthErrorType, CreateProductInput, ProductType, CreatePurchaseInput, PurchaseType, CreateClientSupplierInput,
    ClientSupplierType, UpdateClientSupplierInput, UpdateProductInput, CreateSaleInput, SaleType
)


class EmployeeMutation(graphene.ObjectType):
    # Mantén tus mutaciones existentes de Employee aquí
    pass


class RegisterUser(graphene.Mutation):
    class Arguments:
        input = RegisterUserInput(required=True)

    Output = RegisterUserPayload

    def mutate(self, info, input):
        errors = []

        # Validar que las contraseñas coincidan
        if input.password1 != input.password2:
            errors.append(AuthErrorType(field="password2", message="Las contraseñas no coinciden"))
            return RegisterUserPayload(success=False, errors=errors, user=None, token=None)

        # Validar que el usuario no exista
        if User.objects.filter(username=input.username).exists():
            errors.append(AuthErrorType(field="username", message="Este nombre de usuario ya existe"))
            return RegisterUserPayload(success=False, errors=errors, user=None, token=None)

        # Validar que el email no exista
        if User.objects.filter(email=input.email).exists():
            errors.append(AuthErrorType(field="email", message="Este email ya está registrado"))
            return RegisterUserPayload(success=False, errors=errors, user=None, token=None)

        # Validar longitud de contraseña
        if len(input.password1) < 8:
            errors.append(AuthErrorType(field="password1", message="La contraseña debe tener al menos 8 caracteres"))
            return RegisterUserPayload(success=False, errors=errors, user=None, token=None)

        if errors:
            return RegisterUserPayload(success=False, errors=errors, user=None, token=None)

        try:
            with transaction.atomic():
                # Crear el usuario
                user = User.objects.create_user(
                    username=input.username,
                    email=input.email,
                    password=input.password1
                )

                # Generar token (simplificado - en producción usar JWT)
                token = default_token_generator.make_token(user)

                # Hacer login automático
                login(info.context, user)

                return RegisterUserPayload(
                    success=True,
                    user=user,
                    token=token,
                    errors=[]
                )
        except Exception as e:
            errors.append(AuthErrorType(field="general", message="Error al crear el usuario"))
            return RegisterUserPayload(success=False, errors=errors, user=None, token=None)


class LoginUser(graphene.Mutation):
    class Arguments:
        input = LoginUserInput(required=True)

    Output = LoginUserPayload

    def mutate(self, info, input):
        errors = []

        # Autenticar usuario
        user = authenticate(
            username=input.username,
            password=input.password
        )

        if user is None:
            errors.append(AuthErrorType(field="username", message="Credenciales inválidas"))
            return LoginUserPayload(success=False, errors=errors, user=None, token=None)

        if not user.is_active:
            errors.append(AuthErrorType(field="username", message="Cuenta desactivada"))
            return LoginUserPayload(success=False, errors=errors, user=None, token=None)

        # Hacer login
        login(info.context, user)

        # Generar token
        token = default_token_generator.make_token(user)

        return LoginUserPayload(
            success=True,
            user=user,
            token=token,
            errors=[]
        )


class LogoutUser(graphene.Mutation):
    Output = LogoutUserPayload

    def mutate(self, info):
        user = info.context.user

        if user.is_authenticated:
            logout(info.context)
            return LogoutUserPayload(
                success=True,
                message="Sesión cerrada exitosamente"
            )
        else:
            return LogoutUserPayload(
                success=False,
                message="No hay sesión activa"
            )


class CreateProduct(graphene.Mutation):
    class Arguments:
        input = CreateProductInput(required=True)

    product = graphene.Field(ProductType)
    success = graphene.Boolean()
    errors = graphene.List(AuthErrorType)

    def mutate(self, info, input):
        try:
            product = Product.objects.create(
                name=input.name,
                code=input.code,
                price=input.price,
                laboratory=input.laboratory,
                alias=input.alias,
                quantity=input.quantity
            )
            return CreateProduct(product=product, success=True, errors=None)
        except Exception as e:
            return CreateProduct(product=None, success=False, errors=[AuthErrorType(message=str(e))])


class UpdateProduct(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        input = UpdateProductInput(required=True)

    product = graphene.Field(ProductType)
    success = graphene.Boolean()
    errors = graphene.List(AuthErrorType)

    def mutate(self, info, id, input):
        try:
            product = Product.objects.get(pk=id)

            # Actualizar los campos
            product.name = input.name
            product.code = input.code
            product.price = input.price
            product.laboratory = input.laboratory
            product.alias = input.alias
            product.quantity = input.quantity

            product.save()

            return UpdateProduct(product=product, success=True, errors=None)
        except Product.DoesNotExist:
            return UpdateProduct(
                product=None,
                success=False,
                errors=[AuthErrorType(message="Producto no encontrado")]
            )
        except Exception as e:
            return UpdateProduct(
                product=None,
                success=False,
                errors=[AuthErrorType(message=str(e))]
            )


class CreateSale(graphene.Mutation):
    """Mutación para crear una venta con múltiples productos"""

    class Arguments:
        input = CreateSaleInput(required=True)

    sale = graphene.Field(SaleType)
    success = graphene.Boolean()
    errors = graphene.List(AuthErrorType)

    def mutate(self, info, input):
        try:
            from django.utils import timezone
            from decimal import Decimal

            # Validar que haya al menos un producto
            if not input.details or len(input.details) == 0:
                return CreateSale(
                    sale=None,
                    success=False,
                    errors=[AuthErrorType(message="Debe incluir al menos un producto")]
                )

            # Obtener el empleado actual (si tienes autenticación)
            employee = None
            if info.context.user.is_authenticated:
                try:
                    # Ajusta esto según tu modelo de usuario/empleado
                    employee = info.context.user.employee
                except:
                    pass

            # Obtener cliente si se proporciona
            provider = None
            if input.providerId:
                try:
                    provider = ClientSupplier.objects.get(id=input.providerId)
                except ClientSupplier.DoesNotExist:
                    return CreateSale(
                        sale=None,
                        success=False,
                        errors=[AuthErrorType(message=f"Cliente '{input.providerId}' no encontrado")]
                    )

            # Obtener sucursal si se proporciona
            subsidiary = None
            if input.subsidiaryId:
                try:
                    # from hrmn.models import Subsidiary
                    subsidiary = Subsidiary.objects.get(id=input.subsidiaryId)
                except Subsidiary.DoesNotExist:
                    return CreateSale(
                        sale=None,
                        success=False,
                        errors=[AuthErrorType(message=f"Sucursal '{input.subsidiaryId}' no encontrada")]
                    )

            # Calcular el total de la venta sumando todos los detalles
            total_sale = Decimal('0.00')
            detail_objects = []

            # Validar y preparar los detalles
            for detail_input in input.details:
                try:
                    product = Product.objects.get(id=detail_input.productId)
                except Product.DoesNotExist:
                    return CreateSale(
                        sale=None,
                        success=False,
                        errors=[AuthErrorType(message=f"Producto '{detail_input.productId}' no encontrado")]
                    )

                # Validar stock disponible (si aplica)
                if product.quantity < detail_input.quantity:
                    return CreateSale(
                        sale=None,
                        success=False,
                        errors=[AuthErrorType(
                            message=f"Stock insuficiente para el producto '{product.name}'. Disponible: {product.quantity}, Solicitado: {detail_input.quantity}"
                        )]
                    )

                total_sale += Decimal(str(detail_input.total))

                # Preparar objeto DetailSales (aún no guardado)
                detail_obj = DetailSales(
                    product=product,
                    quantity=detail_input.quantity,
                    price=detail_input.price,
                    subtotal=detail_input.subtotal,
                    total=detail_input.total,
                    observation=getattr(detail_input, 'observation', None)
                )
                detail_objects.append(detail_obj)

            # Crear la venta (Sales) - UNA SOLA VENTA
            sale = Sales.objects.create(
                date_creation=input.date if input.date else timezone.now(),
                employee_creation=employee,
                type_receipt=input.typeReceipt,
                type_pay=input.typePay,
                total=total_sale,  # Total de todos los productos
                provider=provider,
                subsidiary=subsidiary
            )

            # Crear los detalles de venta (DetailSales) - MÚLTIPLES DETALLES
            # Todos asociados a la misma venta
            for detail_obj in detail_objects:
                detail_obj.sale = sale  # Asociar a la misma venta
                detail_obj.save()

                # Actualizar stock del producto
                detail_obj.product.quantity -= detail_obj.quantity
                detail_obj.product.save()

            return CreateSale(sale=sale, success=True, errors=None)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return CreateSale(
                sale=None,
                success=False,
                errors=[AuthErrorType(message=str(e))]
            )


class CreatePurchase(graphene.Mutation):
    class Arguments:
        input = CreatePurchaseInput(required=True)

    purchase = graphene.Field(PurchaseType)
    success = graphene.Boolean()
    errors = graphene.List(AuthErrorType)

    def mutate(self, info, input):
        try:
            try:
                product = Product.objects.get(id=input.productId)
            except Product.DoesNotExist:
                return CreatePurchase(
                    purchase=None,
                    success=False,
                    errors=[AuthErrorType(message=f"Producto '{input.productId}' no encontrado")]
                )
            purchase = Purchase.objects.create(
                product=product,
                price=input.price,
                quantity=input.quantity,
                subtotal=input.subtotal,
                total=input.total,
                typeReceipt=input.typeReceipt,
                typePay=input.typePay,
                date=input.date,
            )
            return CreatePurchase(purchase=purchase, success=True, errors=None)
        except Exception as e:
            return CreatePurchase(purchase=None, success=False, errors=[AuthErrorType(message=str(e))])


class CreateClientSupplier(graphene.Mutation):
    class Arguments:
        input = CreateClientSupplierInput(required=True)

    clientSupplier = graphene.Field(ClientSupplierType)
    success = graphene.Boolean()
    errors = graphene.List(AuthErrorType)

    def mutate(self, info, input):
        try:
            clientSupplier = ClientSupplier.objects.create(
                name=input.name,
                address=input.address,
                phone=input.phone,
                mail=input.mail,
                nDocument=input.nDocument,
                typeDocument=input.typeDocument,
                typePerson=input.typePerson
            )
            return CreateClientSupplier(clientSupplier=clientSupplier, success=True, errors=None)
        except Exception as e:
            return CreateClientSupplier(clientSupplier=None, success=False, errors=[AuthErrorType(message=str(e))])


class UpdateClientSupplier(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        input = UpdateClientSupplierInput(required=True)

    clientSupplier = graphene.Field(ClientSupplierType)
    success = graphene.Boolean()
    errors = graphene.List(AuthErrorType)

    def mutate(self, info, id, input):
        try:
            clientSupplier = ClientSupplier.objects.get(pk=id)

            # Actualizar los camposn
            clientSupplier.name = input.name
            clientSupplier.address = input.address
            clientSupplier.phone = input.phone
            clientSupplier.mail = input.mail
            clientSupplier.nDocument = input.nDocument
            clientSupplier.typeDocument = input.typeDocument
            clientSupplier.typePerson = input.typePerson

            clientSupplier.save()

            return UpdateClientSupplier(clientSupplier=clientSupplier, success=True, errors=None)
        except ClientSupplier.DoesNotExist:
            return UpdateClientSupplier(
                clientSupplier=None,
                success=False,
                errors=[AuthErrorType(message="Cliente/Proveedor no encontrado")]
            )
        except Exception as e:
            return UpdateClientSupplier(
                clientSupplier=None,
                success=False,
                errors=[AuthErrorType(message=str(e))]
            )


class AuthMutation(graphene.ObjectType):
    register_user = RegisterUser.Field()
    login_user = LoginUser.Field()
    logout_user = LogoutUser.Field()
    create_product = CreateProduct.Field()
    update_product = UpdateProduct.Field()
    create_purchase = CreatePurchase.Field()
    create_sale = CreateSale.Field()
    create_client_supplier = CreateClientSupplier.Field()
    update_client_supplier = UpdateClientSupplier.Field()


class Mutation(EmployeeMutation, AuthMutation, graphene.ObjectType):
    pass
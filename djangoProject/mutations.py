from django.utils import timezone
from decimal import Decimal

import graphene
import graphql_jwt

from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction, IntegrityError
from django.contrib.auth.tokens import default_token_generator
from django.db.models import Sum
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from graphene_django.types import ErrorType

from apps.hrmn.models import ClientSupplier, Subsidiary, Employee
from apps.products.models import Product
from apps.sales.models import Purchase, Sales, DetailSales, Cash, Payment
from .types import (
    RegisterUserInput, LoginUserInput,
    RegisterUserPayload, LoginUserPayload, LogoutUserPayload,
    AuthErrorType, CreateProductInput, ProductType, CreatePurchaseInput, PurchaseType, CreateClientSupplierInput,
    ClientSupplierType, UpdateClientSupplierInput, UpdateProductInput, CreateSaleInput, SaleType, OpenCashInput,
    CashType, CloseCashInput, CashSummaryType, MethodTotal, CreateExpensePaymentInput, PaymentType, UpdatePurchaseInput
)
from django.contrib.auth import get_user_model
from .types import UserType

User = get_user_model()


class ObtainJSONWebToken(graphql_jwt.ObtainJSONWebToken):
    user = graphene.Field(UserType)

    @classmethod
    def resolve(cls, root, info, **kwargs):
        return cls(user=info.context.user)


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
            return RegisterUserPayload(success=False, errors=errors, user=None)

        # Validar que el usuario no exista
        if User.objects.filter(username=input.username).exists():
            errors.append(AuthErrorType(field="username", message="Este nombre de usuario ya existe"))
            return RegisterUserPayload(success=False, errors=errors, user=None)

        # Validar que el email no exista
        if User.objects.filter(email=input.email).exists():
            errors.append(AuthErrorType(field="email", message="Este email ya está registrado"))
            return RegisterUserPayload(success=False, errors=errors, user=None)

        # Validar longitud de contraseña
        if len(input.password1) < 8:
            errors.append(AuthErrorType(field="password1", message="La contraseña debe tener al menos 8 caracteres"))
            return RegisterUserPayload(success=False, errors=errors, user=None)

        if errors:
            return RegisterUserPayload(success=False, errors=errors, user=None)

        try:
            with transaction.atomic():
                # Crear el usuario
                user = User.objects.create_user(
                    username=input.username,
                    email=input.email,
                    password=input.password1,
                    first_name=input.first_name or '',
                    last_name=input.last_name or ''
                )

                return RegisterUserPayload(
                    success=True,
                    user=user,
                    errors=[]
                )
        except Exception as e:
            print(f"Error en registro: {e}")
            errors.append(AuthErrorType(field="general", message="Error al crear el usuario"))
            return RegisterUserPayload(success=False, errors=errors, user=None)


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
            return LoginUserPayload(success=False, errors=errors, user=None)

        if not user.is_active:
            errors.append(AuthErrorType(field="username", message="Cuenta desactivada"))
            return LoginUserPayload(success=False, errors=errors, user=None)

        # Hacer login (esto crea la sesión de Django)
        login(info.context, user)

        print(f"Usuario {user.username} autenticado. Session key: {info.context.session.session_key}")

        return LoginUserPayload(
            success=True,
            user=user,
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


class UpdatePurchase(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        input = UpdatePurchaseInput(required=True)

    purchase = graphene.Field(PurchaseType)
    success = graphene.Boolean()
    errors = graphene.List(AuthErrorType)

    def mutate(self, info, id, input):
        try:
            try:
                purchase = Purchase.objects.get(pk=id)
            except Purchase.DoesNotExist:
                return UpdatePurchase(
                    purchase=None,
                    success=False,
                    errors=[AuthErrorType(message=f"Compra '{id}' no encontrada")]
                )

            if 'productId' in input and input.productId is not None:
                try:
                    product = Product.objects.get(id=input.productId)
                    purchase.product = product
                except Product.DoesNotExist:
                    return UpdatePurchase(
                        purchase=None,
                        success=False,
                        errors=[AuthErrorType(message=f"Producto'{product}' no encontrado")]
                    )

            if 'providerId' in input and input.providerId is not None:
                try:
                    provider = ClientSupplier.objects.get(id=input.providerId)
                    purchase.provider = provider
                except ClientSupplier.DoesNotExist:
                    return UpdatePurchase(
                        purchase=None,
                        success=False,
                        errors=[AuthErrorType(message=f"Proveedor '{provider}' no encontrado")]
                    )

            for field in ['quantity', 'price', 'subtotal', 'total', 'typeReceipt', 'typePay', 'date']:
                if field in input and getattr(input, field) is not None:
                    setattr(purchase, field, getattr(input, field))

            purchase.save()
            return UpdatePurchase(purchase=purchase, success=True, errors=None)

        except Exception as e:
            return UpdatePurchase(purchase=None, success=False, errors=[AuthErrorType(message=str(e))])


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


class OpenCash(graphene.Mutation):
    class Arguments:
        input = OpenCashInput(required=True)

    cash = graphene.Field(CashType)
    success = graphene.Boolean()
    errors = graphene.List(ErrorType)

    @staticmethod
    def mutate(root, info, input):
        user = info.context.user

        # DEBUG
        print(f"OpenCash - Usuario: {user}")
        print(f"OpenCash - Autenticado: {user.is_authenticated}")

        if not user.is_authenticated:
            print("Usuario NO autenticado en OpenCash")
            return OpenCash(
                cash=None,
                success=False,
                errors=[ErrorType(messages=['Debe iniciar sesión para abrir una caja'])]
            )

        print(f"Usuario autenticado, continuando...")

        try:
            subsidiary = Subsidiary.objects.get(id=input.subsidiary_id)
            print(f"Subsidiary encontrada: {subsidiary}")
        except Subsidiary.DoesNotExist:
            print(f"Subsidiary {input.subsidiary_id} no encontrada")
            return OpenCash(
                cash=None,
                success=False,
                errors=[ErrorType(messages=['Sucursal no encontrada'])]
            )
        except Exception as e:
            print(f"Error buscando subsidiary: {str(e)}")
            return OpenCash(
                cash=None,
                success=False,
                errors=[ErrorType(messages=[f'Error: {str(e)}'])]
            )

        exists_open = Cash.objects.filter(subsidiary=subsidiary, status='A').exists()
        print(f"¿Existe caja abierta?: {exists_open}")

        if exists_open:
            print("Ya existe una caja abierta")
            return OpenCash(
                cash=None,
                success=False,
                errors=[ErrorType(messages=['Ya existe una caja abierta en esta sucursal'])]
            )

        try:
            print(f"Creando caja...")

            # USAR CAMELCASE como está definido en el modelo
            cash = Cash.objects.create(
                subsidiary=subsidiary,
                name=getattr(input, 'name', None) or 'Caja',
                user=user,
                status='A',
                initialAmount=Decimal(str(input.initial_amount)),  # ⬅️ camelCase
                dateOpen=timezone.now(),  # ⬅️ camelCase
            )

            print(f"Caja {cash.id} creada exitosamente")
            print(f"Detalles: id={cash.id}, status={cash.status}, amount={cash.initialAmount}")
            return OpenCash(cash=cash, success=True, errors=[])

        except Exception as e:
            print(f"Error creando caja: {str(e)}")
            import traceback
            traceback.print_exc()
            return OpenCash(
                cash=None,
                success=False,
                errors=[ErrorType(messages=[f'Error al crear caja: {str(e)}'])]
            )


class CloseCash(graphene.Mutation):
    class Arguments:
        input = CloseCashInput(required=True)
    cash = graphene.Field(CashType)
    summary = graphene.Field(CashSummaryType)
    success = graphene.Boolean()
    errors = graphene.List(ErrorType)

    @staticmethod
    def mutate(root, info, input):
        try:
            cash = Cash.objects.get(id=input.cash_id)
        except Cash.DoesNotExist:
            return CloseCash(cash=None, summary=None, success=False, errors=[ErrorType(messages=['Caja no encontrada'])])

        if cash.status != 'A':
            return CloseCash(cash=None, summary=None, success=False, errors=[ErrorType(messages=['La caja no está abierta'])])

        user = info.context.user

        payments_qs = Payment.objects.filter(cash=cash, status='PAID')
        by_method_qs = payments_qs.values('payment_method').annotate(total=Sum('paid_amount'))
        by_method = [
            MethodTotal(method=row['payment_method'], total=row['total'] or Decimal('0.00'))
        for row in by_method_qs
        ]
        total_expected = payments_qs.aggregate(t=Sum('paid_amount'))['t'] or Decimal('0.00')
        total_counted = Decimal(str(input.closing_amount))
        difference = total_counted - total_expected

        cash.closing_amount = total_counted
        cash.difference = difference
        cash.status = 'C'
        cash.date_close = timezone.now()
        cash.user = user
        cash.save()

        summary = CashSummaryType(
            by_method=by_method,
            total_expected=total_expected,
            total_counted=total_counted,
            difference=difference,
        )
        return CloseCash(cash=cash, summary=summary, success=True, errors=[])


class CreateExpensePayment(graphene.Mutation):
    class Arguments:
        input = CreateExpensePaymentInput(required=True)
    payment = graphene.Field(graphene.NonNull(graphene.JSONString))
    success = graphene.Boolean()
    errors = graphene.List(ErrorType)

    @staticmethod
    def mutate(root, info, input):
        user = info.context.user
        try:
            subsidiary = Subsidiary.objects.get(id=input.subsidiary_id)
            cash = Cash.objects.get(id=input.cash_id)
        except Subsidiary.DoesNotExist:
            return CreateExpensePayment(payment=None, success=False, errors=[ErrorType(messages=['Sucursal no encontrada'])])
        except Cash.DoesNotExist:
            return CreateExpensePayment(payment=None, success=False, errors=[ErrorType(messages=['Caja no encontrada'])])

        payment = Payment.objects.create(
            subsidiary=subsidiary,
            cash=cash,
            payment_type='EXPENSE',
            payment_method=input.payment_method,
            status='PAID',
            payment_date=input.payment_date or timezone.now(),
            total_amount=Decimal(str(input.total_amount)),
            paid_amount=Decimal(str(input.paid_amount)),
            notes=input.notes or '',
            user=user,
        )
        return CreateExpensePayment(payment={'id': str(payment.id)}, success=True, errors=[])


class AuthMutation(graphene.ObjectType):
    register_user = RegisterUser.Field()
    login_user = LoginUser.Field()
    logout_user = LogoutUser.Field()
    create_product = CreateProduct.Field()
    update_product = UpdateProduct.Field()
    create_purchase = CreatePurchase.Field()
    updatePurchase = UpdatePurchase.Field()
    create_sale = CreateSale.Field()
    create_client_supplier = CreateClientSupplier.Field()
    update_client_supplier = UpdateClientSupplier.Field()
    open_cash = OpenCash.Field()
    close_cash = CloseCash.Field()
    create_expense_payment = CreateExpensePayment.Field()
    token_auth = ObtainJSONWebToken.Field()
    verify_token = graphql_jwt.Verify.Field()
    refresh_token = graphql_jwt.Refresh.Field()


class Mutation(EmployeeMutation, AuthMutation, graphene.ObjectType):
    pass
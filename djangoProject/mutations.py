import graphene
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from graphene_django.types import ErrorType

from apps.products.models import Product
from .types import (
    RegisterUserInput, LoginUserInput,
    RegisterUserPayload, LoginUserPayload, LogoutUserPayload,
    AuthErrorType, CreateProductInput, ProductType
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
                sale_price=input.sale_price,
                laboratory=input.laboratory,
                alias=input.alias,
                quantity=input.quantity
            )
            return CreateProduct(product=product, success=True, errors=None)
        except Exception as e:
            return CreateProduct(product=None, success=False, errors=[AuthErrorType(message=str(e))])


class AuthMutation(graphene.ObjectType):
    register_user = RegisterUser.Field()
    login_user = LoginUser.Field()
    logout_user = LogoutUser.Field()
    create_product = CreateProduct.Field()


class Mutation(EmployeeMutation, AuthMutation, graphene.ObjectType):
    pass
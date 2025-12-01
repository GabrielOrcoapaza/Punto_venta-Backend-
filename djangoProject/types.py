import graphene
from graphene_django import DjangoObjectType
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction

from apps.products.models import Product
from apps.hrmn.models import Subsidiary, ClientSupplier
from apps.sales.models import Purchase, Sales, DetailSales


class SubsidiaryType(DjangoObjectType):
    class Meta:
        model = Subsidiary
        fields = '__all__'


class UserType(DjangoObjectType):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'date_joined')
        # exclude = ('password',)


class RegisterUserInput(graphene.InputObjectType):
    username = graphene.String(required=True)
    email = graphene.String(required=True)
    password1 = graphene.String(required=True)
    password2 = graphene.String(required=True)


class LoginUserInput(graphene.InputObjectType):
    username = graphene.String(required=True)
    password = graphene.String(required=True)


class AuthErrorType(graphene.ObjectType):
    field = graphene.String()
    message = graphene.String()


class RegisterUserPayload(graphene.ObjectType):
    user = graphene.Field(UserType)
    token = graphene.String()
    success = graphene.Boolean()
    errors = graphene.List(AuthErrorType)


class LoginUserPayload(graphene.ObjectType):
    user = graphene.Field(UserType)
    token = graphene.String()
    success = graphene.Boolean()
    errors = graphene.List(AuthErrorType)


class LogoutUserPayload(graphene.ObjectType):
    success = graphene.Boolean()
    message = graphene.String()


class ProductType(DjangoObjectType):
    class Meta:
        model = Product
        fields = '__all__'


class DetailSaleType(DjangoObjectType):
    """Type para el detalle de venta (DetailSales)"""

    class Meta:
        model = DetailSales
        fields = '__all__'


class SaleType(DjangoObjectType):
    """Type para la venta (Sales)"""

    class Meta:
        model = Sales
        fields = '__all__'

    # ✅ Usa referencia directa - DetailSaleType ya está definido arriba
    details = graphene.List(DetailSaleType)

    def resolve_details(self, info):
        """Obtener todos los detalles (productos) de esta venta"""
        return self.detailsales_set.all()


class PurchaseType(DjangoObjectType):
    class Meta:
        model = Purchase
        fields = '__all__'


class ClientSupplierType(DjangoObjectType):
    class Meta:
        model = ClientSupplier
        fields = '__all__'


class CreateProductInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    code = graphene.Int(required=True)
    price = graphene.Decimal(required=True)
    laboratory = graphene.String(required=True)
    alias = graphene.String(required=True)
    quantity = graphene.Int(required=True)
    # Campos opcionales
    purchase_price = graphene.Float()
    due_date = graphene.Date()
    subsidiary = graphene.Int()


class UpdateProductInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    code = graphene.Int(required=False)
    price = graphene.Decimal(required=False)
    laboratory = graphene.String(required=False)
    alias = graphene.String(required=True)
    quantity = graphene.Int(required=True)
    purchase_price = graphene.Float()
    due_date = graphene.Date()


# 1. INPUT TYPES (Agregar a tu archivo de types/inputs)
class DetailSaleInput(graphene.InputObjectType):
    """Input para un producto individual en la venta"""
    productId = graphene.ID(required=True)
    quantity = graphene.Int(required=True)
    price = graphene.Decimal(required=True)
    subtotal = graphene.Decimal(required=True)
    total = graphene.Decimal(required=True)
    observation = graphene.String(required=False)


class CreateSaleInput(graphene.InputObjectType):
    """Input para crear una venta con múltiples productos"""
    providerId = graphene.ID(required=False)  # Cliente (ClientSupplier) - opcional
    subsidiaryId = graphene.ID(required=False)  # Sucursal - opcional
    typeReceipt = graphene.String(required=True)  # 'B', 'F', 'T'
    typePay = graphene.String(required=True)  # 'E', 'Y', 'P'
    date = graphene.DateTime(required=False)  # Si no se envía, usar datetime.now()
    details = graphene.List(DetailSaleInput, required=True)  # Lista de productos


class CreatePurchaseInput(graphene.InputObjectType):
    productId = graphene.ID(required=True)
    quantity = graphene.Int(required=True)
    price = graphene.Decimal(required=True)
    subtotal = graphene.Decimal(required=True)
    total = graphene.Decimal(required=True)
    typeReceipt = graphene.String(required=True)
    typePay = graphene.String(required=True)
    date = graphene.DateTime()


class CreateClientSupplierInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    address = graphene.String(required=False)
    phone = graphene.String(required=False)
    mail = graphene.String(required=False)
    nDocument = graphene.Int(required=True)
    typeDocument = graphene.String(required=True)  # 'R','D','O'
    typePerson = graphene.String(required=True)  # 'C','E'


class UpdateClientSupplierInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    address = graphene.String(required=False)
    phone = graphene.String(required=False)
    mail = graphene.String(required=False)
    nDocument = graphene.Int(required=True)
    typeDocument = graphene.String(required=True)
    typePerson = graphene.String(required=True)



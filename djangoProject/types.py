import graphene
from graphene_django import DjangoObjectType
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction

from apps.products.models import Product
from apps.hrmn.models import Subsidiary


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
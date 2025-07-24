import graphene
from graphene_django import DjangoObjectType
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction


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
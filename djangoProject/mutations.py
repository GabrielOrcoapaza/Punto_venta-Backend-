import graphene
from graphql_jwt.shortcuts import get_token, create_refresh_token
from graphql import GraphQLError
from django.contrib.auth import authenticate
from apps.hrmn.models import Employee
from djangoProject.types import EmployeeType


class EmployeeLogin(graphene.Mutation):
    class Arguments:
        username = graphene.String(required=True)
        password = graphene.String(required=True)

    token = graphene.String()
    refresh_token = graphene.String()
    employee = graphene.Field(EmployeeType)
    permissions = graphene.List(graphene.String)

    @classmethod
    def mutate(cls, root, info, username, password):
        # Autenticar con el modelo Employee
        employee = authenticate(username=username, password=password)

        if not employee:
            raise GraphQLError("Credenciales incorrectas")

        if not employee.is_enabled:
            raise GraphQLError("Cuenta de empleado deshabilitada")

        # Obtener permisos del empleado
        permissions = []
        if employee.is_staff:
            permissions.append("staff")
        if employee.is_active:
            permissions.append("active")

        return cls(
            token=get_token(employee),
            refresh_token=create_refresh_token(employee),
            employee=employee,
            permissions=permissions
        )


class Mutation(graphene.ObjectType):
    employee_login = EmployeeLogin.Field()
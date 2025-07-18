import graphene
from apps.hrmn.models import Employee
from .types import EmployeeType
from graphql import GraphQLError


class EmployeeQuery(graphene.ObjectType):
    current_employee = graphene.Field(EmployeeType)
    employees = graphene.List(EmployeeType)

    def resolve_current_employee(self, info):
        employee = info.context.user
        if not employee.is_authenticated:
            raise GraphQLError("No autenticado")
        return employee

    def resolve_employees(self, info):
        employee = info.context.user
        if not employee.is_authenticated or not employee.is_staff:
            raise GraphQLError("No autorizado")
        return Employee.objects.filter(is_enabled=True)
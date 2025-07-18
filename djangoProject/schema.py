import graphene
from .queries import EmployeeQuery
from .mutations import Mutation as EmployeeMutation


class Query(EmployeeQuery, graphene.ObjectType):
    pass


class Mutation(EmployeeMutation, graphene.ObjectType):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)

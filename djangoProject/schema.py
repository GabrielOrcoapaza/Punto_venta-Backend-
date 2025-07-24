import graphene
from .queries import Query as QueryBase
from .mutations import Mutation as MutationBase


class Query(QueryBase, graphene.ObjectType):
    pass


class Mutation(MutationBase, graphene.ObjectType):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)

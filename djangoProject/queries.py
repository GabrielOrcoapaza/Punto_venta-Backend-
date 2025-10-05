import graphene
from graphene_django import DjangoObjectType
from django.contrib.auth.models import User
from django.contrib.auth import get_user

from apps.hrmn.models import ClientSupplier
from apps.products.models import Product
from apps.sales.models import Purchase
from .types import UserType, ProductType, PurchaseType, ClientSupplierType


class EmployeeQuery(graphene.ObjectType):
    # Mantén tus queries existentes de Employee aquí
    pass


class AuthQuery(graphene.ObjectType):
    me = graphene.Field(UserType)

    def resolve_me(self, info):
        user = info.context.user
        if user.is_authenticated:
            return user
        return None


class ProductQuery(graphene.ObjectType):
    products = graphene.List(ProductType)
    product = graphene.Field(ProductType, id=graphene.ID(required=True))

    def resolve_products(self, info):
        return Product.objects.all()

    def resolve_product(self, info, id):
        return Product.objects.get(pk=id)


class PurchaseQuery(graphene.ObjectType):
    purchases = graphene.List(PurchaseType)
    purchase = graphene.Field(PurchaseType, id=graphene.ID(required=True))

    def resolve_purchases(self, info):
        return Purchase.objects.all()

    def resolve_purchase(self, info, id):
        return Purchase.objects.get(pk=id)


class ClientSupplierQuery(graphene.ObjectType):
    clientSuppliers = graphene.List(ClientSupplierType)
    clientSupplier = graphene.Field(ClientSupplierType, id=graphene.ID(required=True))

    def resolve_clientSuppliers(self, info):
        return ClientSupplier.objects.all()

    def resolve_clientSupplier(self, info, id):
        return ClientSupplier.objects.get(pk=id)


class Query(EmployeeQuery, AuthQuery, ProductQuery, PurchaseQuery, ClientSupplierQuery, graphene.ObjectType):
    pass
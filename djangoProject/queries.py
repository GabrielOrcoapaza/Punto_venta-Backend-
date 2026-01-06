import graphene
from django.db.models import Sum
from graphene_django import DjangoObjectType
from django.contrib.auth.models import User
from django.contrib.auth import get_user

from apps.hrmn.models import ClientSupplier, Subsidiary
from apps.products.models import Product
from apps.sales.models import Purchase, Sales, Cash, Payment
from .types import UserType, ProductType, PurchaseType, ClientSupplierType, SaleType, CashType, PaymentType, \
    MethodTotal, CashSummaryType


class EmployeeQuery(graphene.ObjectType):
    # Mantén tus queries existentes de Employee aquí
    pass


class AuthQuery(graphene.ObjectType):
    me = graphene.Field(UserType)

    def resolve_me(self, info):
        user = info.context.user

        # Debug
        print("=" * 50)
        print(f"Usuario en contexto: {user}")
        print(f"¿Es anónimo?: {user.is_anonymous}")
        print(f"¿Está autenticado?: {user.is_authenticated}")
        print("=" * 50)

        # IMPORTANTE: Con JWT, el middleware ya debería haber
        # autenticado al usuario si el token es válido
        if user and user.is_authenticated:
            return user
        return None


class ProductQuery(graphene.ObjectType):
    products = graphene.List(ProductType)
    product = graphene.Field(ProductType, id=graphene.ID(required=True))

    def resolve_products(self, info):
        return Product.objects.all()

    def resolve_product(self, info, id):
        return Product.objects.get(pk=id)


class SaleQuery(graphene.ObjectType):
    sales = graphene.List(SaleType)
    sale = graphene.Field(SaleType, id=graphene.ID(required=True))

    def resolve_sales(self, info):
        return Sales.objects.all()

    def resolve_sale(self, info, id):
        return Sales.objects.get(pk=id)


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


class CashQuery(graphene.ObjectType):
    cashes = graphene.List(CashType)
    cash = graphene.Field(CashType, id=graphene.ID(required=True))
    currentCash = graphene.Field(CashType, subsidiaryId=graphene.ID(required=True))

    def resolve_cashes(self, info):
        return Cash.objects.all()

    def resolve_cash(self, info, id):
        return Cash.objects.get(pk=id)

    def resolve_currentCash(self, info, subsidiaryId):
        subsidiary = Subsidiary.objects.get(pk=subsidiaryId)
        return Cash.objects.filter(subsidiary=subsidiary, status='A').last()


class PaymentQuery(graphene.ObjectType):
    payments = graphene.List(PaymentType)
    payment = graphene.Field(PaymentType, id=graphene.ID(required=True))
    cashPayments = graphene.List(PaymentType, cashId=graphene.ID(required=True))

    def resolve_payments(self, info):
        return Payment.objects.all()

    def resolve_payment(self, info, id):
        return Payment.objects.get(pk=id)

    def resolve_cashPayments(self, info, cashId):
        return Payment.objects.filter(cash_id=cashId).order_by('payment_date')


class CashSummaryQuery(graphene.ObjectType):
    cashSummary = graphene.Field(CashSummaryType, cashId=graphene.ID(required=True))

    def resolve_cashSummary(self, info, cashId):
        cash = Cash.objects.get(pk=cashId)
        qs = Payment.objects.filter(cash=cash, status='PAID')
        by_method_qs = qs.values('payment_method').annotate(total=Sum('paid_amount'))
        by_method = [MethodTotal(method=x['payment_method'], total=x['total'] or 0) for x in by_method_qs]
        total_expected = qs.aggregate(t=Sum('paid_amount'))['t'] or 0
        total_counted = cash.closing_amount or 0
        difference = total_counted - total_expected
        return CashSummaryType(by_method=by_method, total_expected=total_expected, total_counted=total_counted,
                               difference=difference)


class Query(EmployeeQuery, AuthQuery, ProductQuery, SaleQuery, PurchaseQuery, ClientSupplierQuery, CashQuery,
            PaymentQuery, CashSummaryQuery, graphene.ObjectType):
    pass

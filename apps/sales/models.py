from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum, F, Q
from django.utils import timezone
from datetime import datetime

from apps import hrmn, sales
from apps.hrmn.models import ClientSupplier
from apps.products.models import Product

PAYMENT_METHODS = (
    ('E', 'EFECTIVO'),
    ('T', 'TARJETA'),
    ('Y', 'YAPE'),
    ('P', 'PLIN'),
)

PAYMENT_TYPES = (
    ('SALE', 'VENTA'),
    ('PURCHASE', 'COMPRA'),
    ('EXPENSE', 'EGRESO'),
    ('ADJUST', 'AJUSTE'),
)

PAYMENT_STATUS = (
    ('PENDING', 'PENDIENTE'),
    ('PAID', 'PAGADO'),
    ('CANCELLED', 'ANULADO'),
)


class Sales(models.Model):
    TYPE_RECEIPT_CHOICES = (('B', 'Boleta'), ('F', 'Factura'), ('T', 'Ticket'))
    TYPE_PAY_CHOICES = (('E', 'Efectivo'), ('Y', 'Yape'), ('P', 'Plin'))

    id = models.AutoField(primary_key=True)
    date_creation = models.DateTimeField(blank=True, null=True)
    date_cancel = models.DateTimeField(blank=True, null=True)
    employee_creation = models.ForeignKey('hrmn.Employee', on_delete=models.CASCADE,
                                          related_name='order_employee_create', blank=True, null=True)
    employee_cancel = models.ForeignKey('hrmn.Employee', on_delete=models.CASCADE,
                                        related_name='order_employee_cancel', blank=True, null=True)
    type_receipt = models.CharField(max_length=2, choices=TYPE_RECEIPT_CHOICES, default='B')
    type_pay = models.CharField(max_length=2, choices=TYPE_PAY_CHOICES, default='E')
    total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    provider = models.ForeignKey(ClientSupplier, on_delete=models.CASCADE, blank=True, null=True)
    subsidiary = models.ForeignKey('hrmn.Subsidiary', on_delete=models.CASCADE, related_name='order_subsidiary',
                                   blank=True, null=True)

    def __str__(self):
        return str(self.id)


class DetailSales(models.Model):
    id = models.AutoField(primary_key=True)
    sale = models.ForeignKey(Sales, on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.IntegerField(null=True, blank=True)
    quantity_cancel = models.IntegerField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    observation = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return str(self.id)


class Purchase(models.Model):
    TYPE_RECEIPT_CHOICES = (('B', 'Boleta'), ('F', 'Factura'))
    TYPE_PAY_CHOICES = (('E', 'Efectivo'), ('Y', 'Yape'), ('P', 'Plin'))

    id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, blank=True, null=True)
    provider = models.ForeignKey(ClientSupplier, on_delete=models.CASCADE, blank=True, null=True, default=None)
    quantity = models.IntegerField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    typeReceipt = models.CharField(max_length=2, choices=TYPE_RECEIPT_CHOICES, default='')
    typePay = models.CharField(max_length=2, choices=TYPE_PAY_CHOICES, default='E')
    date = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return str(self.id)


class Cash(models.Model):
    STATUS_CASH_CHOICES = (('A', 'APERTURA'), ('C', 'CIERRE'))

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='cashes')
    subsidiary = models.ForeignKey('hrmn.Subsidiary', on_delete=models.CASCADE, blank=True, null=True)

    status = models.CharField(max_length=1, choices=STATUS_CASH_CHOICES, default='C')
    initialAmount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    closingAmount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    difference = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    dateOpen = models.DateTimeField(null=True, blank=True)
    dateClose = models.DateTimeField(null=True, blank=True)

    totalSales = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'Cash'
        constraints = [
            models.UniqueConstraint(
                fields=['subsidiary'],
                condition=Q(status='A'),
                name='unique_open_cash_per_subsidiary'
            ),
        ]

    def cash_status(self):
        return self.status

    @staticmethod
    def get_open_cash(subsidiary):
        return Cash.objects.filter(subsidiary=subsidiary, status='A').last()


class Payment(models.Model):
    id = models.AutoField(primary_key=True)
    subsidiary = models.ForeignKey('hrmn.Subsidiary', on_delete=models.CASCADE, related_name='payments')
    cash = models.ForeignKey('sales.Cash', on_delete=models.PROTECT, related_name='payments')
    sale = models.ForeignKey('sales.Sales', on_delete=models.CASCADE, null=True, blank=True, related_name='payments')
    purchase = models.ForeignKey('Purchase', on_delete=models.CASCADE, null=True, blank=True, related_name='payments')

    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPES)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS)
    status = models.CharField(max_length=10, choices=PAYMENT_STATUS, default='PAID')

    payment_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField(null=True, blank=True)

    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))

    reference_number = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='payments')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if bool(self.sale) == bool(self.purchase):
            raise ValidationError('Debe asociarse a una venta o a una compra, no ambas.')
        if self.cash and self.cash.status != 'A':
            raise ValidationError('La caja debe estar abierta para registrar pagos.')

    def __str__(self):
        return f'{self.payment_date} - {self.paid_amount}'

    class Meta:
        db_table = 'Payment'
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['subsidiary', 'status']),
            models.Index(fields=['payment_date']),
            models.Index(fields=['payment_method']),
            models.Index(fields=['cash', 'payment_date']),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                        (models.Q(sale__isnull=False) & models.Q(purchase__isnull=True)) |
                        (models.Q(sale__isnull=True) & models.Q(purchase__isnull=False))
                ),
                name='payment_sale_xor_purchase'
            ),
        ]


# class CashFlow(models.Model):
#     STATUS_CASH_CHOICES = (('A', 'APERTURA'), ('C', 'CIERRE'))
#     RECEIPT_TYPE_CHOICES = (('F', 'FACTURA'), ('B', 'BOLETA'), ('T', 'TICKET'))
#     TYPE_PAY_CHOICES = (('E', 'EFECTIVO'), ('T', 'TARJETA'), ('Y', 'YAPE'), ('P', 'PLIN'))
#     id = models.AutoField(primary_key=True)
#     cash = models.ForeignKey('sales.Cash', on_delete=models.CASCADE, default=True)
#     order = models.ForeignKey('sales.Sales', on_delete=models.CASCADE, null=True, blank=True)
#     detailOrder = models.ForeignKey('sales.DetailSales', on_delete=models.CASCADE, null=True, blank=True)
#     # detailPlan = models.ForeignKey('sales.Detail_Plan', on_delete=models.CASCADE, default=True)
#     customer = models.CharField('Cliente', max_length=100, null=True, blank=True)
#     date = models.DateTimeField('Fecha de venta', null=True, blank=True)
#     # user = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, null=True)
#     receipt_type = models.CharField(max_length=1, choices=RECEIPT_TYPE_CHOICES, default='')
#     type_pay = models.CharField(max_length=1, choices=TYPE_PAY_CHOICES, default='')
#     status_cash = models.CharField(max_length=1, choices=STATUS_CASH_CHOICES, default='C')
#     total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
#
#     def __str__(self):
#         return str(self.id)
#
#     class Meta:
#         db_table = 'CashFlow'


class PaymentDistribution(models.Model):
    id = models.AutoField(primary_key=True)
    # cash_flow = models.ForeignKey(CashFlow, on_delete=models.CASCADE, related_name='distributions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'PaymentDistribution'


class Operation(models.Model):
    TYPE_OPERATION = (('E', 'ENTRADA'), ('S', 'SALIDA'), ('I', 'INICIAL'))
    TYPE_DOCUMENT = (('F', 'FACTURA'), ('B', 'BOLETA'), ('T', 'TICKET'), ('GU', 'GUIA'), ('N', 'NINGUNO'))
    OPERATION_CHOICES = (('C', 'COMPRA'), ('P', 'PRODUCCION'), ('A', 'AJUSTE'), ('T', 'TRASLADO'))

    id = models.AutoField(primary_key=True)
    employee = models.ForeignKey('hrmn.Employee', on_delete=models.CASCADE, related_name='operation_employee',
                                 blank=True, null=True)
    client_supplier = models.ForeignKey('hrmn.ClientSupplier', on_delete=models.CASCADE,
                                        related_name='operation_employee', blank=True, null=True)
    detail_order = models.ForeignKey('DetailSales', on_delete=models.CASCADE, related_name='operation_detail_order',
                                     blank=True, null=True)
    warehouse = models.ForeignKey('hrmn.Warehouse', on_delete=models.CASCADE, related_name='operation_warehouse',
                                  blank=True, null=True)
    quantity = models.IntegerField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    date = models.DateTimeField(blank=True, null=True)
    type_operation = models.CharField(max_length=1, choices=TYPE_OPERATION, default='')
    type_document = models.CharField(max_length=2, choices=TYPE_DOCUMENT, default='')
    n_document = models.CharField(max_length=45, blank=True, null=True)
    date_document = models.DateField(blank=True, null=True)
    operation = models.CharField(max_length=1, choices=OPERATION_CHOICES, default='')
    reference = models.ForeignKey('self', models.DO_NOTHING, related_name='operation_reference',
                                  blank=True, null=True)

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'Operation'

    def get_total_price(self):
        if self.quantity is not None and self.price is not None:
            return self.quantity * self.price
        return 0


class Device(models.Model):
    TYOE_DEVICE_CHOICES = (('S', 'SALIDA'), ('E', 'ENTRADA'))
    # TIPO_DISPOSITIVO_CHOICES = [('S', 'SALIDA'),
    #                             ('E', 'ENTRADA')]
    id = models.AutoField(primary_key=True)
    subsidiary = models.ForeignKey('hrmn.Subsidiary', on_delete=models.CASCADE, related_name='device_employees',
                                   blank=True, null=True)
    name = models.CharField(max_length=200, blank=True, null=True)
    mac = models.CharField(max_length=200, blank=True, null=True)
    type = models.CharField(max_length=1, choices=TYOE_DEVICE_CHOICES, default='E')
    is_enabled = models.BooleanField(default=True)

    def __str__(self):
        return str(self.name)

    class Meta:
        db_table = 'Device'


class PrintCategory(models.Model):
    id = models.AutoField(primary_key=True)
    category = models.ForeignKey('products.Category', on_delete=models.CASCADE, related_name='print_category_category',
                                 blank=True, null=True)
    device = models.ForeignKey('Device', on_delete=models.CASCADE, related_name='print_category_device',
                               blank=True, null=True)
    is_enabled = models.BooleanField(default=True)
    observation = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'PrintCategory'

# Create your models here.

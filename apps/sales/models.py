from django.db import models
# Create your models here.
from django.db.models import Sum, F
from django.utils import timezone
from datetime import datetime


# from enum import Enum

# from apps.employees.models import Empleado
# from django_mysql.models import EnumField
# from django_enum import Enumfield
from apps.hrmn.models import ClientSupplier
from apps.products.models import Product


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
    # quantity = models.IntegerField(null=True, blank=True)
    # price = models.IntegerField(null=True, blank=True)
    # subtotal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # date = models.DateTimeField(blank=True, null=True)
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
    provider = models.ForeignKey(ClientSupplier, on_delete=models.CASCADE, blank=True, null=True)
    quantity = models.IntegerField(null=True, blank=True)
    price = models.IntegerField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    typeReceipt = models.CharField(max_length=2, choices=TYPE_RECEIPT_CHOICES, default='')
    typePay = models.CharField(max_length=2, choices=TYPE_PAY_CHOICES, default='E')

    observation = models.TextField(max_length=500, null=True, blank=True)
    date = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return str(self.id)


class Cash(models.Model):
    # STATE_CASH_CHOICES = (('A', 'APERTURA'), ('C', 'CIERRE'))
    id = models.AutoField(primary_key=True)
    name = models.CharField('Nombre de caja', max_length=100, null=True, blank=True)
    employee = models.ForeignKey('hrmn.Employee', on_delete=models.CASCADE, null=True, blank=True)
    initial_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date_open = models.DateTimeField('Fecha de apertura', null=True, blank=True)
    date_close = models.DateTimeField('Fecha de cierre', null=True, blank=True)
    total_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subsidiary = models.ForeignKey('hrmn.Subsidiary', on_delete=models.CASCADE, blank=True, null=True)

    # state_cash = models.CharField(max_length=1, choices=STATE_CASH_CHOICES, default='')

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'Cash'

    def cash_status(self):
        status = 'C'
        cash_flow_set = CashFlow.objects.filter(cash=self, status_cash__in=['A', 'C'])
        if cash_flow_set.exists():
            cash_flow_obj = cash_flow_set.last()
            return cash_flow_obj.status_cash
        else:
            return status

    @staticmethod
    def get_open_cash(subsidiary):
        """
        Retorna la caja abierta (status 'A') para una empresa (company) específica.
        """
        cash_flow = CashFlow.objects.filter(cash__subsidiary=subsidiary, status_cash='A').last()
        if cash_flow:
            return cash_flow.cash
        return None


class CashFlow(models.Model):
    STATUS_CASH_CHOICES = (('A', 'APERTURA'), ('C', 'CIERRE'))
    RECEIPT_TYPE_CHOICES = (('F', 'FACTURA'), ('B', 'BOLETA'), ('T', 'TICKET'))
    TYPE_PAY_CHOICES = (('E', 'EFECTIVO'), ('T', 'TARJETA'), ('Y', 'YAPE'), ('P', 'PLIN'))
    id = models.AutoField(primary_key=True)
    cash = models.ForeignKey('sales.Cash', on_delete=models.CASCADE, default=True)
    order = models.ForeignKey('sales.Sales', on_delete=models.CASCADE, null=True, blank=True)
    detailOrder = models.ForeignKey('sales.DetailSales', on_delete=models.CASCADE, null=True, blank=True)
    # detailPlan = models.ForeignKey('sales.Detail_Plan', on_delete=models.CASCADE, default=True)
    customer = models.CharField('Cliente', max_length=100, null=True, blank=True)
    date = models.DateTimeField('Fecha de venta', null=True, blank=True)
    # user = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, null=True)
    receipt_type = models.CharField(max_length=1, choices=RECEIPT_TYPE_CHOICES, default='')
    type_pay = models.CharField(max_length=1, choices=TYPE_PAY_CHOICES, default='')
    status_cash = models.CharField(max_length=1, choices=STATUS_CASH_CHOICES, default='C')
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'CashFlow'


class PaymentDistribution(models.Model):
    id = models.AutoField(primary_key=True)
    cash_flow = models.ForeignKey(CashFlow, on_delete=models.CASCADE, related_name='distributions')
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

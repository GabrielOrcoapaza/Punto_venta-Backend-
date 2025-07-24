from django.contrib.auth.models import AbstractUser
from django.db import models
# from django_mysql.models import EnumField


# Create your models here.
class Employee(models.Model):
    id = models.AutoField(primary_key=True)
    name_lastname = models.CharField(max_length=200, unique=True, blank=True, null=True)
    n_document = models.IntegerField(unique=True, blank=True, null=True)
    charge = models.ForeignKey('Charge', on_delete=models.CASCADE, blank=True, null=True)
    subsidiary = models.ForeignKey('Subsidiary', on_delete=models.CASCADE, blank=True, null=True)
    date_birth = models.DateField(blank=True, null=True)
    phone = models.CharField('Telefono', max_length=100, blank=True, null=True)
    is_enabled = models.BooleanField(default=True)
    password = models.CharField(max_length=100, blank=True, null=True)
    foto = models.ImageField(upload_to='employee_photo/', default='empleoyee_photo/img_empleado.jpg', null=True,
                             blank=True)

    def __str__(self):
        return str(self.name_lastname)

    class Meta:
        db_table = 'Employee'


class Subsidiary(models.Model):
    id = models.AutoField(primary_key=True)
    company = models.ForeignKey('Company', on_delete=models.CASCADE, blank=True, null=True)
    subsidiary = models.CharField(max_length=100, blank=True, null=True)
    # business_name = models.CharField('Razon social', max_length=45, null=True, blank=True)
    address = models.CharField(max_length=150, blank=True, null=True)
    phone = models.CharField(max_length=45, blank=True, null=True)
    logo = models.ImageField(upload_to='subsidiary')
    is_enabled = models.BooleanField(default=True)
    password = models.CharField(max_length=100, blank=True, null=True)
    serie = models.CharField(max_length=45, blank=True, null=True)

    # is_main = models.BooleanField('Sede principal', default=False)

    def __str__(self):
        return str(self.subsidiary)

    class Meta:
        db_table = 'Subsidiary'


# class Company(AbstractUser):
class Company(models.Model):
    id = models.AutoField(primary_key=True)
    ruc = models.CharField(unique=True, max_length=11, blank=True, null=True)
    company = models.CharField('Empresa', max_length=150, blank=True, null=True)
    igv = models.IntegerField(blank=True, null=True)
    url = models.CharField(max_length=600, blank=True, null=True)
    token = models.CharField(max_length=600, blank=True, null=True)
    logo = models.TextField(blank=True, null=True)
    is_enabled = models.BooleanField(default=True)
    password = models.CharField(max_length=100, blank=True, null=True)
    billing_top = models.BooleanField(default=True)
    rrhh = models.BooleanField(default=True)
    logistic = models.BooleanField(default=True)
    production = models.BooleanField(default=True)
    account_suspend = models.BooleanField(default=True)
    suspend_date = models.DateField(blank=True, null=True)
    web = models.BooleanField(default=True)
    app = models.BooleanField(default=True)
    desktop = models.BooleanField(default=True)

    def __str__(self):
        return str(self.company)

    class Meta:
        db_table = 'Company'


class Charge(models.Model):
    id = models.AutoField(primary_key=True)
    subsidiary = models.ForeignKey('Subsidiary', on_delete=models.CASCADE, blank=True,
                                   null=True)
    charge = models.CharField(max_length=50, blank=True, null=True)
    description = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return str(self.charge)

    class Meta:
        db_table = 'Charge'


class Warehouse(models.Model):
    id = models.AutoField(primary_key=True)
    subsidiary = models.ForeignKey('Subsidiary', on_delete=models.CASCADE, blank=True,
                                   null=True)
    warehouse = models.CharField(max_length=45, blank=True, null=True)
    is_enabled = models.BooleanField(default=True)

    def __str__(self):
        return str(self.warehouse)

    class Meta:
        db_table = 'Warehouse'


class ClientSupplier(models.Model):
    TYPE_PERSON_CHOICE = (('C', 'Cliente'), ('E', 'Empresa'))
    TYPE_DOCUMENT_CHOICE = (('D', 'DNI'), ('R', 'RUC'), ('O', 'Otros'))
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200, blank=True, null=True)
    address = models.CharField(max_length=200, blank=True, null=True)
    phone = models.CharField(max_length=100, blank=True, null=True)
    mail = models.CharField(max_length=100, blank=True, null=True)
    n_document = models.IntegerField(blank=True, null=True)
    type_document = models.CharField(max_length=1, choices=TYPE_DOCUMENT_CHOICE, default='R')
    type_person = models.CharField(max_length=1, choices=TYPE_PERSON_CHOICE, default='E')

    def __str__(self):
        return str(self.name)

    class Meta:
        db_table = 'ClientSupplier'

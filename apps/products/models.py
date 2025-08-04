from django.db import models

# Create your models here.
from django.db import models
# Create your models here.


class Category(models.Model):
    id = models.AutoField(primary_key=True)
    subsidiary = models.ForeignKey('hrmn.Subsidiary', on_delete=models.CASCADE, related_name='category_subsidiary',
                                   blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    description = models.CharField(verbose_name='Descripción',
                                   max_length=200, null=True, blank=True)
    is_enabled = models.BooleanField(default=True)

    def __str__(self):
        return str(self.category)

    class Meta:
        db_table = 'Category'


class SubCategory(models.Model):
    id = models.AutoField(primary_key=True)
    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name='subcategory_category', blank=True,
                                 null=True)
    subcategory = models.CharField(max_length=100)
    description = models.CharField(verbose_name='Descripción', max_length=200, null=True, blank=True)
    is_enabled = models.BooleanField(default=True)

    def __str__(self):
        return str(self.subcategory)

    class Meta:
        db_table = 'SubCategory'


class Observation(models.Model):
    id = models.AutoField(primary_key=True)
    observation = models.CharField('Observaciones', max_length=200, null=True, blank=True)
    subcategory = models.ForeignKey('SubCategory', on_delete=models.CASCADE, related_name='observation_subcategory',
                                    null=True,
                                    blank=True)

    def __str__(self):
        return str(self.observation)

    class Meta:
        db_table = 'Observation'


class Product(models.Model):
    id = models.AutoField(primary_key=True)
    code = models.IntegerField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    alias = models.CharField(max_length=100, null=True, blank=True)
    quantity = models.IntegerField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, )
    laboratory = models.CharField(max_length=100, null=True, blank=True)
    subsidiary = models.ForeignKey('hrmn.Subsidiary', on_delete=models.CASCADE, blank=True, null=True)

    def __str__(self):
        return str(self.id)


class UnitMeasure(models.Model):
    id = models.AutoField(primary_key=True)
    unit_measure = models.CharField(max_length=100, blank=True, null=True)
    unit_measure_sunat = models.CharField(unique=True, max_length=200, blank=True, null=True)
    code_sunat = models.CharField(unique=True, max_length=100, blank=True, null=True)
    is_enabled = models.BooleanField(default=True)

    def __str__(self):
        return str(self.unit_measure)

    class Meta:
        db_table = 'UnitMeasure'

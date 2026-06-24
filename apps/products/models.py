from django.db import models

# Create your models here.
from django.db import models
# Create your models here.

PRESCRIPTION_TYPE = (
    ('OTC', 'Venta libre'),
    ('REQUIRED',   'Requiere receta médica'),
    ('CONTROLLED', 'Medicamento controlado'),
    ('NA', 'No aplica'),
)


class Category(models.Model):
    id = models.AutoField(primary_key=True)
    subsidiary = models.ForeignKey('hrmn.Subsidiary', on_delete=models.CASCADE, related_name='category_subsidiary',
                                   blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    description = models.CharField(verbose_name='Descripción',
                                   max_length=200, null=True, blank=True)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['category']

    def __str__(self):
        return str(self.category)


class SubCategory(models.Model):
    id = models.AutoField(primary_key=True)
    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name='subcategory_category', blank=True,
                                 null=True)
    subcategory = models.CharField(max_length=100)
    description = models.CharField(verbose_name='Descripción', max_length=200, null=True, blank=True)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Subcategoría'
        verbose_name_plural = 'Subcategorías'
        ordering = ['subcategory']

    def __str__(self):
        return str(self.subcategory)


class Observation(models.Model):
    id = models.AutoField(primary_key=True)
    observation = models.CharField('Observaciones', max_length=200, null=True, blank=True)
    subcategory = models.ForeignKey('SubCategory', on_delete=models.CASCADE, related_name='observation_subcategory',
                                    null=True,
                                    blank=True)

    class Meta:
        verbose_name = 'Observación'
        verbose_name_plural = 'Observaciones'
        ordering = ['observation']

    def __str__(self):
        return str(self.observation)


class Product(models.Model):

    """
        Producto de la farmacia.

        IMPORTANTE — stock y vencimiento NO van aquí:
          - El stock vive en ProductStock (por sucursal y opcionalmente por lote).
          - La fecha de vencimiento vive en ProductStock también,
            porque cada lote o entrada puede tener su propio vencimiento.

        Tipos de venta:
          OTC        = venta libre
          REQUIRED   = requiere receta (se retiene copia)
          CONTROLLED = medicamento controlado (ENACO)
    """

    id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=100, null=True, blank=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    alias = models.CharField(max_length=100, null=True, blank=True)
    prescription_type = models.CharField(
        'Tipo de venta',
        max_length=20,
        choices=PRESCRIPTION_TYPE,
        default='OTC',
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, )
    laboratory = models.CharField(max_length=100, null=True, blank=True)
    subsidiary = models.ForeignKey('hrmn.Subsidiary', on_delete=models.CASCADE, blank=True, null=True,
                                   related_name='products')
    is_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['name']),
            models.Index(fields=['prescription_type']),
            models.Index(fields=['is_enabled']),
        ]

    def __str__(self):
        return str(self.name)


class UnitMeasure(models.Model):
    id = models.AutoField(primary_key=True)
    unit_measure = models.CharField(max_length=100, blank=True, null=True)
    unit_measure_sunat = models.CharField(unique=True, max_length=200, blank=True, null=True)
    code_sunat = models.CharField(unique=True, max_length=100, blank=True, null=True)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Unidad de medida'
        verbose_name_plural = 'Unidades de medida'
        ordering = ['unit_measure']

    def __str__(self):
        return str(self.unit_measure)


class ProductStock(models.Model):
    """
    Stock del producto por sucursal.

    Cubre tres escenarios de farmacia:

    1. Farmacia SIN lote NI vencimiento:
       batch_number=None, due_date=None → solo controla cantidad

    2. Farmacia CON vencimiento pero SIN número de lote (lo más común):
       batch_number=None, due_date=2025-12-31 → controla cuándo vence

    3. Farmacia CON lote Y vencimiento (DIGEMID estricto):
       batch_number='LOT-001', due_date=2025-12-31 → trazabilidad completa

    La regla FEFO (First Expired First Out) aplica en el caso 2 y 3:
    al vender se descuenta del registro con due_date más próxima.

        Consulta FEFO:
        ProductStock.objects
            .filter(subsidiary=s, product=p, quantity__gt=0, due_date__isnull=False)
            .order_by('due_date')
    """
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='stock_entries',
        verbose_name='Producto',
    )
    subsidiary = models.ForeignKey(
        'hrmn.Subsidiary',
        on_delete=models.CASCADE,
        related_name='stock_entries',
        verbose_name='Sucursal',
    )
    # Número de lote: opcional. None si la farmacia no lo registra.
    batch_number = models.CharField(
        'Número de lote', max_length=100, null=True, blank=True,
        help_text='Dejar vacío si la farmacia no maneja número de lote',
    )
    # Fecha de vencimiento por entrada de stock (lote o compra)
    due_date = models.DateField(
        'Fecha de vencimiento', null=True, blank=True,
        help_text='Vencimiento de este lote o entrada de mercadería',
    )
    quantity = models.DecimalField(
        'Cantidad', max_digits=10, decimal_places=3, default=0,
    )
    # Precio de compra real de esta entrada (puede variar por lote)
    purchase_price = models.DecimalField(
        'Precio de compra', max_digits=10, decimal_places=2, null=True, blank=True,
    )
    created_at = models.DateTimeField('Fecha de ingreso', auto_now_add=True)
    updated_at = models.DateTimeField('Última actualización', auto_now=True)

    class Meta:
        verbose_name = 'Stock de producto'
        verbose_name_plural = 'Stocks de producto'
        # Un producto puede tener varios registros por sucursal
        # diferenciados por número de lote (o por due_date si no hay lote)
        unique_together = ('product', 'subsidiary', 'batch_number', 'due_date')
        ordering = ['due_date']
        indexes = [
            models.Index(fields=['subsidiary', 'product']),
            models.Index(fields=['due_date']),
        ]

    def __str__(self):
        lote = f"Lote {self.batch_number}" if self.batch_number else "Sin lote"
        return f"{self.product.name} | {lote} | Vence {self.due_date}"
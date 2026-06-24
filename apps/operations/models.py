from django.utils import timezone

from django.core.validators import MinValueValidator
from django.db import models

from apps.hrmn.models import Person

OPERATION_TYPES = [
    ('SALE', 'Venta'),
    ('PURCHASE', 'Compra'),
    ('ADJUSTMENT', 'Ajuste de inventario'),
    ('PRODUCTION', 'Producción'),
    ('TRANSFER', 'Transferencia'),
]

PAYMENT_METHODS = [
    ('CASH', 'Efectivo'),
    ('YAPE', 'Yape'),
    ('PLIN', 'Plin'),
    ('CARD', 'Tarjeta'),
    ('TRANSFER', 'Transferencia Bancaria'),
    ('OTROS', 'Otros'),
]

OPERATION_STATUS = [
    ('PROCESSING', 'Procesando'),  # Preparando pedidos
    ('COMPLETED', 'Completada'),  # Orden terminada y pagada
    ('CANCELLED', 'Anulada')  # Orden cancelada
]

PAYMENT_TYPES = [
    ('CASH', 'Contado'),
    ('CREDIT', 'Crédito'),
]


class Supplier(models.Model):
    """
    Proveedor / distribuidor de productos.
    Ej: DECO, Química Suiza, Albis, representaciones locales
    """
    name = models.CharField('Nombre / Razón social', max_length=200)
    ruc = models.CharField('RUC', max_length=11, null=True, blank=True, unique=True)
    contact = models.CharField('Contacto', max_length=150, null=True, blank=True)
    phone = models.CharField('Teléfono', max_length=30, null=True, blank=True)
    email = models.EmailField('Email', null=True, blank=True)
    address = models.TextField('Dirección', blank=True)
    is_enabled = models.BooleanField('Activo', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['name']

    def __str__(self):
        return self.name


class Operation(models.Model):
    """
    Cabecera de cualquier operación del sistema:
      SALE       → venta al cliente (ticket interno)
      PURCHASE   → compra a proveedor
      ADJUSTMENT → ajuste manual de inventario
      PRODUCTION → producción interna
      TRANSFER   → transferencia entre sucursales

    person  = cliente (en ventas) o proveedor (en compras), opcional
    seller  = cajero/empleado que registra la operación

    La sesión de caja (CashSession) vive en finances y se vincula
    con cash_session_id para evitar dependencia circular entre apps.

    Estados:
      PROCESSING → en curso, aún no finalizada
      COMPLETED  → terminada y pagada
      CANCELLED  → anulada (nunca se elimina, solo se marca)
    """
    id = models.AutoField(primary_key=True)
    # ── Identificación ───────────────────────────────────────────
    ticket_number = models.CharField('N° Ticket', max_length=20, unique=True)
    # ── Contexto ─────────────────────────────────────────────────
    subsidiary = models.ForeignKey('hrmn.Subsidiary', on_delete=models.PROTECT, related_name='sales',
                                   verbose_name='Sucursal')
    # ID de finances.CashSession — evita dependencia circular entre apps
    cash_session_id = models.IntegerField(
        'ID sesión de caja',
        help_text='ID de finances.CashSession al que pertenece esta venta',
    )
    seller = models.ForeignKey(
        'hrmn.Person',
        on_delete=models.PROTECT,
        related_name='sales',
        verbose_name='Vendedor / cajero',
        null=True, blank=True,
    )

    # ── Receta médica ────────────────────────────────────────────
    prescription_number = models.CharField(
        'N° Receta médica', max_length=100,
        null=True, blank=True,
        help_text='Obligatorio si la venta incluye productos con receta',
    )
    operation_type = models.CharField('Tipo de operación', max_length=20, choices=OPERATION_TYPES, default='SALE')
    # ── Totales ──────────────────────────────────────────────────
    subtotal = models.DecimalField('Subtotal', max_digits=10, decimal_places=2, default=0)
    igv = models.DecimalField('IGV', max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField('Total', max_digits=10, decimal_places=2, default=0)

    # ── Estado ───────────────────────────────────────────────────
    status = models.CharField(max_length=26, choices=OPERATION_STATUS, default='PROCESSING')
    person = models.ForeignKey('hrmn.Person', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='operations',verbose_name='Cliente / Proveedor')
    notes = models.TextField('Notas', blank=True)
    created_at = models.DateTimeField('Fecha / hora de venta', auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ticket_number']),
            models.Index(fields=['subsidiary', 'created_at']),
            models.Index(fields=['cash_session_id']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Ticket {self.ticket_number} — S/{self.total}"


class OperationDetail(models.Model):
    """
    Línea de detalle de una venta.

    unit_price se congela al momento de la venta porque el precio
    del producto puede cambiar después.

    product_stock guarda el lote específico del que se descontó
    el stock para trazabilidad FEFO.
    """
    operation = models.ForeignKey(
        Operation, on_delete=models.CASCADE,
        related_name='items', verbose_name='Venta',
    )
    product = models.ForeignKey(
        'products.Product', on_delete=models.PROTECT,
        related_name='sale_items', verbose_name='Producto',
    )
    product_stock = models.ForeignKey(
        'products.ProductStock', on_delete=models.PROTECT,
        related_name='sale_items', verbose_name='Lote / entrada',
        null=True, blank=True,
        help_text='Lote del que se descontó según regla FEFO',
    )
    quantity = models.DecimalField(
        'Cantidad', max_digits=10, decimal_places=3,
        validators=[MinValueValidator(0.001)],
    )
    batch_number = models.CharField(max_length=100, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    unit_price = models.DecimalField('Precio unitario', max_digits=10, decimal_places=2)
    subtotal = models.DecimalField('Subtotal', max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Detalle de la operacion'
        verbose_name_plural = 'Detalles de las operaciones'
        ordering = ['id']

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} x{self.quantity} — S/{self.subtotal}"


class Payment(models.Model):
    """
    Pago(s) de una venta.
    Una venta puede pagarse con varios métodos a la vez.
    Ej: S/30 efectivo + S/20 Yape = total S/50

    amount_tendered y change_amount solo aplican para EFECTIVO.
    reference aplica para pagos digitales (N° operación Yape, etc.)
    """
    sale = models.ForeignKey(
        Operation, on_delete=models.CASCADE,
        related_name='payments', verbose_name='Venta',
    )
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)

    amount = models.DecimalField(
        'Monto pagado', max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    amount_tendered = models.DecimalField(
        'Monto entregado', max_digits=10, decimal_places=2,
        null=True, blank=True,
        help_text='Solo efectivo: cuánto entregó el cliente',
    )
    change_amount = models.DecimalField(
        'Vuelto', max_digits=10, decimal_places=2,
        null=True, blank=True,
    )
    reference = models.CharField(
        'N° Operación / referencia', max_length=100,
        null=True, blank=True,
        help_text='N° de operación para Yape, Plin, transferencia',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pago de venta'
        verbose_name_plural = 'Pagos de venta'
        ordering = ['id']

    def __str__(self):
        return f"{self.sale.ticket_number} | {self.payment_method} | S/{self.amount}"


class Return(models.Model):
    """
    Devolución de cliente — siempre referencia a una venta original.
    Al confirmar se devuelve el stock al ProductStock correspondiente.
    """

    class ReturnReason(models.TextChoices):
        WRONG_PRODUCT = 'wrong_product', 'Producto equivocado'
        EXPIRED = 'expired', 'Producto vencido / dañado'
        CHANGED_MIND = 'changed_mind', 'Cambio de receta / decisión'
        OTHER = 'other', 'Otro motivo'

    return_number = models.CharField('N° Devolución', max_length=20, unique=True)
    operation = models.ForeignKey(
        Operation, on_delete=models.PROTECT,
        related_name='returns', verbose_name='Venta original',
    )
    subsidiary = models.ForeignKey(
        'hrmn.Subsidiary', on_delete=models.PROTECT,
        related_name='returns', verbose_name='Sucursal',
    )
    processed_by = models.ForeignKey(
        'hrmn.Person', on_delete=models.PROTECT,
        related_name='returns', verbose_name='Procesado por',
        null=True, blank=True,
    )
    reason = models.CharField(
        'Motivo', max_length=30,
        choices=ReturnReason.choices,
        default=ReturnReason.OTHER,
    )
    reason_detail = models.TextField('Detalle del motivo', blank=True)
    total_refund = models.DecimalField('Total a devolver', max_digits=10, decimal_places=2, default=0)
    refund_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)

    created_at = models.DateTimeField('Fecha devolución', auto_now_add=True)
    notes = models.TextField('Notas', blank=True)

    class Meta:
        verbose_name = 'Devolución'
        verbose_name_plural = 'Devoluciones'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['return_number']),
            models.Index(fields=['operation']),
            models.Index(fields=['subsidiary', 'created_at']),
        ]

    def __str__(self):
        return f"Dev. {self.return_number} — Ticket {self.operation.ticket_number}"


class ReturnItem(models.Model):
    """
    Línea de detalle de una devolución.
    Referencia al SaleItem original para saber exactamente
    qué producto y de qué lote se está devolviendo.
    """
    return_order = models.ForeignKey(
        Return, on_delete=models.CASCADE,
        related_name='items', verbose_name='Devolución',
    )
    sale_item = models.ForeignKey(
        OperationDetail, on_delete=models.PROTECT,
        related_name='return_items', verbose_name='Línea de venta original',
    )
    quantity = models.DecimalField(
        'Cantidad devuelta', max_digits=10, decimal_places=3,
        validators=[MinValueValidator(0.001)],
    )
    unit_price = models.DecimalField('Precio unitario', max_digits=10, decimal_places=2)
    subtotal = models.DecimalField('Subtotal a devolver', max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Línea de devolución'
        verbose_name_plural = 'Líneas de devolución'
        ordering = ['id']

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sale_item.product.name} x{self.quantity}"


# ─────────────────────────────────────────────────────────────────
# TRANSFERENCIAS ENTRE SUCURSALES
# ─────────────────────────────────────────────────────────────────

class Transfer(models.Model):
    """
    Transferencia de stock entre sucursales o almacenes.
    Ej: Almacén central → Sucursal Norte

    Estados:
      PENDING    → registrada, aún no enviada
      IN_TRANSIT → enviada, aún no confirmada en destino
      RECEIVED   → confirmada, stock ya actualizado en destino
      CANCELLED  → cancelada
    """

    class TransferStatus(models.TextChoices):
        PENDING = 'pending', 'Pendiente de envío'
        IN_TRANSIT = 'in_transit', 'En tránsito'
        RECEIVED = 'received', 'Recibida'
        CANCELLED = 'cancelled', 'Cancelada'

    transfer_number = models.CharField('N° Transferencia', max_length=20, unique=True)
    from_subsidiary = models.ForeignKey(
        'hrmn.Subsidiary', on_delete=models.PROTECT,
        related_name='transfers_out', verbose_name='Sucursal origen',
    )
    to_subsidiary = models.ForeignKey(
        'hrmn.Subsidiary', on_delete=models.PROTECT,
        related_name='transfers_in', verbose_name='Sucursal destino',
    )
    requested_by = models.ForeignKey(
        'hrmn.Person', on_delete=models.PROTECT,
        related_name='transfers_requested', verbose_name='Solicitado por',
        null=True, blank=True,
    )
    received_by = models.ForeignKey(
        'hrmn.Person', on_delete=models.PROTECT,
        related_name='transfers_received', verbose_name='Recibido por',
        null=True, blank=True,
    )
    status = models.CharField(
        'Estado', max_length=20,
        choices=TransferStatus.choices,
        default=TransferStatus.PENDING,
    )
    transfer_date = models.DateField('Fecha', default=timezone.now)
    received_at = models.DateTimeField('Fecha de recepción', null=True, blank=True)
    notes = models.TextField('Notas', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Transferencia'
        verbose_name_plural = 'Transferencias'
        ordering = ['-transfer_date']
        indexes = [
            models.Index(fields=['transfer_number']),
            models.Index(fields=['from_subsidiary']),
            models.Index(fields=['to_subsidiary']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Transf. {self.transfer_number} | {self.from_subsidiary} → {self.to_subsidiary}"


class TransferItem(models.Model):
    """
    Línea de detalle de una transferencia.
    Se especifica el lote (product_stock) para mantener
    la trazabilidad FEFO en la sucursal destino.
    """
    transfer = models.ForeignKey(
        Transfer, on_delete=models.CASCADE,
        related_name='items', verbose_name='Transferencia',
    )
    product = models.ForeignKey(
        'products.Product', on_delete=models.PROTECT,
        related_name='transfer_items', verbose_name='Producto',
    )
    product_stock = models.ForeignKey(
        'products.ProductStock', on_delete=models.PROTECT,
        related_name='transfer_items', verbose_name='Lote / entrada origen',
        null=True, blank=True,
    )
    quantity = models.DecimalField(
        'Cantidad', max_digits=10, decimal_places=3,
        validators=[MinValueValidator(0.001)],
    )

    class Meta:
        verbose_name = 'Línea de transferencia'
        verbose_name_plural = 'Líneas de transferencia'
        ordering = ['id']

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from apps.operations.models import Operation

# Create your models here.
CASH_TYPES = [
    ('CASH', 'Caja'),
    ('BANK', 'Cuenta Bancaria'),
    ('DIGITAL', 'Billetera Digital'),
]

PAYMENT_TYPES = [
    ('CASH', 'Contado'),
    ('CREDIT', 'Crédito'),
]

PAYMENT_METHODS = [
    ('CASH', 'Efectivo'),
    ('YAPE', 'Yape'),
    ('PLIN', 'Plin'),
    ('CARD', 'Tarjeta'),
    ('TRANSFER', 'Transferencia Bancaria'),
    ('OTROS', 'Otros'),
]

PAYMENT_STATUS = [
    ('PENDING', 'Pendiente'),
    ('PAID', 'Pagado'),
    ('PARTIAL', 'Parcial'),
    ('CANCELLED', 'Cancelado')
]

TRANSACTION_TYPES = [
    ('INCOME', 'Ingreso'),
    ('EXPENSE', 'Gasto'),
]

CURRENCY_CHOICES = [
    ('PEN', 'Soles'),
    ('USD', 'Dólares'),
]

BILLING_STATUS = [
    ('PROCESSING', 'Procesando'),
    ('SENT', 'Enviado'),
    ('ACCEPTED', 'Emitido'),
    ('ACCEPTED_WITH_OBSERVATIONS', 'Emitido con observaciones'),
    ('REJECTED', 'Rechazado'),
    ('ERROR', 'Error'),
    ('PROCESSING_CANCELLATION', 'Procesando anulación'),
    ('CANCELLATION_PENDING', 'Anulación pendiente'),
    ('CANCELLED', 'Anulado'),
    ('CANCELLATION_ERROR', 'Error en anulación'),
]


DOCUMENT_TYPES = [
    ('TICKET', 'Ticket interno'),
    ('BOLETA', 'Boleta'),
    ('FACTURA', 'Factura'),

]


# ─────────────────────────────────────────────────────────────────
# CAJA FÍSICA
# ─────────────────────────────────────────────────────────────────

class CashRegister(models.Model):
    """
    Caja física / estación de trabajo.
    El administrador la crea y existe permanentemente.
    Una sucursal puede tener varias cajas.
    Ej: Sucursal Centro → Caja 1, Caja 2
    """
    name = models.CharField('Nombre', max_length=100,
                            help_text='Ej: Caja 1, Estación Farmacia')
    code = models.CharField('Código', max_length=20, unique=True,
                            help_text='Ej: CAJA-01')
    subsidiary = models.ForeignKey(
        'hrmn.Subsidiary', on_delete=models.PROTECT,
        related_name='cash_registers', verbose_name='Sucursal',
    )
    is_enabled = models.BooleanField('Activa', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Caja'
        verbose_name_plural = 'Cajas'
        ordering = ['subsidiary', 'name']
        indexes = [models.Index(fields=['subsidiary', 'is_enabled'])]

    def __str__(self):
        return f"{self.name} — {self.subsidiary}"

    @property
    def current_session(self):
        return self.sessions.filter(status='open').first()


# ─────────────────────────────────────────────────────────────────
# TURNO DE CAJA
# ─────────────────────────────────────────────────────────────────

class CashSession(models.Model):
    """
    Turno de un cajero en una caja específica.

    Flujo completo:
      1. Cajero llega → abre su turno en su caja
      2. Trabaja → todas sus operaciones llevan cash_session_id
      3. Al cerrar → declara cuánto tiene por cada método (CashSessionDeclared)
      4. El sistema compara lo declarado vs lo real (CashSessionSummary)
      5. Se genera el IssuedDocument con el resumen agrupado del turno
      6. Turno queda CLOSED

    Regla: una caja solo puede tener UN turno abierto a la vez.
    """

    class SessionStatus(models.TextChoices):
        OPEN = 'open', 'Abierto'
        CLOSED = 'closed', 'Cerrado'

    cash_register = models.ForeignKey(
        CashRegister, on_delete=models.PROTECT,
        related_name='sessions', verbose_name='Caja',
    )
    seller = models.ForeignKey(
        'hrmn.Person', on_delete=models.PROTECT,
        related_name='cash_sessions', verbose_name='Cajero',
    )

    # ── Apertura ─────────────────────────────────────────────────
    opened_at = models.DateTimeField('Hora de apertura', default=timezone.now)
    opening_amount = models.DecimalField(
        'Fondo inicial (efectivo)', max_digits=10, decimal_places=2, default=0,
        help_text='Efectivo que había en la caja al iniciar el turno',
    )

    # ── Cierre ───────────────────────────────────────────────────
    closed_at = models.DateTimeField('Hora de cierre', null=True, blank=True)

    # ── Totales reales calculados por el sistema al cerrar ────────
    total_sales = models.DecimalField('Total ventas', max_digits=12, decimal_places=2, default=0)
    total_purchases = models.DecimalField('Total compras', max_digits=12, decimal_places=2, default=0)
    total_returns = models.DecimalField('Total devoluciones', max_digits=12, decimal_places=2, default=0)
    total_operations = models.IntegerField('N° operaciones', default=0)

    status = models.CharField(
        'Estado', max_length=10,
        choices=SessionStatus.choices, default=SessionStatus.OPEN,
    )
    notes = models.TextField('Notas', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Turno de caja'
        verbose_name_plural = 'Turnos de caja'
        ordering = ['-opened_at']
        indexes = [
            models.Index(fields=['cash_register', 'status']),
            models.Index(fields=['seller', 'status']),
            models.Index(fields=['opened_at']),
        ]
        constraints = [
            # Una caja no puede tener dos turnos abiertos al mismo tiempo
            models.UniqueConstraint(
                fields=['cash_register'],
                condition=models.Q(status='open'),
                name='unique_open_session_per_register',
            )
        ]

    def __str__(self):
        return (
            f"{self.cash_register} | {self.seller} | "
            f"{self.opened_at.strftime('%d/%m/%Y %H:%M')} | {self.get_status_display()}"
        )

    @property
    def is_open(self):
        return self.status == self.SessionStatus.OPEN

    @property
    def duration(self):
        end = self.closed_at or timezone.now()
        delta = end - self.opened_at
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes = remainder // 60
        return f"{hours}h {minutes}m"


# ─────────────────────────────────────────────────────────────────
# DECLARACIÓN DEL CAJERO (verificación antes del cierre)
# ─────────────────────────────────────────────────────────────────

class CashSessionDeclared(models.Model):
    """
    Lo que el cajero declara tener por cada método de pago
    ANTES de que el sistema calcule los totales reales.

    Ejemplo:
      Cajero cuenta su caja y declara:
        Efectivo  → S/ 800.00  (contó físicamente)
        Yape      → S/ 310.00  (revisó su celular)
        Tarjeta   → S/ 150.00  (revisó el POS)

      Luego el sistema calcula lo real (CashSessionSummary)
      y genera la diferencia:
        Efectivo  → declarado S/800 vs real S/850 → diferencia -S/50 (faltante)
        Yape      → declarado S/310 vs real S/320 → diferencia -S/10 (faltante)
        Tarjeta   → declarado S/150 vs real S/150 → diferencia S/0  (cuadra)

    Una sesión tiene UNA declaración por método de pago.
    """
    cash_session = models.ForeignKey(
        CashSession, on_delete=models.CASCADE,
        related_name='declared', verbose_name='Turno de caja',
    )
    payment_method = models.CharField(
        'Método de pago', max_length=20, choices=PAYMENT_METHODS,
    )
    declared_amount = models.DecimalField(
        'Monto declarado por el cajero', max_digits=12, decimal_places=2, default=0,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Declaración del cajero'
        verbose_name_plural = 'Declaraciones del cajero'
        unique_together = ('cash_session', 'payment_method')
        ordering = ['payment_method']

    def __str__(self):
        return (
            f"{self.cash_session} | {self.get_payment_method_display()} "
            f"| Declarado: S/{self.declared_amount}"
        )


# ─────────────────────────────────────────────────────────────────
# RESUMEN REAL DEL SISTEMA (calculado al cerrar)
# ─────────────────────────────────────────────────────────────────

class CashSessionSummary(models.Model):
    """
    Totales REALES por método de pago, calculados por el sistema
    al momento del cierre. Se comparan con CashSessionDeclared.

    Campos:
      system_amount  → lo que el sistema dice que debería haber
      declared_amount→ lo que el cajero dijo que tenía
      difference     → system_amount - declared_amount
                       Positivo = sobrante / Negativo = faltante
    """
    cash_session = models.ForeignKey(
        CashSession, on_delete=models.CASCADE,
        related_name='summaries', verbose_name='Turno de caja',
    )
    payment_method = models.CharField(
        'Método de pago', max_length=20, choices=PAYMENT_METHODS,
    )

    # ── Calculado por el sistema ──────────────────────────────────
    total_sales = models.DecimalField('Total ventas', max_digits=12, decimal_places=2, default=0)
    total_returns = models.DecimalField('Total devoluciones', max_digits=12, decimal_places=2, default=0)
    system_amount = models.DecimalField(
        'Total real (sistema)', max_digits=12, decimal_places=2, default=0,
        help_text='ventas - devoluciones según el sistema',
    )

    # ── Declarado por el cajero ───────────────────────────────────
    declared_amount = models.DecimalField(
        'Total declarado (cajero)', max_digits=12, decimal_places=2, default=0,
    )

    # ── Diferencia ────────────────────────────────────────────────
    difference = models.DecimalField(
        'Diferencia', max_digits=12, decimal_places=2, default=0,
        help_text='Positivo = sobrante | Negativo = faltante',
    )

    class Meta:
        verbose_name = 'Resumen de cierre por método de pago'
        verbose_name_plural = 'Resúmenes de cierre por método de pago'
        unique_together = ('cash_session', 'payment_method')
        ordering = ['payment_method']

    def __str__(self):
        return (
            f"{self.get_payment_method_display()} | "
            f"Sistema: S/{self.system_amount} | "
            f"Declarado: S/{self.declared_amount} | "
            f"Dif: S/{self.difference}"
        )

    def save(self, *args, **kwargs):
        self.system_amount = self.total_sales - self.total_returns
        self.difference = self.declared_amount - self.system_amount
        super().save(*args, **kwargs)

    
class IssuedDocument(models.Model):
    """
    Documento emitido por una venta.

    Una Operation puede generar UNO o VARIOS IssuedDocument:

    Caso 1 — pago mixto, un solo documento:
        Venta S/50 (Efectivo S/30 + Yape S/20)
        → 1 Ticket con todos los productos

    Caso 2 — el cliente pide dividir:
        Venta S/100 (Efectivo S/40 + Tarjeta S/60)
        → 1 Boleta con el producto A (S/60, pagado con tarjeta)
        → 1 Ticket con los productos B y C (S/40, pagado en efectivo)

    Los ítems de cada documento van en IssuedDocumentItem,
    que apunta al OperationDetail específico — así sabes exactamente
    qué productos están en cada documento.

    Por ahora document_type=TICKET no va a SUNAT (billing_status=PENDING).
    Cuando implementes facturación electrónica, BOLETA y FACTURA
    usarán los campos sunat_* que ya están preparados.
    """

    # ── Relación con la venta ─────────────────────────────────────
    operation = models.ForeignKey(
        'operations.Operation',
        on_delete=models.CASCADE,
        related_name='issued_documents',
        verbose_name='Venta',
        help_text='Una venta puede generar más de un documento',
    )

    # ── Tipo y numeración ─────────────────────────────────────────
    document_type = models.CharField(
        'Tipo de documento', max_length=10,
        choices=DOCUMENT_TYPES, default='TICKET',
    )
    # Serie y número — para tickets internos puedes usar T001-000001
    # Para boletas/facturas electrónicas: B001-000123, F001-000456
    serial = models.CharField(
        'Serie', max_length=10,
        help_text='Ej: T001 (ticket), B001 (boleta), F001 (factura)',
    )
    number = models.IntegerField('Número', default=1)

    # ── Cliente ───────────────────────────────────────────────────
    # Puede ser el mismo que Operation.person o diferente
    # (ej: la boleta va a nombre de otra persona)
    person = models.ForeignKey(
        'hrmn.Person',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='issued_documents',
        verbose_name='Cliente',
    )

    # ── Sucursal y cajero ─────────────────────────────────────────
    subsidiary = models.ForeignKey(
        'hrmn.Subsidiary',
        on_delete=models.PROTECT,
        related_name='issued_documents',
        verbose_name='Sucursal',
    )
    seller = models.ForeignKey(
        'hrmn.Person',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='issued_documents_as_seller',
        verbose_name='Cajero',
    )

    # ── Fechas ────────────────────────────────────────────────────
    emission_date = models.DateField('Fecha de emisión')
    emission_time = models.TimeField('Hora de emisión')

    # ── Moneda ────────────────────────────────────────────────────
    currency = models.CharField('Moneda', max_length=3, choices=CURRENCY_CHOICES, default='PEN')
    exchange_rate = models.DecimalField('Tipo de cambio', max_digits=10, decimal_places=4, default=1)

    # ── Totales ───────────────────────────────────────────────────
    # Solo los productos de los IssuedDocumentItem de ESTE documento
    subtotal = models.DecimalField('Subtotal (sin IGV)', max_digits=15, decimal_places=4, default=0)
    igv_amount = models.DecimalField('IGV', max_digits=15, decimal_places=4, default=0)
    total = models.DecimalField('Total', max_digits=15, decimal_places=4, default=0)

    # ── Estado de facturación ─────────────────────────────────────
    # TICKET → siempre PENDING (no va a SUNAT)
    # BOLETA / FACTURA → pasa por PROCESSING → ACCEPTED / REJECTED
    billing_status = models.CharField(
        'Estado SUNAT', max_length=100,
        choices=BILLING_STATUS, default='PROCESSING',
    )

    # ── Campos SUNAT (vacíos por ahora, listos para el futuro) ────
    sunat_operation_id = models.BigIntegerField(null=True, blank=True)
    sunat_response_code = models.CharField(max_length=10, null=True, blank=True)
    sunat_response_description = models.TextField(null=True, blank=True)
    xml_path = models.CharField(max_length=800, null=True, blank=True)
    signed_xml_path = models.CharField(max_length=800, null=True, blank=True)
    cdr_path = models.CharField(max_length=800, null=True, blank=True)
    hash_code = models.CharField(max_length=800, null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=5)
    last_retry_at = models.DateTimeField(null=True, blank=True)

    # ── Anulación ─────────────────────────────────────────────────
    cancellation_reason = models.CharField(max_length=2, null=True, blank=True,
                                           choices=[
                                               ('01', 'Anulación de la operación'),
                                               ('02', 'Error en el RUC'),
                                               ('03', 'Error en la descripción'),
                                               ('06', 'Devolución total'),
                                               ('07', 'Devolución parcial'),
                                           ]
                                           )
    cancellation_description = models.TextField(null=True, blank=True)
    cancellation_date = models.DateField(null=True, blank=True)

    # Re-emisión: si se anuló un ticket y se emite una boleta
    parent_document = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='child_documents',
        verbose_name='Documento origen (re-emisión)',
        help_text='Documento anulado del que nació este',
    )

    notes = models.TextField('Notas', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Documento emitido'
        verbose_name_plural = 'Documentos emitidos'
        ordering = ['-emission_date', '-number']
        # Serie + número únicos por sucursal
        unique_together = ['subsidiary', 'serial', 'number']
        indexes = [
            models.Index(fields=['operation']),
            models.Index(fields=['subsidiary', 'emission_date']),
            models.Index(fields=['billing_status']),
            models.Index(fields=['document_type']),
            models.Index(fields=['person', 'emission_date']),
        ]

    def __str__(self):
        return f"{self.serial}-{self.number:06d} ({self.get_document_type_display()})"

    @classmethod
    def get_next_number(cls, subsidiary_id: int, serial: str) -> int:
        """
        Siguiente número disponible para una serie en una sucursal.
        Ej: T001 tiene hasta el 00050 → retorna 51
        """
        last = cls.objects.filter(
            subsidiary_id=subsidiary_id,
            serial=serial,
        ).order_by('-number').first()
        return (last.number + 1) if last else 1

    @property
    def is_electronic(self):
        """¿Este documento va a SUNAT?"""
        return self.document_type in ('BOLETA', 'FACTURA', 'NOTA_CD', 'NOTA_DB')

    @property
    def full_number(self):
        """Número completo legible. Ej: T001-000051"""
        return f"{self.serial}-{self.number:06d}"


class IssuedDocumentItem(models.Model):
    """
    Producto incluido en un IssuedDocument específico.

    Apunta al OperationDetail — así sabes exactamente de qué
    línea de la venta viene este ítem y a qué lote pertenece.

    En el caso de división de documentos:
        OperationDetail A → IssuedDocumentItem en Boleta
        OperationDetail B → IssuedDocumentItem en Ticket
        OperationDetail C → IssuedDocumentItem en Ticket

    Un OperationDetail no puede aparecer en dos documentos del mismo tipo
    pero sí puede dividirse (ej: 3 unidades en boleta + 2 en ticket).
    """
    issued_document = models.ForeignKey(
        IssuedDocument,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Documento',
    )
    operation_detail = models.ForeignKey(
        'operations.OperationDetail',
        on_delete=models.PROTECT,
        related_name='issued_items',
        verbose_name='Línea de venta',
    )

    # Cantidad incluida en ESTE documento (puede ser parcial)
    quantity = models.DecimalField('Cantidad', max_digits=15, decimal_places=4)

    # Precios copiados al emitir (no cambian aunque el producto cambie de precio)
    unit_value = models.DecimalField('Precio unitario sin IGV', max_digits=15, decimal_places=4)
    unit_price = models.DecimalField('Precio unitario con IGV', max_digits=15, decimal_places=4)

    # Totales de esta línea en este documento
    subtotal = models.DecimalField('Subtotal sin IGV', max_digits=15, decimal_places=4, default=0)
    total = models.DecimalField('Total con IGV', max_digits=15, decimal_places=4, default=0)

    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ítem de documento'
        verbose_name_plural = 'Ítems de documento'
        ordering = ['id']

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_value
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} x {self.operation_detail.product.name} → {self.issued_document.full_number}"

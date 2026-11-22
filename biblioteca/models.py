from django.db import models
from django.db.models import Q


class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre")

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Autor(models.Model):
    nombre = models.CharField(max_length=150, verbose_name="Nombre")

    class Meta:
        verbose_name = "Autor"
        verbose_name_plural = "Autores"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Libro(models.Model):
    titulo = models.CharField(max_length=200, verbose_name="Título")
    anio_publicacion = models.PositiveIntegerField(verbose_name="Año de publicación")
    isbn = models.CharField(max_length=20, unique=True, verbose_name="ISBN")
    idioma = models.CharField(
        max_length=50,
        default="Español",
        verbose_name="Idioma",
    )
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name="libros",
        verbose_name="Categoría",
    )
    autores = models.ManyToManyField(
        Autor,
        related_name="libros",
        verbose_name="Autores",
    )

    class Meta:
        verbose_name = "Libro"
        verbose_name_plural = "Libros"
        ordering = ["titulo"]

    def __str__(self):
        return f"{self.titulo} ({self.anio_publicacion})"


class Ejemplar(models.Model):
    class Condicion(models.TextChoices):
        NUEVO = "nuevo", "Nuevo"
        USADO = "usado", "Usado"
        DANADO = "danado", "Dañado"

    libro = models.ForeignKey(
        Libro,
        on_delete=models.PROTECT,
        related_name="ejemplares",
        verbose_name="Libro",
    )
    codigo_inventario = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Código de inventario",
    )
    condicion = models.CharField(
        max_length=20,
        choices=Condicion.choices,
        default=Condicion.NUEVO,
        verbose_name="Condición",
    )

    class Meta:
        verbose_name = "Ejemplar"
        verbose_name_plural = "Ejemplares"
        ordering = ["codigo_inventario"]

    def __str__(self):
        return f"{self.codigo_inventario} — {self.libro.titulo} ({self.get_condicion_display()})"


class Estudiante(models.Model):
    codigo_estudiantil = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Código estudiantil",
    )
    nombre = models.CharField(max_length=150, verbose_name="Nombre completo")
    correo = models.EmailField(unique=True, verbose_name="Correo electrónico")

    class Meta:
        verbose_name = "Estudiante"
        verbose_name_plural = "Estudiantes"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.codigo_estudiantil} — {self.nombre}"


class Prestamo(models.Model):
    ejemplar = models.ForeignKey(
        Ejemplar,
        on_delete=models.PROTECT,
        related_name="prestamos",
        verbose_name="Ejemplar",
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.PROTECT,
        related_name="prestamos",
        verbose_name="Estudiante",
    )
    fecha_prestamo = models.DateField(
        auto_now_add=True,
        verbose_name="Fecha de préstamo",
    )
    fecha_limite = models.DateField(verbose_name="Fecha límite de devolución")
    fecha_devolucion = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha real de devolución",
    )

    class Meta:
        verbose_name = "Préstamo"
        verbose_name_plural = "Préstamos"
        ordering = ["-fecha_prestamo", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["ejemplar"],
                condition=Q(fecha_devolucion__isnull=True),
                name="unico_prestamo_activo_por_ejemplar",
                violation_error_message=(
                    "Este ejemplar ya tiene un préstamo activo y no puede "
                    "prestarse nuevamente hasta ser devuelto."
                ),
            )
        ]

    @property
    def esta_activo(self):
        return self.fecha_devolucion is None

    def __str__(self):
        estado = (
            "Activo"
            if self.fecha_devolucion is None
            else f"Devuelto ({self.fecha_devolucion})"
        )
        return f"{self.ejemplar.codigo_inventario} -> {self.estudiante.nombre} [{estado}]"

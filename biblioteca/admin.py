from django.contrib import admin
from django.db.models import Count, Q
from django.utils import timezone

from .models import Autor, Categoria, Ejemplar, Estudiante, Libro, Prestamo

admin.site.site_header = "Biblioteca UFPS — Administración"
admin.site.site_title = "Biblioteca UFPS"
admin.site.index_title = "Panel de gestión de préstamos y catálogo"


class EstadoPrestamoFilter(admin.SimpleListFilter):
    title = "estado del préstamo"
    parameter_name = "estado"

    def lookups(self, request, model_admin):
        return [
            ("activo", "Activos (sin devolver)"),
            ("devuelto", "Devueltos"),
            ("vencido", "Vencidos (sin devolver)"),
        ]

    def queryset(self, request, queryset):
        hoy = timezone.localdate()
        if self.value() == "activo":
            return queryset.filter(fecha_devolucion__isnull=True)
        if self.value() == "devuelto":
            return queryset.filter(fecha_devolucion__isnull=False)
        if self.value() == "vencido":
            return queryset.filter(
                fecha_devolucion__isnull=True,
                fecha_limite__lt=hoy,
            )
        return queryset


class TienePrestamoActivoFilter(admin.SimpleListFilter):
    title = "préstamos activos"
    parameter_name = "con_prestamo_activo"

    def lookups(self, request, model_admin):
        return [
            ("si", "Con préstamo activo"),
            ("no", "Sin préstamos activos"),
        ]

    def queryset(self, request, queryset):
        activos_ids = Prestamo.objects.filter(
            fecha_devolucion__isnull=True
        ).values("estudiante_id")
        if self.value() == "si":
            return queryset.filter(pk__in=activos_ids)
        if self.value() == "no":
            return queryset.exclude(pk__in=activos_ids)
        return queryset


class EjemplarInline(admin.TabularInline):
    model = Ejemplar
    extra = 1
    fields = ("codigo_inventario", "condicion")


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "total_libros")
    search_fields = ("nombre",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_total_libros=Count("libros"))

    @admin.display(description="Libros", ordering="_total_libros")
    def total_libros(self, obj):
        return obj._total_libros


@admin.register(Autor)
class AutorAdmin(admin.ModelAdmin):
    list_display = ("nombre", "total_libros")
    search_fields = ("nombre",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_total_libros=Count("libros"))

    @admin.display(description="Libros", ordering="_total_libros")
    def total_libros(self, obj):
        return obj._total_libros


@admin.register(Libro)
class LibroAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "isbn",
        "idioma",
        "categoria",
        "anio_publicacion",
        "mostrar_autores",
        "total_ejemplares",
    )
    search_fields = ("titulo", "isbn", "autores__nombre")
    list_filter = ("categoria", "idioma", "anio_publicacion")
    filter_horizontal = ("autores",)
    inlines = [EjemplarInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("categoria")
            .prefetch_related("autores", "ejemplares")
        )

    @admin.display(description="Autores")
    def mostrar_autores(self, obj):
        return ", ".join(autor.nombre for autor in obj.autores.all())

    @admin.display(description="Ejemplares")
    def total_ejemplares(self, obj):
        return obj.ejemplares.count()


@admin.register(Ejemplar)
class EjemplarAdmin(admin.ModelAdmin):
    list_display = ("codigo_inventario", "libro", "condicion", "disponible")
    search_fields = ("codigo_inventario", "libro__titulo", "libro__isbn")
    list_filter = ("condicion", "libro__categoria")
    autocomplete_fields = ("libro",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("libro", "libro__categoria")
            .annotate(
                _prestamos_activos=Count(
                    "prestamos",
                    filter=Q(prestamos__fecha_devolucion__isnull=True),
                )
            )
        )

    @admin.display(boolean=True, description="¿Disponible?")
    def disponible(self, obj):
        return obj._prestamos_activos == 0


@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ("codigo_estudiantil", "nombre", "correo", "prestamos_activos")
    search_fields = ("codigo_estudiantil", "nombre", "correo")
    list_filter = (TienePrestamoActivoFilter,)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _prestamos_activos=Count(
                    "prestamos",
                    filter=Q(prestamos__fecha_devolucion__isnull=True),
                )
            )
        )

    @admin.display(description="Préstamos activos", ordering="_prestamos_activos")
    def prestamos_activos(self, obj):
        return obj._prestamos_activos


@admin.action(description="Marcar préstamos seleccionados como devueltos (hoy)")
def marcar_como_devueltos(modeladmin, request, queryset):
    hoy = timezone.localdate()
    actualizados = queryset.filter(fecha_devolucion__isnull=True).update(
        fecha_devolucion=hoy
    )
    modeladmin.message_user(
        request,
        f"Se marcaron {actualizados} préstamo(s) como devuelto(s) con fecha {hoy}.",
    )


@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = (
        "ejemplar",
        "estudiante",
        "fecha_prestamo",
        "fecha_limite",
        "fecha_devolucion",
        "esta_devuelto",
    )
    search_fields = (
        "estudiante__codigo_estudiantil",
        "estudiante__nombre",
        "ejemplar__codigo_inventario",
        "ejemplar__libro__titulo",
    )
    list_filter = (EstadoPrestamoFilter, "fecha_prestamo", "fecha_limite")
    readonly_fields = ("fecha_prestamo",)
    autocomplete_fields = ("estudiante", "ejemplar")
    actions = [marcar_como_devueltos]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("estudiante", "ejemplar", "ejemplar__libro")
        )

    @admin.display(boolean=True, description="¿Devuelto?")
    def esta_devuelto(self, obj):
        return obj.fecha_devolucion is not None

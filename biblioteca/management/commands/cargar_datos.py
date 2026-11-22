from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from biblioteca.models import Autor, Categoria, Ejemplar, Estudiante, Libro, Prestamo


class Command(BaseCommand):
    help = "Carga datos de prueba iniciales para la Biblioteca UFPS (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limpiar",
            action="store_true",
            help="Elimina los datos existentes de biblioteca antes de cargar los datos de prueba.",
        )

    def handle(self, *args, **options):
        if options["limpiar"]:
            Prestamo.objects.all().delete()
            Ejemplar.objects.all().delete()
            Libro.objects.all().delete()
            Autor.objects.all().delete()
            Categoria.objects.all().delete()
            Estudiante.objects.all().delete()
            self.stdout.write(self.style.WARNING("Datos anteriores eliminados."))

        # 1. Categorías
        novela, _ = Categoria.objects.get_or_create(nombre="Novela")
        ingenieria, _ = Categoria.objects.get_or_create(nombre="Ingeniería")
        historia, _ = Categoria.objects.get_or_create(nombre="Historia")
        Categoria.objects.get_or_create(nombre="Ciencia Ficción")

        # 2. Autores
        gabo, _ = Autor.objects.get_or_create(nombre="Gabriel García Márquez")
        martin, _ = Autor.objects.get_or_create(nombre="Robert C. Martin")
        harari, _ = Autor.objects.get_or_create(nombre="Yuval Noah Harari")
        hunt, _ = Autor.objects.get_or_create(nombre="Andrew Hunt")
        thomas, _ = Autor.objects.get_or_create(nombre="David Thomas")

        # 3. Libros
        cien_anios, _ = Libro.objects.get_or_create(
            isbn="978-0307474728",
            defaults={
                "titulo": "Cien años de soledad",
                "anio_publicacion": 1967,
                "idioma": "Español",
                "categoria": novela,
            },
        )
        cien_anios.autores.set([gabo])

        amor_colera, _ = Libro.objects.get_or_create(
            isbn="978-0307389732",
            defaults={
                "titulo": "El amor en los tiempos del cólera",
                "anio_publicacion": 1985,
                "idioma": "Español",
                "categoria": novela,
            },
        )
        amor_colera.autores.set([gabo])

        clean_code, _ = Libro.objects.get_or_create(
            isbn="978-0132350884",
            defaults={
                "titulo": "Clean Code",
                "anio_publicacion": 2008,
                "idioma": "Inglés",
                "categoria": ingenieria,
            },
        )
        clean_code.autores.set([martin])

        pragmatic, _ = Libro.objects.get_or_create(
            isbn="978-0135957059",
            defaults={
                "titulo": "The Pragmatic Programmer",
                "anio_publicacion": 1999,
                "idioma": "Inglés",
                "categoria": ingenieria,
            },
        )
        pragmatic.autores.set([hunt, thomas])

        sapiens, _ = Libro.objects.get_or_create(
            isbn="978-8499926223",
            defaults={
                "titulo": "Sapiens: De animales a dioses",
                "anio_publicacion": 2011,
                "idioma": "Español",
                "categoria": historia,
            },
        )
        sapiens.autores.set([harari])

        # 4. Ejemplares (9 copias físicas)
        ejemplares_data = [
            ("LIB-001", cien_anios, Ejemplar.Condicion.USADO),
            ("LIB-002", cien_anios, Ejemplar.Condicion.NUEVO),
            ("LIB-003", amor_colera, Ejemplar.Condicion.USADO),
            ("LIB-004", clean_code, Ejemplar.Condicion.NUEVO),
            ("LIB-005", clean_code, Ejemplar.Condicion.USADO),
            ("LIB-006", clean_code, Ejemplar.Condicion.DANADO),
            ("LIB-007", pragmatic, Ejemplar.Condicion.NUEVO),
            ("LIB-008", sapiens, Ejemplar.Condicion.NUEVO),
            ("LIB-009", sapiens, Ejemplar.Condicion.USADO),
        ]
        ejemplares = {}
        for codigo, libro, condicion in ejemplares_data:
            ej, _ = Ejemplar.objects.get_or_create(
                codigo_inventario=codigo,
                defaults={"libro": libro, "condicion": condicion},
            )
            ejemplares[codigo] = ej

        # 5. Estudiantes (5 estudiantes; Valentina sin préstamos)
        estudiantes_data = [
            ("1152001", "Laura Martínez", "laura.martinez@ufps.edu.co"),
            ("1152002", "Carlos Ramírez", "carlos.ramirez@ufps.edu.co"),
            ("1152003", "Sofía Gómez", "sofia.gomez@ufps.edu.co"),
            ("1152004", "Andrés López", "andres.lopez@ufps.edu.co"),
            ("1152005", "Valentina Torres", "valentina.torres@ufps.edu.co"),
        ]
        estudiantes = {}
        for codigo, nombre, correo in estudiantes_data:
            est, _ = Estudiante.objects.get_or_create(
                codigo_estudiantil=codigo,
                defaults={"nombre": nombre, "correo": correo},
            )
            estudiantes[codigo] = est

        # 6. Préstamos (solo se crean si aún no hay préstamos cargados)
        if not Prestamo.objects.exists():
            hoy = timezone.localdate()
            prestamos_data = [
                # 3 préstamos ya devueltos
                (
                    ejemplares["LIB-004"],
                    estudiantes["1152001"],
                    hoy - timedelta(days=20),
                    hoy - timedelta(days=10),
                    hoy - timedelta(days=11),
                ),
                (
                    ejemplares["LIB-005"],
                    estudiantes["1152002"],
                    hoy - timedelta(days=18),
                    hoy - timedelta(days=8),
                    hoy - timedelta(days=9),
                ),
                (
                    ejemplares["LIB-001"],
                    estudiantes["1152003"],
                    hoy - timedelta(days=15),
                    hoy - timedelta(days=5),
                    hoy - timedelta(days=6),
                ),
                # 4 préstamos activos (fecha_devolucion=None)
                (
                    ejemplares["LIB-004"],
                    estudiantes["1152004"],
                    hoy - timedelta(days=4),
                    hoy + timedelta(days=10),
                    None,
                ),
                (
                    ejemplares["LIB-001"],
                    estudiantes["1152001"],
                    hoy - timedelta(days=3),
                    hoy + timedelta(days=11),
                    None,
                ),
                (
                    ejemplares["LIB-007"],
                    estudiantes["1152001"],
                    hoy - timedelta(days=2),
                    hoy + timedelta(days=12),
                    None,
                ),
                (
                    ejemplares["LIB-008"],
                    estudiantes["1152002"],
                    hoy - timedelta(days=12),
                    hoy - timedelta(days=2),  # préstamo vencido
                    None,
                ),
            ]
            for ejemplar, estudiante, f_prestamo, f_limite, f_dev in prestamos_data:
                p = Prestamo.objects.create(
                    ejemplar=ejemplar,
                    estudiante=estudiante,
                    fecha_limite=f_limite,
                    fecha_devolucion=f_dev,
                )
                # Ajustamos fecha_prestamo histórica para datos realistas
                Prestamo.objects.filter(pk=p.pk).update(fecha_prestamo=f_prestamo)

        self.stdout.write(
            self.style.SUCCESS(
                f"Datos cargados correctamente: "
                f"{Categoria.objects.count()} categorías, "
                f"{Autor.objects.count()} autores, "
                f"{Libro.objects.count()} libros, "
                f"{Ejemplar.objects.count()} ejemplares, "
                f"{Estudiante.objects.count()} estudiantes, "
                f"{Prestamo.objects.count()} préstamos."
            )
        )

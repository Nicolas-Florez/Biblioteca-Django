from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.models import Count, ProtectedError
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from biblioteca.models import Autor, Categoria, Ejemplar, Estudiante, Libro, Prestamo


class BibliotecaModelosYReglasTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nombre="Ingeniería")
        self.autor = Autor.objects.create(nombre="Robert C. Martin")
        self.libro = Libro.objects.create(
            titulo="Clean Code",
            anio_publicacion=2008,
            isbn="978-0132350884",
            idioma="Inglés",
            categoria=self.categoria,
        )
        self.libro.autores.add(self.autor)
        self.ejemplar = Ejemplar.objects.create(
            libro=self.libro,
            codigo_inventario="LIB-100",
            condicion=Ejemplar.Condicion.NUEVO,
        )
        self.est1 = Estudiante.objects.create(
            codigo_estudiantil="1152100",
            nombre="Ana Pérez",
            correo="ana.perez@ufps.edu.co",
        )
        self.est2 = Estudiante.objects.create(
            codigo_estudiantil="1152101",
            nombre="Luis Rojas",
            correo="luis.rojas@ufps.edu.co",
        )

    def test_str_legible_en_todos_los_modelos(self):
        self.assertEqual(str(self.categoria), "Ingeniería")
        self.assertEqual(str(self.autor), "Robert C. Martin")
        self.assertIn("Clean Code", str(self.libro))
        self.assertIn("LIB-100", str(self.ejemplar))
        self.assertIn("Clean Code", str(self.ejemplar))
        self.assertIn("1152100", str(self.est1))
        prestamo = Prestamo.objects.create(
            ejemplar=self.ejemplar,
            estudiante=self.est1,
            fecha_limite=timezone.localdate() + timedelta(days=7),
        )
        self.assertIn("LIB-100", str(prestamo))
        self.assertIn("Ana Pérez", str(prestamo))

    def test_no_permite_dos_prestamos_activos_misma_copia_en_bd(self):
        hoy = timezone.localdate()
        Prestamo.objects.create(
            ejemplar=self.ejemplar,
            estudiante=self.est1,
            fecha_limite=hoy + timedelta(days=7),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Prestamo.objects.create(
                    ejemplar=self.ejemplar,
                    estudiante=self.est2,
                    fecha_limite=hoy + timedelta(days=7),
                )

    def test_no_permite_dos_prestamos_activos_misma_copia_en_full_clean(self):
        hoy = timezone.localdate()
        Prestamo.objects.create(
            ejemplar=self.ejemplar,
            estudiante=self.est1,
            fecha_limite=hoy + timedelta(days=7),
        )
        duplicado = Prestamo(
            ejemplar=self.ejemplar,
            estudiante=self.est2,
            fecha_limite=hoy + timedelta(days=7),
        )
        with self.assertRaises(ValidationError):
            duplicado.full_clean()

    def test_permite_nuevo_prestamo_tras_devolucion(self):
        hoy = timezone.localdate()
        p1 = Prestamo.objects.create(
            ejemplar=self.ejemplar,
            estudiante=self.est1,
            fecha_limite=hoy + timedelta(days=7),
            fecha_devolucion=hoy,
        )
        p2 = Prestamo.objects.create(
            ejemplar=self.ejemplar,
            estudiante=self.est2,
            fecha_limite=hoy + timedelta(days=14),
        )
        self.assertFalse(p1.esta_activo)
        self.assertTrue(p2.esta_activo)

    def test_protect_impide_borrar_estudiante_con_prestamos(self):
        Prestamo.objects.create(
            ejemplar=self.ejemplar,
            estudiante=self.est1,
            fecha_limite=timezone.localdate() + timedelta(days=7),
        )
        with self.assertRaises(ProtectedError):
            self.est1.delete()

    def test_borrar_autor_no_borra_sus_libros(self):
        self.autor.delete()
        self.assertTrue(Libro.objects.filter(pk=self.libro.pk).exists())
        self.assertEqual(self.libro.autores.count(), 0)


class BibliotecaConsultasYOptimizacionTests(TestCase):
    def setUp(self):
        call_command("cargar_datos")

    def test_select_related_reduce_consultas_a_una(self):
        with CaptureQueriesContext(connection) as sin_opt:
            for p in Prestamo.objects.all():
                _ = (p.estudiante.nombre, p.ejemplar.libro.titulo)

        with CaptureQueriesContext(connection) as con_opt:
            for p in Prestamo.objects.select_related("estudiante", "ejemplar__libro"):
                _ = (p.estudiante.nombre, p.ejemplar.libro.titulo)

        self.assertGreater(len(sin_opt), len(con_opt))
        self.assertEqual(len(con_opt), 1)

    def test_prefetch_related_reduce_consultas_a_dos(self):
        with CaptureQueriesContext(connection) as sin_opt:
            for libro in Libro.objects.all():
                _ = [a.nombre for a in libro.autores.all()]

        with CaptureQueriesContext(connection) as con_opt:
            for libro in Libro.objects.prefetch_related("autores"):
                _ = [a.nombre for a in libro.autores.all()]

        self.assertGreater(len(sin_opt), len(con_opt))
        self.assertEqual(len(con_opt), 2)

    def test_libro_mas_prestado_y_estudiantes_sin_prestamo(self):
        mas_prestado = (
            Libro.objects.annotate(total_prestamos=Count("ejemplares__prestamos"))
            .order_by("-total_prestamos")
            .first()
        )
        self.assertEqual(mas_prestado.titulo, "Clean Code")
        self.assertEqual(mas_prestado.total_prestamos, 3)

        sin_prestamo = list(
            Estudiante.objects.filter(prestamos__isnull=True).values_list(
                "nombre", flat=True
            )
        )
        self.assertEqual(sin_prestamo, ["Valentina Torres"])

    def test_copias_disponibles_y_estudiantes_con_prestamo_activo(self):
        prestamos_activos = Prestamo.objects.filter(fecha_devolucion__isnull=True)
        disponibles = set(
            Ejemplar.objects.exclude(
                pk__in=prestamos_activos.values("ejemplar_id")
            ).values_list("codigo_inventario", flat=True)
        )
        self.assertEqual(disponibles, {"LIB-002", "LIB-003", "LIB-005", "LIB-006", "LIB-009"})

        estudiantes_activos = set(
            Estudiante.objects.filter(
                prestamos__isnull=False,
                prestamos__fecha_devolucion__isnull=True,
            )
            .distinct()
            .values_list("nombre", flat=True)
        )
        self.assertEqual(
            estudiantes_activos,
            {"Laura Martínez", "Carlos Ramírez", "Andrés López"},
        )
        self.assertNotIn("Valentina Torres", estudiantes_activos)
        self.assertNotIn("Sofía Gómez", estudiantes_activos)


class BibliotecaAdminTests(TestCase):
    def setUp(self):
        call_command("cargar_datos")
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            username="admin_test",
            email="admin@ufps.edu.co",
            password="test-password-1234",
        )
        self.client.force_login(self.admin_user)

    def test_changelist_todos_los_modelos_responden_200(self):
        modelos = ["categoria", "autor", "libro", "ejemplar", "estudiante", "prestamo"]
        for modelo in modelos:
            url = reverse(f"admin:biblioteca_{modelo}_changelist")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Falló changelist de {modelo}")

    def test_filtros_personalizados_admin(self):
        url_prestamos = reverse("admin:biblioteca_prestamo_changelist")
        for estado in ["activo", "devuelto", "vencido"]:
            resp = self.client.get(url_prestamos, {"estado": estado})
            self.assertEqual(resp.status_code, 200)

        url_estudiantes = reverse("admin:biblioteca_estudiante_changelist")
        resp_si = self.client.get(url_estudiantes, {"con_prestamo_activo": "si"})
        self.assertEqual(resp_si.status_code, 200)
        self.assertContains(resp_si, "Laura Martínez")
        self.assertNotContains(resp_si, "Valentina Torres")

    def test_accion_marcar_como_devueltos(self):
        activos = list(Prestamo.objects.filter(fecha_devolucion__isnull=True))
        self.assertGreater(len(activos), 0)
        url = reverse("admin:biblioteca_prestamo_changelist")
        response = self.client.post(
            url,
            {
                "action": "marcar_como_devueltos",
                "_selected_action": [str(p.pk) for p in activos],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Prestamo.objects.filter(fecha_devolucion__isnull=True).count(),
            0,
        )

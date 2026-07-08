from django.urls import include, path
from rest_framework.routers import DefaultRouter

from gestao.views import (
    AnexoViewSet,
    CategoriaDocumentoViewSet,
    DashboardViewSet,
    DiligenciaViewSet,
    ExecutarJobCobrancaView,
    ProcessoViewSet,
)

router = DefaultRouter()
router.register("processos",   ProcessoViewSet,          basename="processo")
router.register("diligencias", DiligenciaViewSet,        basename="diligencia")
router.register("anexos",      AnexoViewSet,             basename="anexo")
router.register("categorias",  CategoriaDocumentoViewSet, basename="categorias")
router.register("dashboard",   DashboardViewSet,         basename="dashboard")

urlpatterns = [
    path("", include(router.urls)),
    path("internal/jobs/cobranca-atrasos/", ExecutarJobCobrancaView.as_view(), name="job-cobranca-atrasos"),
]

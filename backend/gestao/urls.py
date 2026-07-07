from django.urls import include, path
from rest_framework.routers import DefaultRouter

from gestao.views import AnexoViewSet, CategoriaDocumentoViewSet, DiligenciaViewSet, ProcessoViewSet

router = DefaultRouter()
router.register("processos",   ProcessoViewSet,          basename="processo")
router.register("diligencias", DiligenciaViewSet,        basename="diligencia")
router.register("anexos",      AnexoViewSet,             basename="anexo")
router.register("categorias",  CategoriaDocumentoViewSet, basename="categorias")

urlpatterns = [
    path("", include(router.urls)),
]

from rest_framework.routers import DefaultRouter

from cadastros.views import NivelPrioridadeViewSet, RemetenteViewSet, TipoDocumentoViewSet

router = DefaultRouter()
router.register("remetentes",        RemetenteViewSet,        basename="remetente")
router.register("tipos-documento",   TipoDocumentoViewSet,    basename="tipo-documento")
router.register("niveis-prioridade", NivelPrioridadeViewSet,  basename="nivel-prioridade")

urlpatterns = router.urls

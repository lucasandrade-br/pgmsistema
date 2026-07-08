"""
URL configuration for core_api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from gestao.views import LinkPublicoViewSet

urlpatterns = [
    path("admin/", admin.site.urls),
    # Autenticação JWT — /api/v1/auth/token/ e /api/v1/auth/token/refresh/
    path("api/v1/auth/",      include("core.urls")),
    # Dados de referência — /api/v1/cadastros/remetentes/, /tipos-documento/, etc.
    path("api/v1/cadastros/", include("cadastros.urls")),
    # Gestão de Processos — /api/v1/gestao/processos/
    path("api/v1/gestao/",    include("gestao.urls")),
    # Endpoint público de compartilhamento — sem autenticação
    path(
        "api/v1/publico/link/<uuid:token>/",
        LinkPublicoViewSet.as_view({"get": "retrieve"}),
        name="link-publico",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

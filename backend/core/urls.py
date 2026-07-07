from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from core.views import (
    CustomTokenObtainPairView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ProcuradoresListView,
)

urlpatterns = [
    # POST /api/v1/auth/token/         → obtém access + refresh token
    path("token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    # POST /api/v1/auth/token/refresh/ → renova o access token via refresh token
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # ── Redefinição de senha (fluxo público, sem autenticação) ────────────────
    # POST /api/v1/auth/password-reset/request/  → solicita o link por e-mail
    path(
        "password-reset/request/",
        PasswordResetRequestView.as_view(),
        name="password_reset_request",
    ),
    # POST /api/v1/auth/password-reset/confirm/  → confirma com token + nova senha
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),

    # ── Recursos de apoio ao front-end ──────────────────────────────────────────────
    # GET  /api/v1/auth/procuradores/  → lista de usuários do grupo Procuradores
    path("procuradores/", ProcuradoresListView.as_view(), name="procuradores_list"),
]

from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.contrib.auth import get_user_model
from django.db.models import F, Max

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView as _BaseTokenObtainPairView

from core.services.auth_service import TokenInvalidoError, confirm_password_reset, request_password_reset


# ── JWT com claim de grupos ────────────────────────────────────────────────────

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adiciona o claim 'grupos' ao JWT para RBAC no frontend.

    Suporta login tanto por nome de usuário quanto por e-mail: se o
    campo identificador contiver '@', resolve o e-mail para o username
    correspondente antes de delegar a autenticação ao pipeline do
    simplejwt — a verificação de senha permanece integralmente no Django.
    """

    def validate(self, attrs):
        identifier = attrs.get(self.username_field, '')
        if '@' in identifier:
            User = get_user_model()
            try:
                user = User.objects.get(email__iexact=identifier)
                attrs[self.username_field] = user.username
            except User.DoesNotExist:
                pass  # Deixa o pipeline retornar credenciais inválidas normalmente
        return super().validate(attrs)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["grupos"]   = list(user.groups.values_list("name", flat=True))
        return token


class CustomTokenObtainPairView(_BaseTokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


# ── Serializers ──────────────────────────────────────────────────────────────

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

# ── Listagem de Procuradores ──────────────────────────────────────────────────

class ProcuradoresListView(APIView):
    """
    GET /api/v1/auth/procuradores/

    Retorna a lista de usuários ativos do grupo 'Procuradores',
    utilizada pelo front-end na tela de Distribuição em Lote.

    Resposta:
        [{"id": 2, "nome": "Carlos Andrade", "username": "c.andrade"}, ...]
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        User = get_user_model()
        qs = (
            User.objects
            .filter(groups__name="Procuradores", is_active=True)
            .annotate(ultima_atribuicao=Max('processos_atribuidos__data_atribuicao'))
            .order_by(F('ultima_atribuicao').asc(nulls_first=True))
        )
        data = [
            {
                "id":       u.id,
                "nome":     u.get_full_name() or u.username,
                "username": u.username,
            }
            for u in qs
        ]
        return Response(data)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    new_password = serializers.CharField(min_length=8, write_only=True)


# ── Views ────────────────────────────────────────────────────────────────────

class PasswordResetRequestView(APIView):
    """
    POST /api/v1/auth/password-reset/request/

    Inicia o fluxo de redefinição de senha.

    Proteção anti-enumeração: independentemente de o e-mail existir ou não
    na base, sempre retorna HTTP 200 com a MESMA mensagem genérica.
    O atacante não consegue distinguir os dois cenários pela resposta.
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # Endpoint público — sem autenticação JWT

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # O serviço retorna None silenciosamente se o e-mail não existir.
        # A view não diferencia os dois casos na resposta.
        request_password_reset(email=serializer.validated_data["email"])

        return Response(
            {"detail": "Se o e-mail constar em nossa base, você receberá um link em breve."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    """
    POST /api/v1/auth/password-reset/confirm/

    Confirma a redefinição de senha com o token recebido por e-mail.

    Retorna:
        200 OK  — senha alterada com sucesso.
        400 Bad Request — token inválido, expirado ou já utilizado.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            confirm_password_reset(
                token_str=str(serializer.validated_data["token"]),
                new_password=serializer.validated_data["new_password"],
            )
        except TokenInvalidoError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Senha redefinida com sucesso."},
            status=status.HTTP_200_OK,
        )

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


GRUPOS_DO_SISTEMA = [
    "Protocolador-Chefe",
    "Procurador-Chefe",
    "Procuradores",
    "Procurador-Analista",
    "Protocolo",
    "Cadastrante",
]


class Command(BaseCommand):
    help = "Cria os grupos (roles) padrão do sistema PGM no banco de dados."

    def handle(self, *args, **options):
        criados = []
        existentes = []

        for nome in GRUPOS_DO_SISTEMA:
            grupo, created = Group.objects.get_or_create(name=nome)
            if created:
                criados.append(nome)
            else:
                existentes.append(nome)

        if criados:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Grupos criados ({len(criados)}): {', '.join(criados)}"
                )
            )

        if existentes:
            self.stdout.write(
                self.style.WARNING(
                    f"Grupos já existentes ({len(existentes)}): {', '.join(existentes)}"
                )
            )

        self.stdout.write(self.style.SUCCESS("setup_roles concluído com sucesso."))

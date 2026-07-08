from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0008_link_compartilhamento"),
    ]

    operations = [
        migrations.AddField(
            model_name="processo",
            name="data_resposta_procurador",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Data da Resposta do Procurador",
            ),
        ),
    ]

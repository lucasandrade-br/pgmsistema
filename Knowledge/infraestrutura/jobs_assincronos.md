Este documento estabelece o padrão para processamento em background (assíncrono) no sistema da PGM. O objetivo principal é remover tarefas pesadas, como envio de e-mails e geração de links com TTL, do ciclo de requisição e resposta (Request/Response) da API principal.



###### **1. Ferramenta Escolhida: Google Cloud Tasks**

Para manter a arquitetura serverless e otimizar custos no Google Cloud Run, utilizaremos o Google Cloud Tasks em substituição a ferramentas tradicionais de fila como Celery + Redis.

Vantagens: Não exige manutenção de workers dedicados. O Cloud Tasks gerencia a fila, as tentativas (retries) com backoff exponencial e a taxa de disparo (rate limits).



###### **2. Arquitetura do Fluxo Assíncrono**

O processamento ocorrerá através de Webhooks internos. O fluxo funcionará da seguinte maneira:

* **Geração da Tarefa:** O Serviço (notificacao\_service.py) não envia o e-mail diretamente. Ele monta o payload (com os IDs do documento, remetente e anexos) e cria uma tarefa na fila do Cloud Tasks.
* **Resposta Rápida:** O Serviço finaliza a operação no banco de dados e a View retorna imediatamente um 200 OK ou 201 Created para o Vue.js. O usuário é liberado da tela de carregamento.
* **Execução:** O Cloud Tasks enfileira a requisição e faz uma chamada HTTP POST para um endpoint interno e oculto da nossa própria API Django (ex: POST /api/v1/internal/tasks/enviar\_email\_finalizacao/).
* **Processamento Real:** A nossa API recebe a requisição do Cloud Tasks, executa o envio no servidor SMTP via email\_utils.py e, se ocorrer tudo bem, devolve um 200 OK.
* **Tratamento de Falhas:** Se o servidor SMTP do município falhar, nossa API retorna um 500. O Cloud Tasks percebe a falha e tentará novamente em alguns minutos, de forma automática.



###### **3. Segurança dos Endpoints Internos**

Para evitar que qualquer pessoa dispare esses endpoints de tarefas assíncronas na internet pública:

Os endpoints sob /api/v1/internal/tasks/ não exigirão o JWT do usuário (pois quem os chama é o servidor do Google), mas exigirão autenticação via OIDC (OpenID Connect).

Apenas a conta de serviço (Service Account) do Google Cloud Tasks terá permissão no IAM para invocar essas rotas no Cloud Run.



###### **4. Casos de Uso Obrigatórios**

Todas as funcionalidades abaixo devem obrigatoriamente ser implementadas como tarefas assíncronas:

Disparo de e-mail de "Confirmação de Protocolo" ao remetente.

Disparo de e-mail ao Procurador informando "Documento Distribuído".

Envio de e-mail da etapa "Em Diligência" (com anexos ou geração de AnexoShareToken).

Envio de e-mail ao remetente na etapa "Finalizado".


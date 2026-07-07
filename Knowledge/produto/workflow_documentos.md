Este documento centraliza as regras de negócio referentes à máquina de estados do processo principal (Documento) e as permissões de transição.



###### **1. Ciclo de Vida do Documento**

Sistema gerencia o fluxo através de 7 etapas principais e 1 estado paralelo de rejeição.



* **Etapa 1:** Aguardando Distribuição: A entrada ocorre na criação de um novo protocolo. A ação de protocolar exige ao menos um anexo do tipo INICIAL. É enviado automaticamente um e-mail de confirmação ao remetente, caso ele possua e-mail cadastrado.
* **Etapa 2:** Em Análise: A entrada ocorre por distribuição manual ou automática (round-robin) por um chefe. O sistema calcula automaticamente a data limite somando a data de atribuição ao prazo em dias da prioridade. Na distribuição automática, o sistema prioriza o procurador com a data de atribuição menos recente. O procurador recebe um e-mail de notificação com o documento inicial em anexo.
* **Etapa 3:** Em Diligência: A entrada ocorre quando um procurador abre uma solicitação de documentos faltantes. O procurador descreve o que falta e pode incluir um documento de diligência. Uma entidade SolicitacaoDocumento é gerada com o status Pendente. O documento sai da fila do procurador atribuído.  
* **Etapa 4:** Análise Concluída: A entrada ocorre quando o procurador encerra a análise. É obrigatório possuir ao menos um anexo do tipo RESPOSTA ativo. É obrigatório não possuir nenhuma diligência em aberto (status Pendente ou Enviada).  
* **Etapa 5:** Aguardando Confirmação: A entrada ocorre quando a chefia envia a análise concluída para revisão. O processo fica em uma fila dedicada, visível apenas para o Procurador-Analista e o Procurador-Chefe. As pré-condições exigem ao menos um anexo do tipo RESPOSTA e nenhuma diligência em aberto.
* **Etapa 6:** Finalizado: A entrada pode ocorrer via confirmação normal, finalização direta (pulando fila), ou arquivamento direto pelo Protocolador-Chefe. A ação dispara um e-mail de resposta ao remetente e interessados. Anexos grandes são enviados como links seguros com validade de 168 horas em vez de anexos diretos no e-mail.
* **Etapa 7:** Arquivado: A entrada ocorre por uma ação de arquivar com motivo. Toda ação de arquivamento gera registros no histórico de edição para o status e para o motivo. Esta é uma ação de força bruta, disponível a qualquer momento, exceto se o documento já estiver Finalizado ou Arquivado.
* **Estado Paralelo (Rejeitado):** A entrada ocorre ao rejeitar uma análise concluída. O sistema dispara um e-mail de devolução contendo o motivo ao procurador. O processo retorna ao controle do procurador atribuído para revisão.



###### **2. Matriz de Autorização (RBAC) e Validação de Segurança**

Ações críticas no sistema exigem grupos específicos de usuários e, em alguns casos, validação por PIN criptografado.



|Ação|Grupos Autorizados|Exige PIN?|
|-|-|-|
|Criar Protocolo|Protocolador-Chefe, Protocolo, Cadastrante, superuser|Não|
|Distribuir Processo|Protocolador-Chefe, Protocolo, Procurador-Chefe, superuser|Não|
|Abrir Diligência|Procuradores, Procurador-Analista (apenas o atribuído)|Não|
|Concluir Análise|Procuradores, Procurador-Analista (apenas o atribuído)|Não|
|Enviar p/ Confirmação|Protocolador-Chefe, Protocolo, Procurador-Chefe, superuser|Não|
|Finalizar / Confirmar|Procurador-Analista, Procurador-Chefe|Sim|
|Arquivar (Força Bruta)|Protocolador-Chefe, superuser|Sim|
|Rejeitar Análise|Procurador-Analista, Procurador-Chefe|Sim|



###### **3. Comunicação Externa**

A interface com o mundo externo ocorre estritamente via e-mail unidirecional. O sistema apresenta a seguinte mecânica para diligências:



* **Envio:** O sistema gera um e-mail via SMTP contendo um texto explicativo e os arquivos em anexo, respeitando os limites de MB configurados. Caso os arquivos ultrapassem o limite, são gerados links de download seguros AnexoShareToken.  
* **Retorno:** O cidadão recebe os links via e-mail exclusivamente para download. A resposta do cidadão ocorre fora do sistema (e-mail convencional ou atendimento presencial).
* **Conclusão Manual:** A chefia ou o cadastrante recebe a documentação externa e faz o upload manual no sistema. O tipo do anexo inserido é marcado como DILIGENCIA, o status da solicitação muda para Atendida, e o documento principal retorna para Em Análise. O procurador atribuído é então notificado por e-mail.


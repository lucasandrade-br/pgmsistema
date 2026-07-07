Este documento define as regras de negócio, a estrutura de dados e o comportamento da interface para o módulo de Diligências (SolicitacaoDocumento), abrangendo desde a criação em lote até o gerenciamento unificado pela chefia.



###### **1. Ajustes no Modelo de Dados (Backend)**

Para suportar a rastreabilidade e a movimentação em lote, o banco de dados passará pelas seguintes adequações via migrations:

Isolamento de Justificativas: Criação do campo motivo\_rejeicao para separar semanticamente as rejeições das notas de saneamento manual (que continuarão no campo observacao\_chefia).

Controle de SLA: Adição do campo data\_envio\_email para registrar o disparo externo. O campo existente data\_resposta será tratado estritamente como a data de conclusão da diligência.

Atomicidade: Todo lote de anexos e notas gerado pelo Procurador será salvo via transaction.atomic(), garantindo que não existam registros órfãos. Notas de texto puro utilizarão o campo descricao do model Anexo, tornando o upload de PDF opcional nesses casos.



###### **2. A Interface de Gerenciamento (O Componente Unificado)**

As ações da chefia não estarão acopladas à tela de detalhes do processo. Elas viverão no componente global <DiligenciaActionModal>, que será instanciado tanto na Timeline do processo quanto na tela global de "Diligências Pendentes".

Gatilhos de Abertura:

Contexto Local: Clique direto sobre o nó principal da diligência na Timeline esquerda do DetalheProcesso.vue.

Contexto Global: Clique no botão "Gerenciar" na tabela da tela de listagem de todas as pendências do sistema.

Comportamento do <DiligenciaActionModal>:O modal apresentará os dados da solicitação (descricao\_necessidade) e a lista de arquivos preparados. A chefia terá os seguintes poderes e controles:

Edição e Seleção: A chefia pode editar os metadados dos arquivos enviados pelo procurador e utilizar checkboxes para definir exatamente quais arquivos serão incluídos no e-mail externo.

Ação - Enviar E-mail: Dispara o Cloud Tasks para envio. O status muda para 'Enviada' e o nó da timeline é atualizado.

Ação - Rejeitar: Exige o preenchimento obrigatório do campo motivo\_rejeicao. O status muda para 'Rejeitada' e o processo retorna à fila de análise.

Ação - Concluir Manualmente: Aciona o fluxo de upload de arquivos (a resposta recebida fisicamente/por fora). O status muda para 'Atendida'.



###### **3. O Ciclo de Vida na Timeline**

A diligência não é um evento estático, ela gera movimentações progressivas na linha do tempo:

Abertura: Gera o nó "Diligência Iniciada" (Amarelo). Os arquivos e notas produzidos pelo procurador são renderizados logo abaixo deste nó. Clicar em um arquivo o exibe no <ProcessViewer> à direita.

Fechamento: A ação de "Concluir Manualmente" não altera apenas o nó inicial; ela injeta um novo nó na Timeline ("Diligência Solucionada" - Azul/Verde) no topo da ordem cronológica, contendo os arquivos de resposta anexados pela chefia.


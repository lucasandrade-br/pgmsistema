Este documento detalha o motor unificado de distribuição em lote (Bulk Distribution), que substitui os fluxos paralelos (manual vs. automático) do sistema legado.



###### **1. Proposta de Valor e UI**

Na listagem da etapa "Aguardando Distribuição", a chefia poderá selecionar N processos via checkboxes e, simultaneamente, abrir um painel lateral onde seleciona M procuradores disponíveis para aquele dia. A interface enviará um único comando aglutinado para a API.



###### **2. Contrato da API**

Endpoint: POST /api/v1/processos/distribuir-lote/

Payload Esperado:

{

&#x20; "processos\_ids": \[145, 146, 147, 148],

&#x20; "procuradores\_ids": \[2, 5, 8]

}



###### **3. Lógica do Motor na Camada de Serviço**

A Camada de Serviço (distribuicao\_service.py) deve iterar sobre a lista de processos e distribuir a carga de forma igualitária (Round-Robin) apenas entre os procuradores selecionados. Para cada processo, o serviço deve obrigatoriamente:



Atribuição: Vincular o procurador\_atribuido (FK).

Transição de Status: Alterar o status para "Em Análise".

Timestamp Preciso: Salvar o timezone.now() no campo data\_atribuicao.

Cálculo de Prazo: Somar a quantidade de dias cadastrada na prioridade à data atual e persistir no campo data\_limite.

Limpeza de Histórico: Setar motivo\_ultima\_devolucao e usuario\_ultima\_devolucao como null, zerando resquícios de ciclos anteriores.

Atomicidade: Todo o bloco do lote deve rodar sob transaction.atomic(). Se um processo falhar ao ser salvo, a distribuição inteira deve sofrer rollback.


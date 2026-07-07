Este documento oficializa as adequações de Linguagem Ubíqua (Domain-Driven Design) para o sistema, alinhando os termos técnicos do código com o vocabulário real utilizado pelos procuradores e chefia no dia a dia da PGM.



###### **1. De "Documento" para "Processo"**

No sistema legado, a entidade principal foi nomeada como Documento. No entanto, na realidade do negócio, a PGM analisa Processos (ou Expedientes), que por sua vez contêm vários documentos (Anexos). Essa desconexão cognitiva gera confusão no desenvolvimento.



Frontend e UI: Todas as telas, tabelas, menus e mensagens de sucesso/erro devem utilizar a palavra "Processo". O termo "Documento" será restrito estritamente aos arquivos anexados (Iniciais, Respostas, Diligências).



API RESTful: As rotas principais serão refatoradas para refletir o domínio:



✅ GET /api/v1/processos/



❌ GET /api/v1/documentos/



Banco de Dados (Estratégia Transicional): Para evitar uma migração de altíssimo risco e fricção na base MySQL de produção imediata, a tabela física gestao\_documento e o model Django Documento manterão seus nomes originais temporariamente. A camada de Serviço (Service Layer) e os Serializers/Schemas farão a tradução dos campos (ex: mapeando Documento para Processo nas respostas JSON).


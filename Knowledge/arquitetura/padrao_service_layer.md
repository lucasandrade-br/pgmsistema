Este documento define a arquitetura de Camada de Serviço (Service Layer) que deverá ser estritamente seguida na refatoração do backend em Django. O objetivo é desacoplar a regra de negócio das Views, permitindo reusabilidade, facilidade de testes e escalabilidade.



###### **1. Princípios de Responsabilidade**

Para garantir a organização e a manutenibilidade do código, as responsabilidades devem ser isoladas nas seguintes camadas:



* **Views / Endpoints (API):** Responsáveis exclusivamente por receber a requisição HTTP, validar o payload de entrada (via Serializers/Schemas), chamar o serviço correspondente e retornar a resposta HTTP adequada (ex: 200 OK, 400 Bad Request). Regra de ouro: Nenhuma View pode conter regras condicionais de negócio (ex: if documento.status == ...).
* **Services (Camada de Serviço):** Responsáveis por orquestrar a lógica de negócio. É aqui que validamos permissões complexas (ex: checagem do PIN criptografado), alteramos estados de workflow e disparamos eventos (ex: enfileirar e-mails).
* **Models:** Responsáveis exclusivamente pela integridade dos dados, relacionamentos e lógicas intrínsecas ao banco de dados (ex: geração automática do número de protocolo no método .save()).
* **Selectors (Opcional, mas recomendado):** Funções ou métodos estáticos responsáveis por consultas complexas ao banco de dados, isolando as queries pesadas do ORM fora das Views e Services.



###### **2. Estrutura de Diretórios**

As regras de negócio serão agrupadas por domínio (app) dentro de um diretório services/. Exemplo de estrutura no app central gestao:

gestao/

├── models.py

├── views.py (ou api.py)

├── services/

│   ├── \_\_init\_\_.py

│   ├── documento\_service.py     # Transições de workflow (distribuir, concluir, arquivar)

│   ├── anexo\_service.py         # Lógica de numeração e validação de arquivos

│   └── notificacao\_service.py   # Orquestração de e-mails e links de compartilhamento



###### **3. Diretrizes de Implementação dos Services**

* **Injeção de Dependências:** Sempre que possível, passe as instâncias dos objetos para o serviço em vez de fazer o serviço buscar no banco. Isso facilita a criação de testes unitários simulados (Mocks).
* **Tratamento de Exceções:** Os serviços devem levantar exceções customizadas (ex: WorkflowTransitionError, InvalidPINError) quando uma regra de negócio for violada. A View irá capturar essa exceção e convertê-la em um erro HTTP 400 ou 403 apropriado.
* **Transações de Banco de Dados:** Ações que modificam múltiplas tabelas (ex: Arquivar um documento altera o status em Documento e cria um registro em HistoricoEdicao) devem ser obrigatoriamente encapsuladas em um bloco transaction.atomic() dentro do serviço, garantindo o rollback em caso de falha.


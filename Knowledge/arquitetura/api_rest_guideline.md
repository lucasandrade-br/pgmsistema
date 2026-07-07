Este documento estabelece as diretrizes, padrões e convenções para a construção da API RESTful do sistema da PGM. Todos os endpoints desenvolvidos no backend (Django) e consumidos pelo frontend (Vue.js) devem seguir estritamente este contrato.



###### **1. Nomenclatura de Rotas (Endpoints)**

Use substantivos no plural, nunca verbos: A URL deve representar o recurso, e o método HTTP deve representar a ação.



✅ Correto: GET /api/v1/documentos/

❌ Incorreto: GET /api/v1/get\_documentos/ ou POST /api/v1/criar\_diligencia/



Hierarquia lógica: Sub-recursos devem estar aninhados caso dependam exclusivamente do recurso pai.

✅ GET /api/v1/documentos/{id}/anexos/ (Lista os anexos de um documento específico).



Versionamento: Todas as rotas devem obrigatoriamente estar sob o prefixo de versão /api/v1/.



###### **2. Métodos HTTP e Suas Responsabilidades**

* GET: Recuperar dados (listagem ou detalhe). Nunca altera o estado do banco.
* POST: Criar um novo recurso (ex: Protocolar um novo Documento).
* PUT: Atualizar um recurso inteiro.
* PATCH: Atualização parcial ou alteração de estado do workflow. (ex: Mudar o status de um documento para "Em Diligência").
* DELETE: Remoção lógica ou física (ex: Excluir um anexo antes de finalizar o processo).



###### **3. Padrão de Respostas JSON (Payload)**

Para facilitar a interceptação no Vue.js (ex: usando Axios), todas as respostas devem seguir uma estrutura previsível.



Sucesso (Listagem com Paginação):

{

&#x20; "count": 145,

&#x20; "next": "https://.../api/v1/documentos/?page=2",

&#x20; "previous": null,

&#x20; "results": \[ ... ]

}



Erro (Validações de Regra de Negócio ou Formulário):

Os erros devem retornar sempre no formato de lista por campo, para que o frontend saiba exatamente onde renderizar a mensagem em vermelho.

{

&#x20; "error\_code": "VALIDATION\_FAILED",

&#x20; "message": "A requisição contém dados inválidos.",

&#x20; "details": {

&#x20;   "anexos": \["É obrigatório ao menos 1 anexo do tipo INICIAL para protocolar."],

&#x20;   "pin": \["PIN de autorização inválido."]

&#x20; }

}



###### **4. Códigos de Status HTTP Obrigatórios**

* **200 OK:** Sucesso para GET, PUT, PATCH ou DELETE.
* **201 Created:** Sucesso exclusivo para POST (recurso criado).
* **400 Bad Request:** Falha de validação de dados ou quebra de regra de negócio (ex: tentar concluir análise com diligência pendente).
* **401 Unauthorized:** Usuário não está logado ou o token JWT expirou.
* **403 Forbidden:** Usuário logado, mas não tem permissão no grupo (RBAC) para aquela ação específica.
* **404 Not Found:** Recurso (ID) não encontrado.
* **500 Internal Server Error:** Erro não tratado no servidor. O frontend deve exibir uma mensagem genérica de "Erro sistêmico".



###### **5. Autenticação e Validação de PIN**

**Autenticação Padrão:** A API será protegida por tokens JWT (JSON Web Tokens) trafegados no header Authorization: Bearer <token>. O Vue.js armazenará este token localmente.

**Ações Críticas (Exigência de PIN):** Para endpoints que finalizam, confirmam ou arquivam processos, o payload (corpo da requisição) deve obrigatoriamente conter um campo "pin\_autorizacao". A Camada de Serviço (Service Layer) validará este PIN contra o hash criptografado no modelo Profile antes de processar qualquer alteração no banco de dados.


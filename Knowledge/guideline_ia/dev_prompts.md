Este documento contém as diretrizes primárias e os templates de prompts que devem ser utilizados ao interagir com agentes de IA (como GitHub Copilot, Gemini, etc.) durante o desenvolvimento do sistema da PGM. O objetivo é garantir que a IA produza código aderente à nossa arquitetura desacoplada e às nossas regras de negócio.



###### **1. Instrução de Sistema (System Prompt Base)**

Sempre que iniciar uma nova sessão de desenvolvimento ou abrir um novo chat com a IA no repositório, inicie com o seguinte contexto para calibrar o agente:



"Atue como um Engenheiro de Software Sênior. Estamos refatorando um sistema legado em Django para uma arquitetura moderna e desacoplada. O backend será uma API RESTful (Django + DRF/Ninja) e o frontend será em Vue.js 3 (Composition API).

A regra de ouro deste projeto é: Consulte sempre o diretório knowledge/ na raiz do projeto antes de propor qualquer solução. Este diretório é a fonte da verdade para regras de negócio, contratos de API e padrões arquiteturais.

Nunca misture regras de negócio nas Views ou endpoints. Utilize estritamente o padrão de Camada de Serviço (Service Layer). Nunca gere código monolítico (templates HTML renderizados pelo Django)."



###### **2. Restrições e Limites da IA (Anti-Alucinação)**

A IA deve obedecer estritamente às seguintes restrições:



* **Não invente bibliotecas:** O gerenciamento de dependências no backend é restrito ao que está no requirements.txt / pyproject.toml, e no frontend ao package.json. Se precisar de uma biblioteca nova, a IA deve sugerir e aguardar aprovação.
* **Respeite o RBAC:** Ao criar endpoints críticos, a IA deve automaticamente verificar a matriz de permissões no arquivo knowledge/produto/workflow\_documentos.md
* **Segurança do PIN:** Qualquer transição de finalização, arquivamento ou rejeição deve obrigatoriamente exigir a validação do PIN criptografado na Camada de Serviço.
* **Respostas HTTP Padrão:** A IA não pode criar formatos JSON aleatórios para respostas da API. Ela deve seguir a estrutura definida em knowledge/arquitetura/api\_rest\_guidelines.md.



###### **3. Templates de Prompts para o Dia a Dia**

Para manter arquivos enxutos e focados, utilize os seguintes templates ao solicitar a criação de código:



**3.1. Para criar um Novo Serviço (Backend)**

"Com base nas regras definidas em knowledge/produto/workflow_documentos.md e seguindo o padrão de arquitetura de knowledge/arquitetura/padrao_service_layer.md, crie o arquivo documento\service.py no app gestao. Implemente apenas o método concluir\_analise, garantindo o uso de transaction.atomic() e validando se o documento possui ao menos um anexo do tipo RESPOSTA."



**3.2. Para criar um Novo Endpoint / Rota (Backend)**

"Leia o serviço documento\_service.py recém-criado. Agora, crie a View/Endpoint correspondente para a ação de concluir a análise. Siga estritamente as convenções de resposta JSON e status HTTP definidos em knowledge/arquitetura/api\_rest\_guidelines.md. A View não deve conter nenhuma regra de negócio, apenas injetar os dados no serviço e tratar as exceções."



**3.3. Para criar um Componente / View (Frontend em Vue 3)**

"Leia a documentação da nossa stack em knowledge/arquitetura/frontend\_vue\_stack.md e o contrato da API em api\_rest\_guidelines.md. Crie o componente PainelGerencial.vue para o módulo de processos utilizando Vue 3 (Composition API com <script setup>). Este componente deve buscar a lista de documentos aguardando confirmação através da nossa instância global do Axios e renderizar eventuais erros no formato padronizado."


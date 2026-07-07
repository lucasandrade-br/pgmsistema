Este documento estabelece a arquitetura, a estrutura de diretórios e os padrões de desenvolvimento para o frontend em Vue.js (Vue 3). O objetivo é garantir um código modular, modularizado por regras de negócio, facilitando a manutenção e o consumo seguro da API RESTful.



###### **1. Estrutura de Diretórios (Padrão Modular)**

O projeto frontend adotará uma estrutura baseada em módulos de negócio (Screaming Architecture), agrupando componentes, rotas e views de um mesmo domínio sob o mesmo diretório, em vez de separar tudo rigidamente por tipos de arquivos.frontend/

├── public/

├── src/

│   ├── assets/              # Estilos globais (Tailwind/Vuetify) e imagens

│   ├── core/                # Infraestrutura transacional do frontend

│   │   ├── api/             # Configuração do Axios (interceptors de token)

│   │   ├── router/          # Configuração global do Vue Router e Guards

│   │   └── store/           # Stores globais do Pinia (ex: auth.js)

│   ├── components/          # Componentes globais e reutilizáveis (Botões, Modais)

│   ├── modules/             # Módulos encapsulados por domínio de negócio

│   │   ├── dashboard/

│   │   ├── processos/       # CRUD de Documentos, Distribuição e Workflow

│   │   │   ├── components/  # Componentes exclusivos do módulo (ex: CardProcesso.vue)

│   │   │   ├── store/       # Estado local do módulo se necessário

│   │   │   ├── views/       # Telas do módulo (ListaProcessos.vue, DetalheProcesso.vue)

│   │   │   └── routes.js    # Sub-rotas do módulo de processos

│   │   └── diligencias/     # Módulo para gerenciamento de solicitações

│   ├── App.vue

│   └── main.js



###### **2. Gerenciamento de Estado Global (Pinia)**

O Pinia será utilizado estritamente para estados que precisam ser compartilhados entre múltiplos módulos independentes. O principal caso de uso é a authStore.

**Armazenamento de Tokens:** O token JWT retornado pela API será armazenado no estado da store e persistido de forma segura no localStorage ou sessionStorage do navegador.

**Controle de Perfil e Grupos:** A store de autenticação manterá os dados do usuário logado e a lista de grupos de permissão vinculados a ele (ex: Protocolador-Chefe, Procurador-Chefe, Procuradores, Procurador-Analista, Protocolo, Cadastrante) para realizar a renderização condicional de elementos na interface.



###### **3. Roteamento e Guardas de Segurança (Vue Router)**

As rotas do frontend devem refletir fielmente as regras de acesso do sistema. Utilizaremos os metadados das rotas (meta) para definir quais grupos possuem permissão de visualizar cada tela.

**Navigation Guards (beforeEach):** Antes de resolver qualquer transição de rota, o roteador global interceptará a navegação para validar:

Se a rota exige autenticação e se o usuário possui um token válido.

Se o grupo do usuário (extraído da authStore) está incluído no array meta.requiredGroups da rota de destino. Caso o usuário não tenha permissão, ele será redirecionado para uma tela de erro 403 (Acesso Negado).

Exemplo conceitual de configuração de rota protegida:

{

&#x20; path: '/gerencia/painel',

&#x20; component: PanelGerencial.vue,

&#x20; meta: { 

&#x20;   requiresAuth: true, 

&#x20;   requiredGroups: \['Procurador-Chefe', 'Protocolador-Chefe'] 

&#x20; }

}



###### **4. Cliente HTTP (Axios) e Interceptadores**

Toda a comunicação com a API v1 do Django passará por uma instância centralizada do Axios no diretório src/core/api/.



* **Request Interceptor:** Injetará automaticamente o cabeçalho Authorization: Bearer <token> em todas as requisições disparadas pelo frontend, buscando o token ativo diretamente da store de autenticação.
* **Response Interceptor:** Tratará de forma centralizada os erros comuns da API:

  * **Erro 401 (Unauthorized):** Limpará o token expirado da store e redirecionará o usuário imediatamente para a tela de login.
  * **Erro 403 (Forbidden):** Disparará um alerta global de falta de privilégios.
  * **Erro 400 (Bad Request):** Repassará o objeto de validação (details) diretamente para o componente que fez a chamada, permitindo que as mensagens de erro específicas (como validação de formulários ou erro de PIN inválido) sejam exibidas logo abaixo dos campos de input correspondentes na tela.


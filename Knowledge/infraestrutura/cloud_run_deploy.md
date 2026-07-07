Este documento define a estratégia de infraestrutura, conteinerização e CI/CD (Continuous Integration / Continuous Deployment) para o sistema da PGM, utilizando os serviços do Google Cloud Platform (GCP).



###### **1. Estratégia de Conteinerização (Docker)**

O sistema será dividido em dois contêineres distintos, garantindo que o backend e o frontend escalem de forma independente.



**Backend (Django API):** O Dockerfile do backend será focado em instalar as dependências do requirements.txt, rodar as migrações no banco (Cloud SQL) e expor a aplicação utilizando o Gunicorn. O .dockerignore deve excluir rigorosamente arquivos locais, .env e pastas de cache (\_\_pycache\_\_).

**Frontend (Vue.js):** O Dockerfile do frontend utilizará um modelo multi-stage build. A primeira etapa rodará o Node.js para compilar o código (npm run build). A segunda etapa usará um servidor Nginx super leve apenas para servir os arquivos estáticos gerados, garantindo alta performance.



###### **2. Pipeline de CI/CD (GitHub Actions)**

Nenhum deploy será feito manualmente a partir da máquina do desenvolvedor. Utilizaremos o GitHub Actions para automatizar o fluxo:



**Gatilho:** Quando um Pull Request for aprovado e mergeado na branch main.

**Build:** O pipeline fará o build das imagens Docker do backend e do frontend.

**Push:** As imagens serão enviadas para o Google Artifact Registry.

**Deploy:** O pipeline atualizará as revisões dos serviços no Google Cloud Run, apontando para a nova imagem.



###### **3. Topologia no Google Cloud Run**

Teremos dois serviços rodando no Cloud Run:



**pgm-api-service:** Rodando o backend (Django). Variáveis de ambiente sensíveis (credenciais de banco, chaves de API, segredos JWT) serão injetadas via Google Secret Manager.

**pgm-frontend-service:** Rodando o Nginx com os estáticos do Vue.js.



###### **4. Roteamento e Domínios Personalizados**

Devido às limitações de mapeamento direto de domínio em determinadas regiões do GCP (ex: southamerica-east1 - São Paulo), a arquitetura de borda utilizará o Firebase Hosting como proxy reverso e gerenciador de certificados SSL.



**Configuração do firebase.json:** O Firebase Hosting será configurado não para servir estáticos diretamente, mas para fazer o rewrite das rotas.

Requisições para https://sistema.pgmvitoriape.com.br/api/\* serão roteadas para o serviço pgm-api-service no Cloud Run.

Todas as demais requisições para https://sistema.pgmvitoriape.com.br/\* serão roteadas para o pgm-frontend-service.

Isso resolve o problema de redirecionamento para URLs padrão do Google e mantém o usuário sempre sob o domínio oficial da procuradoria.


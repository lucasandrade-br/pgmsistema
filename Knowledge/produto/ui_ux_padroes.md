Este documento estabelece os padrões visuais e a padronização de componentes (Smart Components) do frontend em Vue.js. O objetivo é eliminar código duplicado, garantir consistência visual e centralizar a manutenção da interface.



###### **1. Princípios de Design System Interno**

Nenhuma tela deverá recriar estruturas de interface (HTML/CSS) do zero. O desenvolvimento deve obrigatoriamente consumir os componentes baseizados no diretório src/components/. O visual deve ser limpo, focado em usabilidade e com forte indicação de hierarquia de ações.



###### **2. Componentes Base Obrigatórios**

**2.1. <BaseTable /> (Listagens Universais)**

Todas as listagens do sistema (Processos, Diligências, Remetentes) utilizarão o componente de tabela centralizado.

Funcionalidades Nativas: Paginação remota (integrada ao padrão de retorno da API REST), ordenação por colunas, checkboxes para seleção múltipla e um slot de ações na última coluna.

Padronização: Mensagens de "Nenhum registro encontrado" e loaders (esqueletos de carregamento) devem ser tratados diretamente no componente pai, evitando telas em branco ou quebras de layout.



**2.2. <BaseUploadModal /> (Cadastro de Anexos)**

Substituirá os múltiplos formulários espalhados pelo sistema legado. Será chamado sempre que a ação "Adicionar Documento" for disparada.

Comportamento Visual: Modal flutuante (overlay) bloqueando a tela principal com Drag and Drop (arrastar e soltar).

Campos Obrigatórios (Conforme Modelo da API):

arquivo: Validação estrita de extensão (pdf, jpg, png, etc.) e bloqueio visual caso exceda 30 MB.

tipo\_documento: Campo de seleção (Dropdown) consumindo a listagem de categorias ativas.

numero\_documento: O frontend deve fazer um GET prévio para sugerir o número no formato N/AAAA. O campo deve permitir edição manual pelo usuário antes do envio.



**2.3. <BaseEditAnexoModal /> (Edição de Metadados)**

Componente de interface exclusivo para edição.

Regra de Interface: O campo de upload de arquivo deve ser renderizado, porém com a propriedade disabled=true, deixando claro visualmente para o usuário que o arquivo em si é imutável.

Ações Permitidas: Edição apenas da numeração, tipo e uma chave (Toggle/Switch) para gerenciar a propriedade ativo (Soft Delete).



**2.4. Renderização Condicional de Telas Únicas**

O painel de detalhamento (DetalheProcesso.vue) não terá versões distintas por perfil. A tela será única. Botões de ação como "Distribuir", "Devolver" ou "Finalizar" devem utilizar renderização condicional (v-if) baseada nas permissões presentes na Store do Pinia.


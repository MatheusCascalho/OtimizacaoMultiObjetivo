# Plano de implementação — WORKFLOW_INSTANCE

Plano de tarefas para implementar a especificação em [`README.md`](./README.md). O escopo cobre o fluxo funcional de ponta a ponta para o TSP biobjetivo de tempo e distância, mantendo o catálogo preparado para outros tipos de problema.

## Situação atual

- [x] Especificação funcional, contratos propostos e critérios de aceite documentados.
- [x] Mockup navegável com dados e estados simulados em `mockups/`.
- [x] Modelo TSP biobjetivo e heurística aleatória presentes em `src/`.
- [ ] API, persistência de instâncias, uploads reais, worker assíncrono e notificações ainda não integrados.
- [ ] `compose.yaml` ainda inicia somente o servidor estático do mockup.

## Fase 1 — Fechar decisões e contratos

- [x] Definir contrato CSV compatível com os exemplos: matriz numérica sem cabeçalho, UTF-8/BOM, delimitador vírgula, decimal ponto, diagonal zero e limite de 10 MiB.
- [x] Restringir a primeira versão ao `random-heuristic`, com padrão de 50 amostragens e semente opcional.
- [x] Definir progresso por amostragens e cancelamento cooperativo; descartar amostras parciais ao cancelar.
- [x] Definir v1 local single-user sem autenticação; exigir autenticação/autorização antes de disponibilizar o serviço a outros usuários ou à rede.
- [x] Definir PostgreSQL como banco principal e alinhar o README e a visão do projeto.
- [x] Definir as unidades do TSP v1: horas (`h`) e quilômetros (`km`).
- [x] Documentar contratos propostos para catálogo, upload, instância, execução, resultados e notificações, incluindo erros HTTP padronizados.

**Saída:** propostas validadas e contratos estáveis para orientar API, domínio e interface.

## Fase 2 — Preparar aplicação e ambiente local

- [ ] Definir a estrutura de pacotes da API Flask, serviços de aplicação, domínio, repositórios e adaptadores externos, mantendo domínio independente de Flask/Celery.
- [ ] Adicionar configurações externas e validadas para banco, Redis, armazenamento S3, limites de upload e segredos; não versionar credenciais.
- [ ] Definir retenção e limpeza de uploads/resultados/notificações, validade de uploads temporários e configuração/versão SILO.
- [ ] Implementar migrações versionadas e inicialização repetível do PostgreSQL.
- [ ] Adicionar serviços Flask, worker Celery, Redis, PostgreSQL e armazenamento S3 compatível (SILO) ao Compose, com volumes persistentes e preparação repetível do bucket.
- [ ] Definir verificações de saúde e dependências de inicialização para que API e worker só processem tarefas quando seus serviços necessários estiverem disponíveis.
- [ ] Documentar execução, configuração local e comandos de migração/teste.

**Saída:** ambiente integrado inicializável localmente, sem remover a possibilidade de servir o mockup durante o desenvolvimento.

## Fase 3 — Catálogo, arquivos e criação de instâncias

- [ ] Criar catálogo JSON versionado para `tsp-time-distance`, com objetivos/unidades/direções, papéis dos arquivos, análises, algoritmos e parâmetros disponíveis.
- [ ] Implementar leitura do catálogo e endpoints `GET /problem-types` e `GET /problem-types/{problem_type_id}`.
- [ ] Implementar adaptador de armazenamento S3 e ciclo de vida de uploads temporários, com chaves opacas, checksum SHA-256, metadados e limpeza de objetos órfãos.
- [ ] Implementar validação dos CSVs de tempo e distância: presença, formato, conteúdo numérico finito, matriz quadrada não vazia, dimensões iguais e ordem de nós consistente; retornar arquivo e localização do erro quando possível.
- [ ] Implementar `POST /uploads` com validação síncrona do CSV na v1, incluindo metadados do upload e erros por tamanho/formato/conteúdo.
- [ ] Implementar persistência e endpoints de criação, listagem, consulta e edição permitida de instâncias; validar seleção contra o catálogo e associar somente uploads válidos.
- [ ] Congelar na instância o tipo/versão de catálogo, configuração selecionada, referências dos arquivos e timestamps.

**Saída:** é possível criar e consultar uma instância válida sem depender de dados fictícios ou de arquivos locais compartilhados entre serviços.

## Fase 4 — Análise prévia

- [ ] Implementar geração única do layout de cidades e persistir coordenadas e ordem por instância.
- [ ] Implementar `GET /instances/{instance_id}/analysis/input/matrix` com objetivo, unidade, direção, nós e pesos necessários ao heatmap.
- [ ] Implementar `GET /instances/{instance_id}/analysis/input/graph`, selecionando vizinhos de saída por cidade, excluindo a diagonal e preservando direção em matrizes assimétricas.
- [ ] Limitar vizinhos efetivos a `n - 1` e retornar claramente quantidade solicitada e efetiva; usar 20 como padrão de visualização.
- [ ] Testar matrizes pequenas, assimétricas, parâmetros fora do intervalo e consistência do layout entre consultas.

**Saída:** os dados reais da instância alimentam as análises prévias e obedecem às regras de visualização da especificação.

## Fase 5 — Execução assíncrona e estados

- [ ] Implementar persistência de execuções e transições válidas (`queued`, `running`, `cancel_requested`, `cancelled`, `completed`, `failed`).
- [ ] Implementar `POST /instances/{instance_id}/runs`, `GET /instances/{instance_id}/runs` e `GET /runs/{run_id}`; usar `Idempotency-Key` para evitar execuções duplicadas.
- [ ] Coordenar registro da execução e publicação Celery para evitar tarefa sem registro ou execução presa em `queued`; registrar e comunicar falhas do broker.
- [ ] Implementar worker Celery que carrega os arquivos via adaptador S3, executa serviços de domínio/algoritmo e persiste progresso, resultados e falhas sanitizadas.
- [ ] Implementar `POST /runs/{run_id}/cancel`; manter `cancel_requested` até confirmação do worker e garantir que repetição do pedido seja idempotente.
- [ ] Implementar consulta de estado por polling e definir intervalo progressivo no cliente; não exigir SSE para a primeira integração.
- [ ] Testar reentrega de tarefas, solicitações repetidas, indisponibilidade de broker, falhas do solver e cancelamento durante execução.

**Saída:** otimizações são executadas fora do ciclo HTTP, com estado durável e sem apresentar cancelamento ou conclusão antes de confirmação.

## Fase 6 — Resultados e notificações

- [ ] Persistir soluções, valores dos objetivos, dominância e rota ordenada; guardar versões de catálogo/algoritmo e parâmetros efetivos por execução.
- [ ] Implementar endpoints paginados para resumo e soluções, disponíveis somente após estado `completed`.
- [ ] Implementar consulta de solução e grafo da rota usando apenas seus arcos e o layout persistido da instância.
- [ ] Implementar exportação CSV da rota, com sequência ordenada, identificador da cidade e retorno à origem.
- [ ] Implementar persistência e endpoints de notificações (`GET /notifications`, `PATCH /notifications/{notification_id}`), associadas à instância e à execução.
- [ ] Garantir que execução cancelada ou falha não habilite resultados finais e que os erros do serviço sejam apresentados sem stack traces.
- [ ] Testar paginação, dominância, fidelidade do layout, conteúdo/headers do CSV e acesso prematuro a resultados.

**Saída:** resultados finais reproduzíveis, consultáveis e exportáveis; conclusão gera notificação persistente.

## Fase 7 — Integrar o frontend e concluir o fluxo

- [ ] Substituir dados demonstrativos do mockup por chamadas à API para catálogo, upload, criação e análise prévia, preservando o fluxo e padrões visuais existentes.
- [ ] Ligar estados de envio, validação, criação e recuperação de erros aos contratos reais; impedir submissões duplicadas e preservar campos em falhas recuperáveis.
- [ ] Ligar dashboard a consulta/polling do estado da instância e execução; manter navegação disponível durante o processamento.
- [ ] Implementar solicitação e confirmação visível de cancelamento, sem exibir resultados como concluídos prematuramente.
- [ ] Habilitar análise final somente após conclusão; integrar fronteira de Pareto, tabela de soluções, visualização da rota e download CSV.
- [ ] Integrar centro de notificações com contador de não lidas, marcação como lida e navegação para a instância/execução relacionada.
- [ ] Verificar acessibilidade por teclado e tecnologia assistiva, estados não dependentes somente de cor e uso legível em larguras mobile e desktop.
- [ ] Atualizar a documentação do mockup e do ambiente para distinguir claramente protótipo, serviços reais e limitações restantes.

**Saída:** o usuário conclui o fluxo de ponta a ponta na interface sem depender das simulações locais.

## Fase 8 — Validação de aceite

- [ ] Executar testes unitários de domínio para catálogo, parsing/validação CSV, configuração, grafo e transições de estado.
- [ ] Executar testes de integração da API, PostgreSQL, armazenamento S3 compatível e ciclo Celery/worker.
- [ ] Executar testes de interface para criação, erros, polling, cancelamento, resultados, notificações e exportação.
- [ ] Validar os 12 critérios de aceite da seção **Critérios de aceite** em [`README.md`](./README.md), incluindo teclado, responsividade e consistência das coordenadas.
- [ ] Fazer uma execução local limpa via Compose e confirmar persistência após reiniciar os serviços.
- [ ] Atualizar o README principal e a documentação da feature para refletir o ambiente e as decisões efetivamente implementados.

## Dependências principais

1. A Fase 1 precede decisões de persistência, validação de arquivos e comportamento de execução.
2. A Fase 2 fornece infraestrutura para as Fases 3 a 6.
3. A Fase 3 precede a análise prévia (Fase 4) e execução (Fase 5).
4. A Fase 5 precede resultados e notificações completas (Fase 6).
5. A Fase 7 depende dos contratos e endpoints que integrar; pode avançar em paralelo usando mocks de API após estabilização dos contratos.
6. A Fase 8 valida o conjunto integrado e fecha os critérios de aceite.

# Plano de implementação — WORKFLOW_INSTANCE

Plano de tarefas para implementar a especificação em [`README.md`](./README.md). O escopo cobre o fluxo funcional de ponta a ponta para o TSP biobjetivo de tempo e distância, mantendo o catálogo preparado para outros tipos de problema.

## Situação atual

- [x] Especificação funcional, contratos propostos e critérios de aceite documentados.
- [x] Mockup navegável com dados e estados simulados em `mockups/`.
- [x] Modelo TSP biobjetivo e heurística aleatória presentes em `src/`.
- [x] Scaffold da API Flask, worker Celery, configuração PostgreSQL/S3 e ambiente Compose implementados na Fase 2.
- [ ] Fluxos funcionais de instâncias, uploads, execuções, resultados e notificações ainda não integrados.

## Fase 1 — Fechar decisões e contratos

- [x] Definir contrato CSV compatível com os exemplos: matriz numérica sem cabeçalho, UTF-8/BOM, delimitador vírgula, decimal ponto, diagonal zero e limite de 10 MiB.
- [x] Restringir a primeira versão ao `random-heuristic`, com padrão de 50 amostragens e semente opcional.
- [x] Definir progresso por amostragens e cancelamento cooperativo; descartar amostras parciais ao cancelar.
- [x] Definir v1 local single-user sem autenticação; exigir autenticação/autorização antes de disponibilizar o serviço a outros usuários ou à rede.
- [x] Definir PostgreSQL como banco principal e alinhar o README e a visão do projeto.
- [x] Definir as unidades do TSP v1: horas (`h`) e quilômetros (`km`).
- [x] Documentar contratos propostos para catálogo, upload, instância, execução, resultados e notificações, incluindo erros HTTP padronizados.

**Saída:** propostas validadas e contratos estáveis para orientar API, domínio e interface.

## Estrutura de pacotes aprovada

```text
src/
  api/
    __init__.py              # create_app(), registro de blueprints e composição Flask
    settings.py              # Pydantic Settings e leitura de configuração
    errors.py                # conversão de erros da aplicação para respostas HTTP
    routes/
      problem_types.py       # rotas e DTOs HTTP do catálogo
      uploads.py             # upload e validação de entrada
      instances.py           # criação e consulta de instâncias/análise prévia
      runs.py                # execução, status e cancelamento
      results.py             # soluções, grafos e exportação CSV
      notifications.py       # listagem e leitura de notificações
  workflow_instance/
    domain/                  # entidades e regras de instância, upload, run e notificação
    application/
      use_cases/             # criação, validação, otimização, consulta e cancelamento
      ports/                 # interfaces de repositórios, catálogo, objetos e fila
  infrastructure/
    persistence/postgres/    # modelos SQLAlchemy e implementações dos repositórios
    object_storage/s3/       # adaptador de objetos usando API S3
    catalog/json/            # leitor do catálogo JSON versionado
    task_queue/celery/       # configuração de broker e publicação de tarefas
  worker/
    celery_app.py            # inicialização do worker e composição dos adaptadores
    tasks.py                 # tarefas Celery; delegam aos casos de uso
migrations/                  # revisões Alembic para PostgreSQL
```

Os pacotes atuais `optimization_problems/`, `monoobjective_algorithms/` e `multiobjective_algorithms/` permanecem no lugar. Os casos de uso chamam esses módulos por suas APIs existentes. Dependências seguem uma direção: `api` e `worker` chamam `application`; `application` aplica regras de `domain` e depende de `ports`; `infrastructure` implementa as portas. `domain` não importa Flask, SQLAlchemy, Celery, SDK S3 ou variáveis de ambiente. DTOs HTTP ficam na API; modelos ORM ficam na infraestrutura; nenhum deles é usado como entidade de domínio.

Manter o início simples: um app factory Flask, blueprints por recurso, casos de uso explícitos e adaptadores injetados na composição da API/worker. Não criar camada genérica de serviços ou repositórios sem necessidade. Testes espelham as fronteiras (`tests/api/`, `tests/workflow_instance/`, `tests/infrastructure/`), com banco/armazenamento reais somente nos testes de integração.

## Fase 2 — Preparar aplicação e ambiente local

- [x] Definir a estrutura de pacotes da API Flask, serviços de aplicação, domínio, repositórios e adaptadores externos, mantendo domínio independente de Flask/Celery.
- [x] Escolher Pydantic Settings para configuração validada por ambiente; manter `.env.example` sem valores secretos e não versionar credenciais locais.
- [x] Escolher SQLAlchemy 2 e Alembic para persistência e migrações PostgreSQL.
- [x] Definir uploads temporários sem associação a instância com validade de 1 hora; arquivos de instâncias, resultados e notificações permanecem até exclusão explícita.
- [x] Definir paginação para listas: `limit=50`, máximo 200, `offset=0`.
- [x] Confirmar limite máximo de 10 MiB por arquivo CSV e a imagem/tag SILO recomendada abaixo.
- [x] Definir exclusão de instância em cascata; bloquear exclusão enquanto houver execução ativa e executar limpeza de objetos externos de forma repetível.
- [x] Configurar migrações Alembic versionadas e inicialização automática antes de iniciar a API. A revisão inicial é baseline vazia; migrações das entidades da feature entram junto à persistência da Fase 3.
- [x] Adicionar serviços Flask, worker Celery, Redis, PostgreSQL e SILO ao Compose, com volumes persistentes e inicialização repetível do bucket.
- [x] Definir publicação local do frontend em `127.0.0.1:8080` e da API em `127.0.0.1:5000`; banco, broker, worker e object storage não publicam portas no host.
- [x] Aplicar o limite de bytes por arquivo e expirar uploads temporários não associados após 1 hora.
- [ ] Aplicar limites e paginação nas listas de instâncias, execuções e notificações.
- [x] Definir healthchecks: `pg_isready` para PostgreSQL, `redis-cli ping` para Redis, `GET /minio/health/ready` para SILO (validar com a imagem fixada) e `/health/live`/`/health/ready` na API; API e worker dependem dos serviços necessários.
- [x] Implementar healthchecks e dependências de inicialização no Compose.
- [x] Documentar execução, configuração local e comandos de migração/teste.

**Saída:** ambiente integrado inicializável localmente, sem remover a possibilidade de servir o mockup durante o desenvolvimento.

Pydantic Settings deve validar, no mínimo, `DATABASE_URL`, `CELERY_BROKER_URL`, `S3_ENDPOINT_URL`, bucket, credenciais S3, limite de bytes por upload (10 MiB), expiração (3.600 segundos), paginação (50/200), ambiente e porta. Dentro do container, a API escuta em `0.0.0.0:5000`; o mapeamento do host fica restrito a `127.0.0.1:5000`.

### Recomendação de imagem para armazenamento local

Usar a imagem aprovada `docker.io/pgsty/silo:RELEASE.2026-10-26T00-00-00Z`, fixando uma release em vez de `latest`. O repositório oficial do [PGSTY SILO](https://github.com/pgsty/silo) identifica a imagem e a release como multi-arquitetura `amd64`/`arm64`; o [README oficial](https://github.com/pgsty/silo#quick-start) fornece o comando de execução e as variáveis `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD`. A [documentação de compatibilidade](https://silo.pgsty.com/compatibility/server/) recomenda verificar as diferenças do fork antes de substituir MinIO. Testar `/minio/health/ready` como healthcheck de readiness antes de fixá-la no Compose. A configuração da aplicação ainda deve usar API S3 padrão, sem expor SDKs específicos do SILO ao domínio.

Para desenvolvimento local: endpoint S3 interno `http://silo:9000`, console `9001` não publicada no host, diretório de dados montado em volume persistente, credenciais em `.env` ignorado pelo Git, healthcheck do serviço e tarefa de inicialização idempotente para criar o bucket. A tag foi a release publicada mais recente identificada em 02/11/2026; atualizar a imagem exige revisão da release e reteste do adaptador S3.

## Fase 3 — Catálogo, arquivos e criação de instâncias

- [x] Criar catálogo JSON versionado para `tsp-time-distance`, com objetivos/unidades/direções, papéis dos arquivos, análises, algoritmos e parâmetros disponíveis.
- [x] Implementar leitura do catálogo e endpoints `GET /problem-types` e `GET /problem-types/{problem_type_id}`.
- [x] Implementar adaptador S3 e persistência de uploads temporários com chaves opacas, checksum SHA-256, metadados e remoção após expiração.
- [ ] Implementar reconciliação e limpeza de objetos S3 órfãos.
- [x] Validar cada CSV: formato, conteúdo numérico finito não negativo, matriz quadrada com ao menos dois nós, diagonal zero e localização de erros quando possível.
- [ ] Validar dimensões entre os dois uploads durante a criação da instância e registrar a confirmação da ordem dos nós.
- [x] Implementar `POST /uploads` com validação síncrona do CSV na v1, incluindo metadados do upload e erros por tamanho/formato/conteúdo.
- [ ] Implementar persistência e endpoints de criação, listagem, consulta e edição permitida de instâncias; validar seleção contra o catálogo e associar somente uploads válidos.
- [ ] Implementar `DELETE /instances/{instance_id}` com exclusão em cascata; rejeitar enquanto houver execução ativa, marcar exclusão solicitada e repetir com segurança a limpeza de arquivos no object storage.
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

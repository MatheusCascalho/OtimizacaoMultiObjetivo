# Relatório de desenvolvimento: WORKFLOW_INSTANCE

**Período coberto:** 02/11/2026, 15:17–18:06 UTC  
**Tipo:** síntese de conversa de desenvolvimento

## Objetivos da conversa

- Especificar o fluxo de criação, execução e análise de instâncias de otimização.
- Criar um mockup do fluxo TSP biobjetivo de tempo e distância.
- Evoluir o mockup com visualização de soluções, exportação CSV e filtro de vizinhos no grafo.
- Definir contratos de API e decisões de arquitetura/persistência para o backend.
- Documentar a arquitetura proposta em diagramas Mermaid.

## Decisões

- O catálogo de tipos de problemas define entradas, objetivos, algoritmos e visualizações disponíveis; API e domínio validam as configurações recebidas.
- A execução da otimização é assíncrona: Flask cria o registro da execução e enfileira tarefas Celery usando Redis como broker. Workers Python executam os serviços de domínio/solver. Redis não é armazenamento persistente da aplicação.
- PostgreSQL é o banco principal para metadados, execuções, notificações e soluções consultáveis. SQLite fica restrito a testes ou experimentação local simplificada.
- Arquivos de entrada ficam em armazenamento de objetos S3 compatível; SILO foi escolhido como opção de serviço em container para o ambiente local. A aplicação usa uma interface S3 para permitir substituição do serviço.
- Catálogos ficam em JSON versionado no repositório. Instâncias e execuções registram configuração e versões relevantes para reprodutibilidade.
- O layout espacial das cidades é gerado e persistido por instância, sendo reutilizado nos grafos de dados e soluções.
- O filtro do grafo prévio tem padrão de 20 vizinhos, ordena por menor tempo e limita o valor efetivo a `n - 1`; em matrizes assimétricas, vizinhos são selecionados por cidade de origem.

## Artefatos criados ou alterados

- `README.md`: alterado para incluir link à especificação da feature.
- `docs/features/workflow_instance/README.md`: criado e expandido com catálogo TSP, fluxo e critérios de aceite, endpoints Flask, exemplos de payloads, estados de execução, Celery/Redis, persistência em PostgreSQL/S3, SILO local, entidades relacionais e diagramas Mermaid de componentes, execução assíncrona e entidades persistidas.
- `docs/features/workflow_instance/mockups/README.md`: criado e alterado para documentar as interações e os limites do protótipo.
- `docs/features/workflow_instance/mockups/index.html`: criado e atualizado com assistente de criação, dashboard TSP, filtro de vizinhos, tabela de soluções e diálogo de visualização.
- `docs/features/workflow_instance/mockups/app.js`: criado e atualizado com simulações do fluxo, seleção dos vizinhos mais próximos, coordenadas compartilhadas entre grafos, ações de ver solução e download de rota CSV.
- `docs/features/workflow_instance/mockups/styles.css`: criado e atualizado para os controles do filtro, tabela e diálogo responsivo da solução.
- `docs/dev_report/2026-11-02-REP02-workflow-instance.md`: este relatório.

## Interação com a IA

A IA elaborou a especificação e o protótipo a partir dos requisitos iterativos da pessoa usuária. Em seguida, registrou a proposta de endpoints, ajustou a arquitetura após a decisão de usar Celery/Redis e documentou a estratégia de persistência aceita, incluindo PostgreSQL e armazenamento S3 compatível em container. A pessoa usuária também solicitou e orientou a inclusão dos diagramas Mermaid e das interações adicionais do mockup.

## Dificuldades e limitações

- O exemplo possui seis cidades; portanto, o controle configurado com padrão 20 exibe efetivamente até cinco vizinhos por cidade. O mockup informa essa limitação.
- As matrizes, rotas, coordenadas, progresso e resultados do mockup são demonstrativos. Arquivos não são enviados nem processados por backend.
- API Flask, worker Celery, Redis, PostgreSQL, SILO e solver não foram implementados ou integrados nesta conversa. A exigência de executá-los em containers está documentada, mas o arquivo Compose não foi alterado para adicioná-los.
- O navegador não estava disponível para inspeção visual responsiva ou teste automatizado de interações no browser.
- A porta 8080 já estava ocupada pelo servidor existente; o mockup da feature foi servido temporariamente pelo servidor Python na porta 8766.

## Verificações realizadas

- `node --check` no JavaScript do mockup: sem erros de sintaxe.
- Verificação estrutural do HTML: IDs únicos, referências de recursos locais e seletores JavaScript conferidos.
- Teste isolado do filtro de vizinhos com valores 1, 2 e 20: cada cidade obteve a quantidade esperada de vizinhos de saída e nenhum auto-vizinho foi selecionado.
- Diagnósticos do editor para HTML, CSS e JavaScript: nenhum erro reportado.
- `git diff --check`: sem erros de whitespace.
- Servidor estático Python na porta 8766: página respondeu HTTP 200 e o JavaScript servido passou por `node --check`.
- Nenhum teste de integração, build do backend ou inspeção visual foi executado.

## Próximos pontos

- Implementar a configuração de desenvolvimento com Flask, workers Celery, Redis, PostgreSQL e o serviço S3 compatível SILO, incluindo volumes, preparação do bucket, variáveis locais e migrações.
- Definir contratos finais de upload/CSV, autenticação, retenção, parâmetros de solver, cancelamento e progresso.
- Implementar persistência e serviços de domínio, mantendo a API desacoplada do broker e do armazenamento de objetos.
- Substituir dados demonstrativos por chamadas reais à API e validar o fluxo em navegador nas larguras mobile e desktop.

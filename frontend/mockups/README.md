# ParetoLab: identidade visual e mockup

## Direção de marca

**ParetoLab** é um ambiente de exploração de trade-offs, não apenas um painel de métricas. A identidade combina a precisão de um caderno de pesquisa com a clareza de uma ferramenta de análise: superfícies claras, divisórias finas, dados alinhados e cor reservada para destacar decisões e soluções.

- **Assinatura:** ParetoLab — Laboratório de Otimização Multiobjetivo.
- **Ideia do símbolo:** pontos conectados por uma fronteira ascendente, representando alternativas não dominadas. No mockup, o símbolo é composto por eixos e pontos, sem depender de um arquivo de imagem externo.
- **Paleta:** papel `#F5F4EE`, tinta `#182B25`, verde `#28624D`, coral `#D96545`, azul `#4777A8` e amarelo `#E5B94F`. Verde indica execução e viabilidade; coral e azul distinguem objetivos; amarelo marca atenção e seleção.
- **Tipografia:** Space Grotesk para títulos, DM Sans para interface e IBM Plex Mono para valores, identificadores e metadados. O mockup usa fontes alternativas caso as fontes web não estejam disponíveis.
- **Princípios de interface:** densidade moderada, hierarquia por tipografia e alinhamento, gráficos como conteúdo principal, controles explícitos e sem decoração que concorra com os dados.

## Interface local

O frontend usa somente HTML, CSS e JavaScript vanilla. Com a stack Compose ativa, a tela consome o catálogo, upload, instâncias, análise de matrizes/grafo, execução/polling/cancelamento, resultados, notificações e download de rota da API local.

Os relatórios de robustez e multicritério são persistidos por execução e reapresentados ao abrir a última execução concluída da instância. A seção de decisão AHP permite calibrar comparações entre distância, tempo, emissão de CO2 e Min-Max Regret, conferir a razão de consistência e consultar o ranking e as matrizes (com paginação para matrizes de alternativas maiores). O cálculo é realizado pela API Python em `POST /api/v1/runs/{run_id}/ahp`; blocos das matrizes de alternativas são obtidos por `POST /api/v1/runs/{run_id}/ahp/matrices`. Ambos usam somente métricas disponíveis no relatório real de robustez e não criam resultados ilustrativos.

Sem API disponível, o dashboard mantém um conjunto ilustrativo, identificado como tal; não indica sucesso de criação ou execução. O solver real v1 é `RandomHeuristic` e produz uma aproximação por amostragem, não uma fronteira ótima garantida.

Para testar o fluxo real, configure `.env.example` em `.env`, execute `docker compose up --build` na raiz e abra `http://127.0.0.1:8080`. A API fica em `http://127.0.0.1:5000`; ambas as portas são locais. Não exponha esta versão single-user à rede, pois ainda não há autenticação.
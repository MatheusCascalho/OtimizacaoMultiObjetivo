# WORKFLOW_INSTANCE — criação, execução e análise de instâncias

## Objetivo

Especificar o fluxo ponta a ponta para criar uma instância de otimização a partir de arquivos, inspecionar os dados, configurar e acompanhar uma execução assíncrona e analisar seus resultados. O catálogo de tipos de problema determina quais entradas, algoritmos e visualizações estão disponíveis.

Esta é uma especificação funcional. API, banco de dados e solvers ainda não estão integrados ao mockup. O protótipo navegável fica em [`mockups/`](./mockups/).

## Catálogo de tipos de problema

O catálogo deve ser a fonte de configuração do fluxo, evitando que telas mantenham listas independentes. Cada tipo publicado deve declarar:

| Informação | Conteúdo |
|---|---|
| Identificação | Código estável, nome, descrição e objetivos com nome, unidade e direção (minimizar/maximizar). |
| Entradas | Arquivos esperados, formato, validações e relação entre arquivos. |
| Análise prévia | Visualizações disponíveis e as entradas consumidas por cada visualização. |
| Solução | Modelos/algoritmos disponíveis, descrição e parâmetros configuráveis, quando aplicável. |
| Análise de resultados | Visualizações disponíveis, dados necessários e interpretações apresentadas. |

O cliente carrega essas opções a partir do catálogo do problema selecionado. A API/domínio deve validar novamente todas as escolhas; uma opção removida ou incompatível não pode ser aceita somente porque a interface a enviou.

### Entrada inicial do catálogo: TSP biobjetivo — tempo vs. distância

- **Objetivos:** minimizar tempo e minimizar distância.
- **Arquivos:** duas matrizes de adjacência CSV, uma para tempo e outra para distância; cada arquivo é uma matriz quadrada numérica sem cabeçalho. A ordem dos nós deve ser idêntica nos dois arquivos. Não presumir simetria.
- **Análise prévia:** grafo de arcos ponderados e heatmap da matriz de cada objetivo. No grafo, permitir configurar quantos vizinhos mais próximos mostrar por cidade; o padrão é 20, ordenado pelo menor tempo (minimizando esse objetivo) e excluindo a diagonal. Limitar a quantidade efetiva a `n - 1`, pois uma cidade não pode ter mais vizinhos do que as demais cidades da matriz. Mostrar claramente a quantidade solicitada e o limite disponível. Em matrizes assimétricas, selecionar os vizinhos de saída por cidade conforme sua própria linha; representar os arcos selecionados com direção. O grafo deve identificar qual peso/unidade está sendo mostrado; os heatmaps devem identificar objetivo, eixos/nós e escala.
- **Algoritmos:** a lista efetivamente selecionável deve vir das implementações disponíveis para esse tipo de problema. O mockup mostra ε-restrição como exemplo de opção, não como integração ou disponibilidade confirmada.
- **Análise dos resultados:** fronteira de Pareto (tempo × distância), tabela de soluções com valores/unidades e indicação de dominância. Cada linha oferece **Ver solução**, para desenhar somente os arcos da rota selecionada, e **Baixar resultado**, para exportar a sequência de cidades visitadas em CSV.

As coordenadas das cidades devem ser geradas uma vez para o grafo da instância e persistidas junto à instância/layout. O grafo de cada solução deve reutilizar exatamente esse conjunto de coordenadas; abrir diferentes soluções não deve recalcular a posição dos nós. O CSV de rota contém a ordem e identificador da cidade e inclui o retorno à cidade inicial, formando o ciclo do TSP.

Validações mínimas dos arquivos: extensão/formato aceito, conteúdo numérico finito, matriz não vazia e quadrada, dimensões iguais entre arquivos e correspondência da ordem dos nós. Erros devem apontar arquivo e, quando possível, linha/coluna. A regra para diagonal, separador decimal e limite de tamanho deve ser definida junto ao contrato de dados do domínio antes da integração.

## Fluxo do usuário

1. **Nova Instância:** escolher o tipo do problema, informar um nome e anexar todos os arquivos requeridos pelo catálogo. Para TSP, anexar os CSVs de tempo e distância em campos identificados separadamente. A interface valida presença, tipo e tamanho localmente; o servidor valida o conteúdo.
2. **Configuração:** avançar para revisar as visualizações de análise prévia e de resultados e selecionar o modelo/algoritmo. As opções e padrões vêm do tipo de problema. É necessário selecionar pelo menos uma visualização em cada etapa de análise e um algoritmo disponível.
3. **Criação:** confirmar em **Criar instância**. A instância é persistida com o tipo, nome, arquivos/referências e configuração. Ao concluir a criação, abrir seu dashboard em estado **Pronta para otimização**, apresentando a análise prévia.
4. **Execução:** **Otimizar** solicita uma execução assíncrona e retorna sem esperar o solver terminar. Mostrar estado, identificador/horário e progresso somente se fornecido pelo serviço. O usuário pode navegar para outras áreas e voltar ao dashboard.
5. **Cancelamento:** durante uma execução ativa, permitir **Cancelar otimização**. Exibir estado de cancelamento até a confirmação do serviço; só marcar como cancelada depois da confirmação. Resultados parciais, se existirem, não devem ser apresentados como execução concluída.
6. **Conclusão e análise:** ao receber estado concluído, habilitar **Visualizar resultados** e criar uma notificação no centro de notificações. A ação abre o dashboard da instância; a análise utiliza as visualizações escolhidas na criação.

## Estados e comportamento

Estados da instância: **Rascunho**, **Pronta para otimização**, **Em fila**, **Em execução**, **Cancelamento solicitado**, **Cancelada**, **Concluída** e **Falhou**. Erros de validação de entrada/configuração devem manter a instância editável; falha de execução deve oferecer a mensagem retornada pelo serviço e permitir uma nova tentativa sem ocultar o histórico.

| Situação | Comportamento esperado |
|---|---|
| Envio/criação em andamento | Indicar atividade e impedir submissões duplicadas; preservar os campos em caso de falha recuperável. |
| Execução ativa | Atualizar status sem bloquear a navegação; disponibilizar cancelamento e manter identificação da instância. |
| Serviço indisponível/erro | Informar que a ação não foi concluída e oferecer nova tentativa apropriada. Não mostrar sucesso fictício. |
| Cancelamento solicitado | Aguardar confirmação e representar claramente que a execução ainda pode estar encerrando. |
| Execução concluída | Habilitar análise e registrar notificação acessível por botão com nome e contador de não lidas. |
| Execução cancelada/falha | Não habilitar análise de resultados finais; mostrar status e mensagem correspondente. |

Notificações devem ser associadas à instância e à execução, persistir após navegação/atualização quando houver suporte de backend, e levar o usuário ao recurso relacionado. O status também deve ser obtido ao abrir o dashboard, não depender exclusivamente de a tela permanecer aberta.

## Contratos de serviço esperados

Os nomes abaixo são conceituais; a API ainda precisa definir os contratos finais:

- Consultar o catálogo de problemas e suas opções.
- Criar instância com metadados, arquivos e seleções validadas.
- Solicitar uma execução e receber um identificador de execução sem aguardar o solver.
- Consultar estado/progresso e resultados de uma execução.
- Solicitar cancelamento de uma execução ativa e receber sua confirmação/estado final.
- Consultar notificações do usuário e marcar como lidas.

O mecanismo de atualização (polling, eventos enviados pelo servidor ou outro) e autenticação são decisões da implementação. Erros e estados devem ter representação explícita no contrato.

## Critérios de aceite

1. O usuário consegue selecionar tipo, nome e todos os arquivos obrigatórios; arquivos ausentes ou incompatíveis são indicados antes da criação.
2. O passo de configuração apresenta somente gráficos e algoritmos associados ao tipo escolhido, permite confirmar preferências e impede configuração incompleta.
3. Após criar a instância, o dashboard exibe as análises prévias configuradas e identifica os dados/orientação/unidades apresentados.
4. A execução é iniciada de forma assíncrona; o usuário pode navegar para outra área sem perder o vínculo com a execução.
5. Durante a execução, o usuário consegue solicitar cancelamento e acompanha a confirmação/status final sem ver a execução falsamente concluída.
6. Depois da conclusão, **Visualizar resultados** só então fica habilitado, mostra as análises configuradas e uma notificação direciona à instância.
7. Erros de upload, validação, criação, execução, consulta e cancelamento são comunicados sem serem convertidos em sucesso.
8. A tabela pós-otimização oferece **Ver solução** e **Baixar resultado** para cada alternativa. O grafo da solução exibe apenas seus arcos, e as posições das cidades coincidem com o grafo de entrada.
9. O CSV exportado apresenta a sequência ordenada de cidades, incluindo o retorno à origem.
10. O grafo prévio inicia com o parâmetro 20, exibe por cidade até `n - 1` vizinhos ordenados pelo menor peso e se atualiza ao alterar o parâmetro.
11. O fluxo funciona por teclado, tem rótulos e estados anunciáveis por tecnologia assistiva, e não depende exclusivamente de cor.
12. Em larguras móveis e desktop, etapas, gráficos, arquivos e ações permanecem legíveis e utilizáveis.

## Mockup e limites

Abra [`mockups/index.html`](./mockups/index.html) diretamente ou sirva a pasta `mockups/` com um servidor estático. O protótipo usa somente HTML, CSS e JavaScript vanilla.

Os nomes, matrizes, grafo, estados do solver e resultados do protótipo são ilustrativos. A seleção de arquivos ocorre somente no navegador; não há leitura/upload real, validação de domínio, persistência, API, notificações em segundo plano ou solver. O botão de otimização simula conclusão/cancelamento localmente para demonstrar a interação.

Na visualização do mockup, o controle começa em 20 vizinhos por cidade e ordena pelo tempo. Como o exemplo tem seis cidades, o limite efetivo é cinco vizinhos por cidade. A disposição fixa A–F é armazenada no estado JavaScript da instância e compartilhada pelo grafo de entrada e pelos grafos de rota. O CSV baixado contém os dados fictícios da solução demonstrativa selecionada.

## Decisões pendentes para a integração

- Contrato de CSV (codificação, separador, cabeçalho, separador decimal), regra de diagonal e tamanho máximo.
- Algoritmos e parâmetros realmente disponíveis para cada tipo de problema.
- Transporte de atualização assíncrona, política de cancelamento e formato de progresso/resultados.
- Persistência, retenção e limites de tamanho dos arquivos; autenticação/autorização do workspace.
- Frequência e retenção de notificações, incluindo comportamento com múltiplas execuções por instância.

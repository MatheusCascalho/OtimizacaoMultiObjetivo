# Contexto para corrigir a seleção de algoritmo e as curvas de evolução

**Período coberto:** 06/11/2026

**Tipo:** handoff. Este arquivo descreve o estado observado e o que outro agente deve implementar. Nenhum código, teste ou linha de banco foi alterado nesta conversa.

## Fontes consultadas

- `src/infrastructure/catalog/json/problem_types.json`
- `frontend/mockups/index.html` e `frontend/mockups/app.js`
- `src/api/routes/instances.py` e `src/api/routes/runs.py`
- `src/worker/tasks.py`
- `src/workflow_instance/domain/frontier_sampling.py`
- `src/multiobjective_algorithms/quality_evolution.py`
- `src/monoobjective_algorithms/tsp/heuristics/random_heuristic.py`
- `src/monoobjective_algorithms/tsp/heuristics/neuro_lkh.py`
- `src/infrastructure/persistence/postgres/models/instance.py`, `run.py` e `solution.py`
- Consulta ao Postgres do compose em execução, em 06/11/2026, sem alteração dos dados

## O que o usuário pediu

1. Liberar, na criação da instância, a escolha entre `RandomHeuristic` e `NeuroLKH`. Hoje essa escolha não aparece para o usuário.
2. Corrigir a última instância do banco para que os gráficos de evolução mostrem `NeuroLKH` no lugar de `RandomHeuristic`.
3. Corrigir o significado das curvas. A evolução esperada é a da fronteira acumulada dentro de cada rodada, não uma curva cujos pontos são as rodadas.

O enunciado anterior pedia 10 momentos igualmente espaçados e curvas médias sobrepostas, uma figura por indicador. A correção posterior, que esta implementação deve seguir, é mais específica e está na seção "Curvas" abaixo. Não reimplementar o eixo atual de rodadas.

## Problema 1: não há seleção de algoritmo

O catálogo do tipo `tsp-time-distance` lista um único algoritmo: `random-heuristic`, nome `RandomHeuristic`. Não existe entrada `neuro-lkh`. A entrada atual não tem `exact` nem `method`.

O diálogo "Criar instância" tem tipo de problema, nome e as duas matrizes. Não tem controle de algoritmo. Em `createInstance`, o corpo enviado à API fixa `configuration.algorithm_id` em `'random-heuristic'`.

A API já recusa um `algorithm_id` fora do catálogo, com `unsupported_algorithm` (422), em `POST /api/v1/instances`. Incluir `neuro-lkh` só no frontend, sem o catálogo, continua sendo rejeitado.

`POST /api/v1/instances/{id}/runs` copia `instance.configuration.algorithm_id` para `runs.algorithm_id`. O fallback, se o campo faltar, é `"random-heuristic"`.

O worker não lê esse id. `execute_run_with_dependencies` instancia sempre `NeuroLKH(seed=base_seed)` e chama `solver.solve` com `objective="time"` e `parameters.weight`. O peso de cada amostragem da rodada é `(attempt - 1) / (iterations - 1)`, com `attempt` de 1 até `iterations`. `RandomHeuristic.solve` rejeita o parâmetro `weight`. Um despacho que apenas troque a classe e continue passando `weight` quebra a heurística aleatória.

As duas classes já existem e declaram `algorithm_id`: `RandomHeuristic` é `"random-heuristic"`; `NeuroLKH` é `"neuro-lkh"`. Nenhuma das duas está marcada como exata ou heurística num campo que as curvas leiam. Estar em `src/monoobjective_algorithms/tsp/heuristics/` não conta.

### O que implementar

- Incluir os dois algoritmos no catálogo de `tsp-time-distance`, com nome exibido `RandomHeuristic` e `NeuroLKH`. Marcar os dois como não exatos, no formato que ` _catalog_exact` já entende: `method` igual a `"heuristic"`, ou `exact: false`. Manter os parâmetros que cada solver aceita. `iterations` e `seed` valem para os dois. `lkh_trials` é só do NeuroLKH. Não enviar `weight` para `RandomHeuristic`.
- No diálogo de criar instância, um controle obrigatório, em português, populado pelos algoritmos do tipo de problema escolhido. O `POST` usa o id selecionado. O padrão visível pode ser `NeuroLKH`, porque é o solver que o worker executa hoje, mas o usuário precisa conseguir escolher `RandomHeuristic`.
- No worker, escolher a classe pelo `runs.algorithm_id`. `neuro-lkh` continua o fluxo atual de peso e LKH. `random-heuristic` usa `RandomHeuristic` sem `weight`. Um id desconhecido falha a execução com mensagem explícita, sem cair em silêncio no NeuroLKH.
- Atualizar o teste de catálogo que hoje exige a lista `["random-heuristic"]` e os testes de execução que assumem NeuroLKH para toda run.

`PATCH` da instância devolve `instance_configuration_frozen` (409) depois que existe qualquer run. A última instância já tem execuções concluídas. A correção dela não passa por esse endpoint.

## Problema 2: a última instância está rotulada como RandomHeuristic

Consulta feita no Postgres do compose, ordenando `instances.created_at` decrescente. A última instância é:

| Campo | Valor |
|---|---|
| `instance_id` | `inst_9a4c7c95dd7245f4866938b293052363` |
| `name` | `TSP BIOBJETIVO MULTIFRONTEIRA` |
| `status` | `completed` |
| `configuration.algorithm_id` | `random-heuristic` |
| `created_at` | `2026-11-06 00:50:00+00` |

As duas execuções concluídas dessa instância também estão com `algorithm_id` `random-heuristic`:

| `run_id` | `created_at` | `parameters` | Soluções | Rodadas |
|---|---|---|---|---|
| `run_c9abecac1b6a431abc0e47fbdb35a1e9` | `2026-11-06 21:28:39+00` | `iterations` 50, `repetitions` 5, `seed` 3940718952 | 250 | 1 a 5 |
| `run_1d80955713e44972a0b911570cbf5c6a` | `2026-11-06 00:50:11+00` | `iterations` 50, `repetitions` 5, `seed` 1998090279 | 250 | 1 a 5 |

A legenda vem de `_evolution_label`: o nome do catálogo para `runs.algorithm_id`. Como o id gravado é `random-heuristic`, a curva aparece como `RandomHeuristic`. O cálculo dessas runs foi feito por `NeuroLKH`, porque o worker ignora o id.

Há outras 11 instâncias, todas com `random-heuristic`. Não alterá-las. Há uma run `running` em `inst_9c3840dddb8d46af922a0931521b1072`; não mexer nela.

### O que implementar

Depois que o catálogo tiver `neuro-lkh` com nome `NeuroLKH`, atualizar só a última instância e as duas runs da tabela acima:

- `instances.configuration` dessa instância: `algorithm_id` passa a `neuro-lkh`, preservando o resto do JSON.
- `runs.algorithm_id` das duas runs passa a `neuro-lkh`.

Isso só corrige o rótulo. Não reconstrói a evolução intra-rodada dessas runs. Os dados guardados não trazem a ordem das amostragens. Ver a seção seguinte.

## Problema 3: as curvas tratam a rodada como iteração

`quality_evolution.py` documenta a decisão atual: a fronteira candidata só é persistida por `round_index`, então o eixo horizontal é a rodada, com no máximo 10 instantes. Com 5 rodadas, os cinco índices entram. `GET /api/v1/instances/{instance_id}/quality-evolution` devolve `axis: "iteration"` e `axis_label: "Iterações"`, mas cada ponto é uma rodada. A média junta execuções do mesmo algoritmo e dos mesmos parâmetros, ignorando `seed`.

O que o usuário espera, para o padrão de 50 amostragens por rodada:

- Dentro da rodada 1, cinco indicadores de hipervolume e cinco de espalhamento Δ.
- O primeiro usa só as 10 primeiras amostragens daquela rodada.
- Os seguintes usam as 20, as 30, as 40 e, por fim, as 50 primeiras. Cada ponto é a fronteira candidata do prefixo acumulado, não a fronteira da amostragem isolada.
- O mesmo vale para as rodadas 2, 3, 4 e 5.
- Cada indicador continua numa figura própria. As curvas das rodadas ficam sobrepostas na mesma figura.
- O eixo horizontal é o número de amostragens do prefixo (10, 20, 30, 40, 50), não o índice da rodada.

Se `iterations` não for 50, o passo continua sendo blocos de 10 amostragens acumuladas, e o último ponto é o prefixo completo da rodada. Com menos de 10 amostragens, há um único ponto, no total da rodada. Esta regra substitui, para este gráfico, a leitura de "10 momentos ao longo da execução inteira".

Há duas runs concluídas do mesmo algoritmo nessa instância. A média do enunciado, neste desenho, é a média entre execuções no mesmo número de rodada e no mesmo tamanho de prefixo. Uma execução só produz a curva dela. A semente continua fora da chave que separa curvas. O rótulo da curva precisa identificar a rodada e o algoritmo, em português.

Hipervolume e Δ seguem as definições já implementadas: objetivos normalizados de 0 no utópico a 1 no nadir, referência do hipervolume em 1,1 vezes o nadir normalizado. A referência e os extremos do espalhamento devem ser os da execução inteira, fixos para todos os prefixos, para a curva não mudar de escala no meio. A dominância é recalculada em cada prefixo. A coluna `dominance` gravada no fim da rodada não serve para o prefixo.

### Por que a última instância não tem esses pontos

Em cada rodada o worker acumula rotas únicas e só então grava `run_solutions`, todas com o mesmo `created_at` e só com `round_index`. Não há `attempt` nem ordem de amostragem na solução. `solution_timings` guarda `round`, `attempt` e `duration_ms`, sem rota e sem objetivos. Os 250 registros da última run são 50 rotas únicas por rodada, sem ordem recuperável. Não dá para saber quais foram as 10 primeiras.

Consequência: atualizar o `algorithm_id` faz a legenda dizer `NeuroLKH` com o gráfico antigo (um ponto por rodada). A curva por prefixo só existe para execuções novas, que persistirem a ordem da amostragem, ou para uma reexecução. Não inventar a ordem dos registros atuais. Não apagar as soluções já gravadas só para trocar o rótulo.

### O que implementar

- Persistir, por amostragem, o suficiente para montar os prefixos: rodada, índice da tentativa (1..`iterations`) e os objetivos. Pode ser coluna nova em `run_solutions` ou outra tabela. A fronteira final por rodada, já usada pelo mapa, continua disponível.
- Calcular hipervolume e Δ de cada prefixo 10, 20, 30, … na leitura, sem gravar o indicador.
- Trocar o payload de `quality-evolution` para essa série. O eixo deixa de se chamar iteração quando o valor é o tamanho do prefixo; o rótulo deve dizer que é o número de amostragens acumuladas na rodada.
- Uma curva por rodada, sobreposta, em cada uma das duas figuras. Média entre execuções comparáveis no mesmo par (rodada, tamanho do prefixo).
- Testes: prefixo de 10 não inclui a 11ª amostragem; 50 amostragens geram os pontos 10, 20, 30, 40 e 50; duas rodadas viram duas curvas; a ordem ausente nos registros antigos não é preenchida com a ordem de `solution_id`.

## Fora deste handoff

Não mudar a fórmula do hipervolume, a referência 1,1, o espalhamento Δ, os KPIs, a tabela por rodada, o filtro de rodadas nem o mapa. Não fazer commit neste relatório. Não incluir segredo de conexão.

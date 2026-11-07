# Seleção de algoritmo e curvas por prefixo da rodada

**Período coberto:** 06/11/2026

**Origem:** o handoff `docs/dev_report/2026-11-06-REP01-selecao-algoritmo-evolucao.md` pediu a implementação. Este relatório registra o que foi feito a partir dele.

## O que foi pedido

1. Permitir escolher `RandomHeuristic` ou `NeuroLKH` ao criar a instância.
2. Corrigir o rótulo da última instância e das duas execuções concluídas dela para `neuro-lkh`.
3. Trocar as curvas de evolução: o eixo passa a ser o prefixo acumulado de amostragens dentro de cada rodada, com uma curva por rodada.

## Decisões seguidas

- Os dois algoritmos entram no catálogo de `tsp-time-distance` com `method: "heuristic"`. `lkh_trials` fica só no NeuroLKH. `weight` não é parâmetro de catálogo nem é enviado à heurística aleatória.
- O diálogo de criar instância lista os algoritmos do tipo escolhido. O valor inicial visível é NeuroLKH.
- O worker escolhe a classe por `runs.algorithm_id`. Um id desconhecido falha a execução com mensagem explícita.
- Cada tentativa nova é gravada em `run_attempt_samples`, com rodada, índice e objetivos. A fronteira final continua em `run_solutions`.
- Hipervolume e Δ de cada prefixo são calculados na leitura. A referência e os extremos do espalhamento são os da execução inteira. A dominância é recalculada no prefixo.
- Execuções sem ordem de amostragem não geram curva e não usam a ordem de `solution_id`.

## Artefatos

Criados:

- `migrations/versions/0007_run_attempt_samples.py`
- `docs/dev_report/2026-11-06-REP02-selecao-algoritmo-curvas.md`

Modificados:

- `src/infrastructure/catalog/json/problem_types.json`
- `src/infrastructure/persistence/postgres/models/solution.py`
- `src/infrastructure/persistence/postgres/models/__init__.py`
- `src/multiobjective_algorithms/quality_evolution.py`
- `src/multiobjective_algorithms/__init__.py`
- `src/api/routes/runs.py`
- `src/worker/tasks.py`
- `frontend/mockups/index.html`
- `frontend/mockups/app.js`
- `frontend/mockups/quality_evolution.js`
- `tests/multiobjective_algorithms/test_quality_evolution.py`
- `tests/api/test_quality_evolution.py`
- `tests/api/test_problem_types.py`
- `tests/api/test_instances.py`
- `tests/worker/test_tasks.py`
- `tests/frontend/test_quality_evolution.js`

Consultado, sem edição de código: o handoff `docs/dev_report/2026-11-06-REP01-selecao-algoritmo-evolucao.md`.

## Banco em execução

No Postgres do compose, só estes registros mudaram de `random-heuristic` para `neuro-lkh`:

- instância `inst_9a4c7c95dd7245f4866938b293052363`
- execuções `run_1d80955713e44972a0b911570cbf5c6a` e `run_c9abecac1b6a431abc0e47fbdb35a1e9`

As outras 11 instâncias continuam com `random-heuristic`. A migração `0007_run_attempt_samples` foi aplicada no mesmo banco. As soluções já gravadas não foram apagadas nem reordenadas.

## Verificações

- `PYTHONPATH=src .venv/bin/python -m pytest tests/api tests/worker tests/multiobjective_algorithms tests/workflow_instance tests/domain tests/infrastructure -q`: 114 testes passaram.
- A API em execução passou a listar `random-heuristic` e `neuro-lkh`, ambos com `method` `heuristic`.
- `GET /api/v1/instances/inst_9a4c7c95dd7245f4866938b293052363/quality-evolution` responde com eixo `accumulated_samples`, nenhuma curva e a mensagem de que as execuções concluídas não guardam a ordem das amostragens.
- No navegador, em `http://127.0.0.1:8080`, o diálogo "Criar instância" tem o controle obrigatório Algoritmo, com NeuroLKH selecionado e RandomHeuristic disponível. A instância relabelada mostra essa mesma mensagem nas duas figuras de evolução.
- Os testes de frontend em Node não rodaram neste ambiente: o comando `node` não está instalado. O `app.js` servido foi exercitado pelo diálogo no navegador.

## Limitações

A curva por prefixo só existe para execuções novas, que persistirem a ordem da tentativa. A última instância continua sem esses pontos. As imagens `api`, `worker` e `paretolab` foram reconstruídas e recriadas para publicar o código. Não houve commit.

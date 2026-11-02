# Relatório de desenvolvimento: algoritmos TSP

**Período coberto:** 02/11/2026, 18:34–19:46 UTC  
**Tipo:** síntese de conversa de desenvolvimento

## Objetivos e decisões

- Separar a especificação de algoritmos da documentação da feature e mantê-la em `docs/algorithms/`.
- Criar uma instrução compartilhada do workspace que exija seguir essa especificação no desenvolvimento de algoritmos.
- Implementar em Pyomo o modelo TSP biobjetivo descrito na página 5 de `docs/UFMG/trabalho_completo.pdf`, com uma classe builder dedicada. O modelo mantém tempo e distância, minimiza um objetivo por execução e permite limitar o objetivo secundário. Os coeficientes MTZ foram generalizados para `n` nós.
- Organizar instâncias de teste em `data/instances/` e mover para lá `tempo.csv` e `distancia.csv`.
- Implementar `RandomHeuristic` como baseline compatível com a interface de solver monoobjetivo. A heurística retorna um ciclo Hamiltoniano aleatório ancorado no nó 1 e ambos os custos; uma semente opcional permite reproduzir a rota. A heurística não aceita limites de objetivos.
- Manter uma documentação Markdown por heurística em `docs/algorithms/`.

## Artefatos criados ou modificados

- `.github/instructions/algorithms.instructions.md`: criada instrução compartilhada para desenvolvimento, testes e notebooks de algoritmos.
- `README.md`: modificado para resumir a arquitetura e apontar para a especificação.
- `docs/algorithms/README.md`: criada e evoluída como especificação canônica da arquitetura, contratos de solver e modelo TSP.
- `docs/algorithms/random-heuristic.md`: criada documentação específica da baseline.
- `docs/features/workflow_instance/README.md`: removida a especificação de algoritmos, mantendo o documento focado no workflow.
- `requirements.txt`: criado com dependência Pyomo.
- `src/optimization_problems/`: criado pacote e modelo TSP; `tsp/instance.py` valida e normaliza as matrizes e `tsp/models/tsp_biobjective_model_builder.py` constrói o MILP.
- `src/monoobjective_algorithms/`: criado contrato compartilhado e implementação TSP de `RandomHeuristic`.
- `tests/optimization_problems/` e `tests/monoobjective_algorithms/`: criados testes para o builder e a heurística.
- `data/instances/tempo.csv` e `data/instances/distancia.csv`: movidos da raiz para a pasta de instâncias.
- `docs/dev_report/2026-11-02-REP03-tsp-algorithms.md`: este relatório.
- `docs/UFMG/trabalho_completo.pdf`: consultado para extrair a formulação da página 5.

## Interação com a IA

A IA reorganizou a documentação conforme as orientações da pessoa usuária, criou a instrução de workspace, extraiu o texto da página 5 do PDF e implementou o modelo e a heurística de acordo com os contratos definidos. Também moveu os CSVs e verificou que podem ser carregados como uma instância TSP de 250 cidades.

## Validações e limitações

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -t . -v`: 10 testes passaram.
- Smoke test com `data/instances/tempo.csv` e `data/instances/distancia.csv`: a heurística retornou uma rota fechada com 251 entradas e valores para ambos os objetivos.
- O modelo Pyomo foi construído com a instância armazenada; não foi executado um solver matemático.
- `git diff --check`: sem erros de whitespace.
- A baseline retorna uma rota viável, não uma solução ótima. Não foram avaliados seu desempenho estatístico, tempo de execução comparativo ou qualidade contra outros algoritmos.

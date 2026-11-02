# RandomHeuristic — TSP

## Finalidade

Heurística baseline para o Problema do Caixeiro Viajante (TSP). Gera uma rota viável aleatória sem tentar melhorá-la; serve como referência simples para comparação com outras heurísticas e solvers.

## Implementação

- Classe: `RandomHeuristic`
- Código: [`src/monoobjective_algorithms/tsp/heuristics/random_heuristic.py`](../../src/monoobjective_algorithms/tsp/heuristics/random_heuristic.py)
- Entrada: `TSPInstance`, com matrizes quadradas e alinhadas de tempo e distância.
- Interface: `MonoobjectiveSolver`, com `SolveRequest` e `SolveResult`.

## Comportamento

A heurística fixa o nó 1 como depósito, embaralha uniformemente os nós restantes e retorna o ciclo fechado:

```text
(1, ..., 1)
```

Cada nó aparece exatamente uma vez antes do retorno ao depósito. Os custos totais de tempo e distância são calculados para a rota e incluídos em `objective_values`. O resultado tem status `feasible`; a heurística não garante otimalidade nem melhora a rota.

## Parâmetros e reprodutibilidade

- `seed` (opcional, inteiro): pode ser fornecido ao construir `RandomHeuristic(seed=...)` ou em `SolveRequest.parameters["seed"]`. Usar a mesma semente e instância reproduz a mesma rota.
- Não há outros parâmetros suportados.

## Capacidades e limitações

- Pode ser chamada com objetivo principal `time` ou `distance`; ambos os custos são sempre retornados.
- Não aceita `objective_limits`, pois não procura uma rota que satisfaça limites em objetivos secundários. Não deve ser usada em métodos como ε-restrição que dependam dessa capacidade.
- Cada chamada retorna uma única rota aleatória, sem busca local ou avaliação de dominância.

## Testes

Os testes da implementação ficam em [`tests/monoobjective_algorithms/test_random_heuristic.py`](../../tests/monoobjective_algorithms/test_random_heuristic.py) e cobrem validade do ciclo, cálculo dos custos, reprodutibilidade pela semente e rejeição de pedidos incompatíveis.

# NeuroLKH — TSP

## Finalidade

Heurística guiada pela rede pré-treinada [NeuroLKH](https://github.com/liangxinedu/NeuroLKH) para uma instância do caixeiro viajante. O solver monoobjetivo recebe o TSP biobjetivo de tempo e distância, unifica os dois custos com um peso e devolve um ciclo. Não treina um modelo novo e não garante o ótimo.

## Implementação

- Classe: `NeuroLKH`
- Código: [`src/monoobjective_algorithms/tsp/heuristics/neuro_lkh.py`](../../src/monoobjective_algorithms/tsp/heuristics/neuro_lkh.py)
- Entrada: `TSPInstance`, com matrizes quadradas e alinhadas de tempo e distância.
- Interface: `MonoobjectiveSolver`, com `SolveRequest` e `SolveResult`.
- Dependência: submódulo `third_party/NeuroLKH`, checkpoint padrão `third_party/NeuroLKH/pretrained/neurolkh.pt`.
- Compilação do wrapper SWIG: [`build_neurolkh_swig.sh`](../../build_neurolkh_swig.sh), com Python 3.11. A imagem da API e do worker usa `python:3.11-slim-bookworm`, e o script repete os passos do `setup.sh` (`swig -python LKH.i` e `setup.py build_ext`) com esse interpretador. O código C fica em `third_party/NeuroLKH/SRC_swig`, não em `LKH-3.0.6`.
- Ambiente isolado, criado uma vez: `python3.11 -m venv third_party/NeuroLKH/.venv`, depois `numpy`, `scikit-learn` e `torch` (CPU). O SWIG usado na compilação foi o pacote pip `swig` desse ambiente, porque o binário do sistema não estava instalado. O script de build aplica o patch de custo explícito antes de compilar.

## Comportamento

Cada chamada de `solve` trata uma instância e um peso `w` em `[0, 1]`.

1. `WeightedCostScalarization.scalarize` normaliza tempo e distância para `[0, 1]` e unifica `s_ij(w) = w * t_hat_ij + (1 - w) * d_hat_ij`.
2. Essa matriz unificada vira as duas matrizes de uma `TSPInstance` temporária. `JonkerVolgenantSymmetrization.transform` simetriza essa instância, produzindo o TSP simétrico de `2n` nós. As matrizes originais não são simetrizadas em separado.
3. A rede `SparseGCNModel` recebe coordenadas 2D obtidas por MDS clássico dessa matriz simétrica, só como entrada da rede. A diagonal com penalidade e as arestas de acoplamento negativas não são enviadas ao helper de coordenadas do projeto. O LKH não otimiza a distância euclidiana desse embedding.
4. `featureGenerate` monta as arestas candidatas e `SparseGCNModel.forward` prediz escores de aresta e penalidades de nó. `LKH.main` recebe essas predições e a matriz simétrica explícita.
5. O conjunto de candidatas da rede pode deixar algumas arestas proibidas da simetrização. Um 2-opt sobre a matriz explícita troca cada uma delas por uma aresta entre as partições de saída e entrada, reduzindo o custo simétrico, até o ciclo poder ser decodificado.
6. O ciclo está nos `2n` nós. `JonkerVolgenantSymmetrization.original_route` recupera o ciclo original de `n` cidades, começando e terminando na cidade 1.
7. `objective_values` soma as matrizes originais de tempo e distância ao longo desse ciclo. O custo escalarizado e o custo simétrico, que inclui o deslocamento `-n * penalty`, não são o tempo nem a distância reportados.

O resultado tem status `feasible` quando o ciclo original é válido. Se a rede, a extensão ou o LKH falham, ou se o ciclo simétrico não pode ser decodificado, o status é `failed`, com `solution=None` e `objective_values` vazio. Não há fallback para `RandomHeuristic` e nenhum ciclo é inventado.

### Escala inteira

O LKH guarda pesos explícitos em inteiro de 32 bits e, em `CreateCandidateSet`, multiplica cada um por `Precision` (100). Antes dessa multiplicação, cada peso fica no máximo em 20_000_000.

Sobre a matriz simétrica `c_ij`:

- `shift` é o menor custo fora da diagonal, a aresta de acoplamento `-penalty`.
- `scale = (20_000_000 - 2) / max(c_ij - shift)` para `i ≠ j` (ou 1, se esse máximo é 0).
- `w_ij = round(scale * (c_ij - shift))` fora da diagonal; a diagonal fica 0.
- Se o arredondamento deixar um acoplamento tão caro quanto uma transição real, essas transições e as arestas proibidas sobem o suficiente para o acoplamento continuar estritamente mais barato.
- Uma constante final torna todo peso fora da diagonal pelo menos 1. Ela não muda a ordem entre ciclos que usam a mesma quantidade de cada tipo de aresta.

Diferenças menores que cerca de `1 / scale` podem coincidir no inteiro. A penalidade de Jonker-Volgenant domina a amplitude da matriz, então `scale` diminui quando a instância cresce.

## Parâmetros e reprodutibilidade

- `weight` (número finito em `[0, 1]`, padrão 0.5): peso da unificação. Pode ser definido no construtor ou em `SolveRequest.parameters["weight"]`; o pedido vale só para aquela chamada.
- `seed` (inteiro ou `None`): mesma validação de `RandomHeuristic`. `None` usa a semente fixa 1234 no processo do LKH. A mesma instância, o mesmo peso e a mesma semente reproduzem a mesma chamada.
- `lkh_trials` (inteiro positivo, padrão 1000): número de tentativas do LKH.
- `model_path` existe só no construtor e aponta para o checkpoint. O padrão é `third_party/NeuroLKH/pretrained/neurolkh.pt`.

O worker, quando não recebe `weight` nos parâmetros da execução, usa 0.5 se há uma iteração e `(i - 1) / (total - 1)` na iteração `i` quando há mais de uma, cobrindo `[0, 1]`. Um `weight` fixo na execução é repetido em todas as iterações. `seed` e `lkh_trials` são repassados quando estão nos parâmetros da execução.

## Capacidades e limitações

- Aceita objetivo principal `time` ou `distance`. Os dois custos originais são sempre retornados.
- Não aceita `objective_limits`. Não serve para ε-restrição.
- Cada chamada devolve um ciclo, não uma fronteira e não um ótimo garantido.
- Depende do runtime NeuroLKH em Python 3.11 (`third_party/NeuroLKH/.venv`), da extensão SWIG `_LKH` e do checkpoint pré-treinado. A imagem da API e do worker também é Python 3.11 e fala com esse runtime por um processo local, um processo por chamada. A imagem copia o checkout para `/app/third_party/NeuroLKH` (`NEUROLKH_ROOT`) e cria esse ambiente durante o build. Sem essa cópia, a execução no ParetoLab não encontra o pacote.
- A rede foi treinada com coordenadas euclidianas. Aqui ela vê um MDS da matriz de custos; a busca do LKH usa a matriz explícita.

## Testes

Os testes ficam em [`tests/monoobjective_algorithms/test_neuro_lkh.py`](../../tests/monoobjective_algorithms/test_neuro_lkh.py). Usam um backend injetado, sem PyTorch e sem SWIG, e cobrem a matriz simétrica da unificação, a decodificação do ciclo, a remoção de arestas proibidas, os custos originais, a reprodutibilidade, a rejeição de pedidos incompatíveis e a falha do backend. O teste do worker em [`tests/worker/test_tasks.py`](../../tests/worker/test_tasks.py) substitui `NeuroLKH` por um solver falso e verifica a persistência e os pesos enviados ao longo das iterações.

# NeuroLKH

`NeuroLKH` combina uma Sparse Graph Convolutional Network (SGN) treinavel com
o algoritmo LKH em C. A rede classifica arestas candidatas e estima penalidades
de nos; o LKH recebe esses sinais e executa as buscas de troca variavel em
lambda sobre a matriz explicita do objetivo.

## Solver

- Entrada: `TSPInstance`, com matrizes alinhadas de tempo e distancia.
- Objetivo: `time` ou `distance`; a matriz escolhida e enviada ao LKH como
  `TSP` simetrico ou `ATSP` dirigido.
- Saida: ciclo Hamiltoniano fechado, indexado a partir de 1, e os valores dos
  dois objetivos calculados nas matrizes originais.
- Construtor: `NeuroLKH(model_path, candidate_count=20, candidate_limit=5,
  trials=10, seed=1234)`.
- Parametros por chamada: `seed` e `trials`. Limites de objetivos nao sao
  suportados.
- O checkpoint deve ter sido treinado por `neuro_lkh_training`; pesos
  pre-treinados do NeuroLKH original usam coordenadas e outra arquitetura de
  entrada, portanto nao sao intercambiaveis.

Exemplo:

```python
solver = NeuroLKH(model_path="models/neuro_lkh.pt")
result = solver.solve(instance, SolveRequest(objective="distance"))
```

O wrapper escreve arquivos temporarios para candidatos e penalidades, serializa
a matriz em TSPLIB `FULL_MATRIX` e chama `elkai._elkai.solve_problem`. Os
arquivos sao removidos ao fim da chamada. Para ATSP, o LKH transforma a matriz
em uma instancia simetrica de `2n` nos; candidatos dirigidos e penalidades sao
expandidos para essa representacao antes de chamar o backend. Custos e
penalidades sao escalados para inteiros internos do LKH, mas os objetivos
retornados sao recalculados com os custos originais.

## Treinamento

O gerador produz TSPs euclidianos sinteticos: distancia simetrica e tempo
dirigido, obtido por velocidades aleatorias por arco. O rótulo de arestas e o
ciclo otimo obtido pelo algoritmo exato Held-Karp. O script limita esse rotulo
exato a 18 nos para manter o custo exponencial controlado. A perda das
penalidades usa o grau do 1-tree minimo da matriz simetrizada, conforme a
formulacao do artigo; para matrizes dirigidas, isso e um sinal aproximado.

Treino pequeno para validar o fluxo:

```bash
PYTHONPATH=src python -m monoobjective_algorithms.tsp.heuristics.neuro_lkh_training \
  --samples 128 --nodes 10 --epochs 2 --batch-size 16 \
  --hidden-dim 32 --gcn-layers 3 --output models/neuro_lkh.pt
```

O exemplo pequeno nao e uma configuracao de qualidade para producao. O modelo
treinado com instancias sinteticas pequenas nao tem garantia de generalizacao
para a instancia real de 250 nos. Para avaliar o uso real, gere um corpus que
represente a distribuicao das matrizes do projeto e compare rotas e custos com
baselines.

## Notebook de demonstracao

O notebook [`neuro_lkh_tsp.ipynb`](../../notebooks/neuro_lkh_tsp.ipynb) mostra
um fluxo autocontido de treino curto, chamada ao Elkai/LKH, validacao da rota e
comparacao com o rotulo exato em uma instancia sintetica pequena. Ele e
demonstrativo; nao representa uma configuracao de treino para producao.

## Backend e limitacoes

O backend e o pacote [`elkai`](https://github.com/fikisipi/elkai), que expõe
LKH 3 em uma extensao C para Python e aceita TSP/ATSP com matriz explicita.
Ele nao usa SWIG; foi selecionado porque o SWIG upstream do NeuroLKH recebe
coordenadas EUC_2D e nao aceita as matrizes do projeto. A licenca do Elkai/LKH
restringe o uso e a distribuicao a fins academicos e nao comerciais. Nao use
esse backend em um produto comercial sem obter uma licenca adequada.

O PyPI publica wheels do Elkai ate CPython 3.13. No CPython 3.14, a instalacao
via sdist 2.0.1 falha por uma chave `project.url` invalida no `pyproject.toml`
do pacote; use um interpretador com wheel disponivel ou uma versao do pacote
com essa metainformacao corrigida.

A rede neste projeto e treinada para custos derivados de matrizes, nao e uma
reproducao da arquitetura de entrada euclidiana do checkpoint original. A
heuristica retorna solucoes viaveis, nao prova de otimalidade. A inferencia e
executada em CPU pelo PyTorch; CUDA e opcional para treinamento.

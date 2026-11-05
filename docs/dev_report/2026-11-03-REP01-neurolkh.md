# Relatório de desenvolvimento: NeuroLKH

**Período coberto:** 02/11/2026–03/11/2026

**Tipo:** síntese de conversa de desenvolvimento

## Objetivos e decisões

- Integrar NeuroLKH ao projeto para TSP/ATSP com matrizes explícitas, aproximando a busca local da implementação LKH descrita no artigo.
- Treinar uma SGN própria em vez de reutilizar pesos pré-treinados, cuja entrada original baseada em coordenadas não corresponde às matrizes do projeto.
- Usar o LKH em C como backend. A investigação concluiu que o binding SWIG upstream não recebe as matrizes explícitas necessárias; foi escolhido Elkai, uma extensão CPython que aceita matrizes TSPLIB `FULL_MATRIX` para TSP e ATSP.
- Gerar instâncias sintéticas e usar ciclos ótimos Held–Karp como rótulos, limitando os rótulos exatos a 18 nós.
- Criar um notebook autocontido que demonstre treinamento curto, uso do solver e avaliação visual, tomando `random_heuristic_tsp.ipynb` como referência.

## Artefatos criados ou modificados

- `src/monoobjective_algorithms/tsp/heuristics/neuro_lkh_features.py`: criado para extrair features das matrizes e preparar candidatos, penalidades e dados do LKH.
- `src/monoobjective_algorithms/tsp/heuristics/neuro_lkh_model.py`: criado com a arquitetura SGN treinável para features derivadas de matrizes explícitas.
- `src/monoobjective_algorithms/tsp/heuristics/neuro_lkh_training.py`: criado com geração sintética, rótulos Held–Karp, treinamento e gravação de checkpoints.
- `src/monoobjective_algorithms/tsp/heuristics/neuro_lkh.py`: criado como wrapper do solver, serializando TSP/ATSP e usando a extensão nativa do Elkai/LKH.
- `tests/monoobjective_algorithms/test_neuro_lkh.py`: criado com testes de features, treinamento, validação de rotas e integração com o backend.
- `requirements.txt`: modificado para incluir Elkai e sinalizar a restrição de licença.
- `docs/algorithms/README.md`: modificado para referenciar a documentação de NeuroLKH.
- `docs/algorithms/neuro-lkh.md`: criado para documentar solver, treinamento, backend, licença e limitações; depois modificado para apontar ao notebook.
- `notebooks/neuro_lkh_tsp.ipynb`: criado como demonstração do fluxo de treino, chamada LKH, validação de rota e comparação com Held–Karp.
- `notebooks/random_heuristic_tsp.ipynb`: consultado como referência de estrutura e apresentação.
- `.github/instructions/algorithms.instructions.md`: consultado para seguir os contratos e orientações de notebooks de algoritmos.

## Interação com a IA

A IA inspecionou a compatibilidade do binding original com as matrizes do projeto, implementou e documentou a alternativa com Elkai/LKH, e produziu o notebook demonstrativo. As decisões da pessoa usuária de abandonar Python puro, treinar uma rede própria, preservar matrizes explícitas e aceitar Elkai orientaram a implementação. O notebook usa uma instância sintética pequena e informa que os parâmetros de demonstração não são uma configuração de produção.

## Validações e limitações

- A estrutura JSON do notebook e a sintaxe das células Python foram verificadas; `git diff --check` não reportou problemas.
- A execução de `pytest` focado foi tentada, mas a coleta falhou por `ModuleNotFoundError: No module named 'torch'` no ambiente `.venv` usado nesse teste.
- O notebook registra a execução da célula de instalação de PyTorch e da célula de imports/descoberta do repositório, que imprimiu `PyTorch: 2.15.0+cu132`. As células de treino e de chamada ao LKH não têm execução registrada nesta validação.
- A chamada à extensão nativa Elkai/LKH, incluindo os caminhos TSP e ATSP, não foi confirmada em execução. A documentação registra a limitação de instalação do Elkai 2.0.1 via sdist no CPython 3.14.
- A licença do Elkai/LKH restringe uso e distribuição a fins acadêmicos e não comerciais. A SGN e o corpus sintético demonstrativo não têm garantia de generalização às instâncias reais de 250 nós. O Held–Karp tem custo exponencial e é limitado a 18 nós.
- Antes da criação deste relatório, os demais arquivos do repositório não tinham mudanças pendentes; os artefatos estão nos commits `cf0bfa1` (implementação NeuroLKH) e `ba1edf0` (notebook demonstrativo).

## Próximos passos úteis

- Preparar um ambiente compatível com PyTorch e Elkai e executar todas as células do notebook do início ao fim.
- Rodar os testes focados e a suíte de testes nesse ambiente.
- Confirmar o comportamento nativo do Elkai com matrizes simétricas e assimétricas e revisar a utilização efetiva dos arquivos de candidatos e penalidades.
- Para avaliar qualidade em escala, treinar com dados representativos das matrizes reais e comparar custos/rotas com baselines, respeitando os termos da licença.

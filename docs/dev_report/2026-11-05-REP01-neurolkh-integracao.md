# Relatório: integração do NeuroLKH no worker do ParetoLab

**Período coberto:** 05/11/2026

**Tipo:** registro da conversa de implementação

## Resumo

O pedido foi implementar o NeuroLKH conforme `docs/algorithms/guia_de_integra_o_neurolkh.md`, com a interface monoobjetivo usada por `RandomHeuristic`, e passar a chamá-lo em `src/worker/tasks.py`. A instância resolvida pela rede pré-treinada é a unificação escalarizada das matrizes de tempo e distância, simetrizada por Jonker-Volgenant.

Foi criado um solver que carrega o checkout upstream, roda a rede e o LKH em um processo Python 3.11 e devolve a rota original com tempo e distância das matrizes de entrada. O worker troca o peso da unificação ao longo das iterações. Um notebook de 50 pesos foi executado na instância de 250 cidades. A imagem Docker foi alterada para Python 3.11 e para copiar o checkout, mas o build observado nesta conversa falhou ao recriar o `venv`; a correção posterior do `.dockerignore` não teve um build bem-sucedido registrado aqui. O remoto de `third_party/NeuroLKH` passou a ser `https://github.com/MatheusCascalho/NeuroLKH.git`. Nenhum commit foi criado.

## Decisões

- O LKH otimiza a matriz simétrica explícita. As coordenadas de MDS alimentam só a rede. A distância euclidiana desse embedding não substitui o custo escalarizado: a penalidade de Jonker-Volgenant domina a matriz, `torgerson_mds` exige diagonal zero, e um tour euclidiano não é obrigado a usar as arestas de acoplamento.
- Cada iteração do worker, sem um `weight` fixo nos parâmetros da execução, usa `w = (i - 1) / (total - 1)`. Uma única iteração usa `0.5`. O custo unificado é `s_ij(w) = w * t̂_ij + (1 - w) * d̂_ij`, depois da normalização min-max de cada matriz para `[0, 1]`.
- O processo da aplicação pode continuar em outro interpretador e chamar o runtime 3.11 por subprocesso. A imagem `src/api/Dockerfile` foi em seguida alterada para `python:3.11-slim-bookworm`, de modo que API, worker e o `venv` do NeuroLKH usem o mesmo Python.
- O conjunto de candidatas da rede pode deixar arestas proibidas da simetrização. Um 2-opt na matriz explícita troca essas arestas antes de `original_route`. O custo candidato enviado ao LKH passou a ser `C()`, sem a penalidade de nó `Pi`; `D()` fazia o ganho do Lin-Kernighan falhar na asserção `Gain % Precision == 0`.

## Artefatos

Criados:

- `src/monoobjective_algorithms/tsp/heuristics/neuro_lkh.py`
- `src/monoobjective_algorithms/tsp/heuristics/neurolkh_costs.py`
- `src/monoobjective_algorithms/tsp/heuristics/neurolkh_worker.py`
- `tests/monoobjective_algorithms/test_neuro_lkh.py`
- `docs/algorithms/neuro-lkh.md`
- `build_neurolkh_swig.sh`
- `scripts/neurolkh/ParetoLabExplicit.c`
- `scripts/neurolkh/apply_paretolab_lkh_patch.py`
- `notebooks/neuro_lkh_tsp.ipynb`
- `third_party/NeuroLKH/.gitignore` (no checkout do fork, ainda não commitado; ignora `.venv/`)

Modificados:

- `src/monoobjective_algorithms/tsp/heuristics/__init__.py`
- `src/monoobjective_algorithms/tsp/__init__.py`
- `src/worker/tasks.py`
- `tests/worker/test_tasks.py`
- `docs/algorithms/README.md` (árvore de módulos)
- `docs/algorithms/guia_de_integra_o_neurolkh.md` (URL do submódulo)
- `docs/algorithms/neuro-lkh.md`
- `src/api/Dockerfile`
- `.dockerignore`
- `compose.yaml` (`NEUROLKH_ROOT`)
- arquivos C do checkout em `third_party/NeuroLKH/SRC_swig/` (patch de custo explícito e troca de `D()` por `C()` em `ReadCandidates.c`)

`.gitmodules` e o `origin` do checkout passaram de `https://github.com/liangxinedu/NeuroLKH.git` para `https://github.com/MatheusCascalho/NeuroLKH.git`. O `HEAD` local e o `origin/main` do fork estavam em `32ab884c2fe6548ca4011eeb181af70fbfedc72b`. As modificações C locais não foram commitadas no fork. `RandomHeuristic` permanece no repositório. O catálogo JSON continua oferecendo só `random-heuristic`; o worker não consulta esse id e chama `NeuroLKH`.

## Dificuldades

- O exemplo `LKH.solve_tsp` do guia não existe no upstream. A chamada real usa `SRC_swig.LKH.featureGenerate`, `net.sgcn_model.SparseGCNModel.forward` e `SRC_swig.LKH.main`.
- O host desta sessão está em Python 3.12.3. A extensão SWIG foi compilada com Python 3.11.17 em `third_party/NeuroLKH/.venv`, com Torch CPU, porque o 3.12 remove macros da C-API usadas pelo wrapper.
- Na instância de 250 cidades (500 nós após a simetrização), a primeira busca estourou `LinKernighan.c:135` (`Gain % Precision == 0`). Depois da troca para `C()`, o tour ainda tinha 2 arestas proibidas e não decodificava. O 2-opt removeu as duas e a rota original passou a ser recuperada.
- No ParetoLab, o worker procurava `/app/third_party/NeuroLKH` e a imagem só copiava `src`. O código novo chegou a reportar a mensagem ampliada pedindo a inclusão do checkout na imagem. `docker restart` não troca a imagem; foi indicado `docker compose up -d --build --force-recreate`, sem `down -v`.
- O build com `python:3.11-slim-bookworm` falhou em `python -m venv` com `No such file or directory: '/app/third_party/NeuroLKH/.venv/bin/python'`. O `.venv` do host era copiado; o `python` dele aponta para `/usr/bin/python3.11`, ausente na imagem. `.dockerignore` passou a ignorar `**/.venv` e o Dockerfile apaga esse diretório antes de criar o ambiente. Não houve, nesta conversa, um build concluído depois dessa alteração.
- `git submodule set-url` não conseguiu gravar `.git/config` no sandbox. A URL foi gravada depois, direto no config do repositório pai e no `origin` do checkout. `git submodule sync` não reconheceu o pathspec, e `git status` do pai chegou a mostrar `third_party/` como não rastreado; o checkout em si tem `.git` e remoto atualizado.

## Verificações feitas

- A implementação inicial reportou 25 testes passando em `test_neuro_lkh.py`, `test_random_heuristic.py`, `test_scalarization.py`, `test_jonker_volgenant.py` e `test_tasks.py`, e uma instância de 3 cidades com peso `0.5`, semente `1` e 20 tentativas retornando rota `(1, 3, 2, 1)`, tempo `20` e distância `7`.
- Nesta sessão, depois do ajuste de `C()` e do 2-opt, `PYTHONPATH=src .venv/bin/python -m pytest tests/monoobjective_algorithms/test_neuro_lkh.py` passou com 6 testes e, após o teste de descoberta do checkout, com 7.
- Uma chamada real na instância `data/instances` (250 cidades), peso `0`, semente `42` e 20 tentativas, retornou status `feasible`, rota começando em `(1, 141, 10, 118, 13, 12, 39, 57)`, tempo `26.8` e distância `1466.7`, em cerca de 4 s.
- O notebook `notebooks/neuro_lkh_tsp.ipynb` foi executado: 50 pesos de `0` a `1`, semente `42`, 20 tentativas. Resultado registrado nas saídas: 50 rotas únicas, 3 não dominadas na amostra, primeira solução com tempo `26.80 h` e distância `1466.70 km`. A figura foi embutida no notebook.
- `git -C third_party/NeuroLKH check-ignore` confirmou que `.venv` casa com `.gitignore:1:.venv/`. O `.gitignore` em si continuava não rastreado na branch `adaptacao`.

## Interação com a IA

A IA leu o guia, a interface de `RandomHeuristic`, a escalarização e Jonker-Volgenant, e delegou a implementação inicial do solver a um agente de algoritmos. Em seguida revisou o contrato `solve`, a troca no worker e o texto de `docs/algorithms/neuro-lkh.md`.

Quando se perguntou se o LKH deveria usar a distância euclidiana do MDS, a resposta foi negativa, com base na forma da matriz simétrica e na decodificação da rota. O notebook foi escrito no formato de `notebooks/random_heuristic_tsp.ipynb`. A execução na instância de 250 cidades expôs a asserção do LKH e as arestas proibidas; a IA alterou o patch C, recompilou a extensão e acrescentou o 2-opt.

No erro de checkout ausente no ParetoLab, a IA atribuiu a falha à imagem que não copiava `third_party` e alterou `src/api/Dockerfile`, `.dockerignore` e `compose.yaml`. O usuário pediu a troca da imagem para Python 3.11 e, depois, relatou a falha do `venv` no build; a IA ajustou o Dockerfile e o `.dockerignore`. Também descreveu a variação de peso a partir de `_neuro_lkh_weight` e de `unify_costs`, apontou o submódulo para o fork e preencheu o `.gitignore` do checkout.

## Próximos passos

- Rodar de novo `docker compose build` e `docker compose up -d --force-recreate` e confirmar que o worker encontra `/app/third_party/NeuroLKH` e conclui uma execução.
- Commitar, no fork e na branch desejada, o `.gitignore` e, se for o caso, o patch C ainda só no diretório de trabalho.
- Registrar o submódulo no índice do repositório pai, se `third_party/` continuar não rastreado.
- O catálogo da aplicação ainda não oferece `neuro-lkh`.

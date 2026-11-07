# Relatório: o que mudou entre a falha e a integração do NeuroLKH

**Período coberto:** 03/11/2026–05/11/2026

**Tipo:** comparação entre duas execuções, a partir dos relatórios já registrados

## Fontes

Consultados, sem alteração:

- `docs/dev_report/2026-11-03-REP02-neurolkh-falha-tecnica.md`
- `docs/dev_report/2026-11-05-REP01-neurolkh-integracao.md`
- `docs/dev_report/2026-11-03-REP01-neurolkh.md` (contexto da primeira implementação)
- `docs/algorithms/guia_de_integra_o_neurolkh.md` (especificação seguida na segunda execução)

Este arquivo foi criado nesta conversa. Nenhum código de solver foi alterado aqui.

## Resumo

A execução de 02–03/11 não integrou o NeuroLKH. Entregou uma Sparse Graph Network própria, rótulos Held–Karp até 18 nós e um backend Elkai. O teste de integração parou porque `elkai` não existia no CPython 3.14.2 do `.venv`, e as células do notebook que treinam e chamam o solver não têm execução registrada.

A execução de 05/11 seguiu o guia de integração, carregou o checkout upstream (fork) e chamou a rede pré-treinada e o LKH pela extensão SWIG, num processo Python 3.11. Na instância de 250 cidades, uma chamada com peso `0` devolveu rota viável; o notebook de 50 pesos foi executado e gravou saídas. O que muda entre as duas, e que está ligado a esse resultado, é o alvo do código, o interpretador da extensão nativa, a separação entre entrada da rede e custo do LKH, e dois reparos feitos depois que a busca real falhou.

O build Docker da imagem com esse checkout não concluiu na conversa de 05/11. O sucesso registrado é o do solver no host e do notebook, não o do worker em container.

## O que a primeira execução não fez

O relatório de 03/11 descreve quatro desvios em relação ao requisito:

1. O código de [liangxinedu/NeuroLKH](https://github.com/liangxinedu/NeuroLKH) não foi incorporado nem chamado.
2. A incompatibilidade do binding SWIG com a matriz explícita do projeto foi tratada como impedimento para usar o NeuroLKH inteiro. O modo por subprocesso, documentado no README upstream, não foi testado.
3. Elkai substituiu o LKH do NeuroLKH. Uma chamada direta a `elkai._elkai.solve_problem`, fora do `.venv`, passou num TSP simétrico de quatro nós em Python 3.12. Isso não exercita `CANDIDATE_FILE`, `PI_FILE`, PyTorch nem a instância de 250 nós.
4. A rede treinada no projeto usa features e rótulos próprios. Não há, naquele relatório, execução dessa rede nas matrizes reais.

O mesmo relatório já separava o que faltava: rodar pesos pré-treinados no problema que o upstream suporta; só depois adaptar a entrada para matriz explícita; não tratar uma SGN alternativa como integração concluída.

## Mudanças que precedem o resultado de 05/11

### 1. O solver passou a chamar o NeuroLKH

Na segunda execução o checkout está em `third_party/NeuroLKH`, com `HEAD` local e `origin/main` do fork em `32ab884c2fe6548ca4011eeb181af70fbfedc72b`. O remoto deixou de ser `https://github.com/liangxinedu/NeuroLKH.git` e passou a ser `https://github.com/MatheusCascalho/NeuroLKH.git`.

A chamada deixou o exemplo `LKH.solve_tsp` do guia, que não existe no upstream, e usa a sequência real: `SRC_swig.LKH.featureGenerate`, `net.sgcn_model.SparseGCNModel.forward` e `SRC_swig.LKH.main`. O LKH otimizado é o do checkout, com patch C local para custo explícito, não a extensão do Elkai.

Sem esse checkout e sem essa sequência, a primeira execução não tinha como reproduzir a busca que o artigo acopla à SGN. O smoke test do Elkai mostrava outro binding, em outra instância.

### 2. A extensão SWIG rodou em Python 3.11

O guia marca Python 3.12 como incompatível: o wrapper SWIG do NeuroLKH usa macros da C-API removidas nessa versão. Na sessão de 05/11 o host estava em Python 3.12.3. A extensão foi compilada com Python 3.11.17 em `third_party/NeuroLKH/.venv`, com Torch CPU. O processo da aplicação chama esse runtime por subprocesso. A imagem `src/api/Dockerfile` foi alterada para `python:3.11-slim-bookworm` com a mesma intenção; o build observado nessa conversa falhou ao recriar o `venv` e não há build bem-sucedido registrado depois do ajuste do `.dockerignore`.

Na execução anterior o `.venv` do projeto era CPython 3.14.2, sem wheel do Elkai, e a máquina não tinha Python 3.13 nem `ensurepip` no 3.12. O único LKH que chegou a rodar foi o Elkai 2.0.1, instalado com `pip --target` no Python 3.12 do sistema. Esse arranjo não compila o SWIG do NeuroLKH e também não hospedava o backend que o wrapper da época importava.

A troca de interpretador não melhora o modelo. Ela é a condição para a extensão C do upstream carregar. A primeira execução não tinha essa condição no ambiente em que os testes rodaram.

### 3. A rede pré-treinada e o custo do LKH foram separados

A primeira decisão tratou a entrada por coordenadas do NeuroLKH como incompatível com as matrizes do projeto e, a partir disso, treinou outra rede. A segunda mantém os pesos pré-treinados e restringe o embedding.

Coordenadas de MDS alimentam só a rede. O LKH otimiza a matriz simétrica explícita. A distância euclidiana do embedding não substitui o custo escalarizado: a penalidade de Jonker-Volgenant domina a matriz, `torgerson_mds` exige diagonal zero, e um tour euclidiano não é obrigado a usar as arestas de acoplamento. Essa separação está registrada como decisão da conversa de 05/11, depois da pergunta sobre usar a distância do MDS no LKH.

O custo unificado, com min-max de cada matriz para `[0, 1]`, é `s_ij(w) = w * t̂_ij + (1 - w) * d̂_ij`. Sem `weight` fixo, o worker usa `w = (i - 1) / (total - 1)`; uma iteração usa `0.5`. A instância que a rede vê já é simétrica. O risco de ATSP apontado em 03/11 deixa de ser uma hipótese sobre o upstream: a matriz dirigida não é entregue ao LKH.

Isso cobre o passo que o relatório de falha pedia antes de retreinar: executar os pesos existentes no domínio que o modelo conhece e declarar, no adaptador, o que a matriz do projeto precisa virar para entrar nesse domínio.

### 4. Dois reparos só apareceram quando a instância de 250 cidades rodou

A primeira execução não chegou a essa busca, então estes defeitos não estavam visíveis.

Na instância de 250 cidades a simetrização produz 500 nós. A primeira busca estourou `LinKernighan.c:135` (`Gain % Precision == 0`). O custo candidato enviado ao LKH passou de `D()` para `C()`, isto é, sem a penalidade de nó `Pi`. Com `D()`, o ganho do Lin-Kernighan saía da grade inteira exigida por `Precision`.

Depois dessa troca, o tour ainda tinha 2 arestas proibidas da simetrização e não decodificava. Um 2-opt na matriz explícita removeu as duas antes de `original_route`. A chamada seguinte, peso `0`, semente `42` e 20 tentativas, devolveu status `feasible`, rota começando em `(1, 141, 10, 118, 13, 12, 39, 57)`, tempo `26.8` e distância `1466.7`, em cerca de 4 s.

O notebook executado em seguida percorreu 50 pesos de `0` a `1`, mesma semente e as mesmas 20 tentativas. As saídas registradas indicam 50 rotas únicas, 3 não dominadas na amostra, e a primeira solução com tempo `26.80 h` e distância `1466.70 km`.

O patch C e o 2-opt são locais. As modificações em `third_party/NeuroLKH/SRC_swig/` não foram commitadas no fork. Sem eles, o relatório de 05/11 descreve a busca abortando ou devolvendo um tour que não recupera a rota original. O sucesso medido depende desses dois ajustes, além do checkout e do Python 3.11.

## O que foi verificado em cada execução

| Verificação | 02–03/11 | 05/11 |
|---|---|---|
| Código upstream chamado | Não | Sim, via SWIG no fork local |
| Testes do wrapper | 6 passaram; o de integração falhou ao importar `elkai` | `test_neuro_lkh.py`: 6, depois 7, após o teste de descoberta do checkout. A implementação inicial reportou 25 testes em cinco arquivos e uma instância de 3 cidades |
| LKH em instância real | Não. Smoke test Elkai: 4 nós, Python 3.12, fora do `.venv` | 250 cidades, peso `0`, rota viável |
| Notebook | Instalação/import de PyTorch e descoberta da raiz. Treino e chamada LKH sem execução registrada | 50 pesos executados, saídas e figura gravadas no notebook |
| Imagem Docker com o checkout | Não fazia parte dessa entrega | Build com `python:3.11-slim-bookworm` falhou ao recriar o `venv`; não há build concluído depois do `.dockerignore` |

## O que não explica o resultado

- Trocar a URL do submódulo para o fork, por si só. O `HEAD` usado é o do upstream em `32ab884`; o que o LKH executou a mais está no diretório de trabalho, não num commit do fork.
- A SGN e o Held–Karp da primeira entrega. Esses módulos não são o caminho que produziu a rota de 250 cidades em 05/11.
- O teste unitário isolado do Elkai. Ele não exercita a rede pré-treinada nem a decodificação de Jonker-Volgenant.
- O ajuste de Docker e `.dockerignore`. Foram feitos na mesma conversa, e o relatório deixa o build seguinte sem registro de sucesso.

## Limites que continuam

O catálogo JSON ainda oferece só `random-heuristic`. O worker chama `NeuroLKH` direto. `.gitignore` do checkout, na branch `adaptacao`, seguia não rastreado; `third_party/` chegou a aparecer como não rastreado no repositório pai. O worker no container só fica coberto depois de um `docker compose build` que encontre `/app/third_party/NeuroLKH` e termine uma execução. Isso permanece como próximo passo do relatório de 05/11, não como verificação feita.

## Interação com a IA

Nesta conversa a IA leu os dois relatórios pedidos, o relatório de implementação de 03/11 e o guia de integração, e redigiu este comparativo. Não alterou solver, testes, Dockerfile nem o checkout.

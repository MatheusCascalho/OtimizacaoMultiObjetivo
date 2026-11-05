# Relatório técnico: falha na integração do NeuroLKH

**Período coberto:** 02/11/2026–03/11/2026

**Tipo:** análise técnica de implementação e proposta de retomada

## Resumo executivo

O objetivo principal era criar um wrapper do código de
[liangxinedu/NeuroLKH](https://github.com/liangxinedu/NeuroLKH) e usá-lo neste
repositório. Esse objetivo não foi atingido. O código entregue implementa uma
SGN própria, com features, treinamento e rótulos próprios, e usa Elkai como
backend LKH alternativo. Não incorpora nem chama o código Python/C do NeuroLKH
upstream. O notebook criado demonstra essa alternativa, não um wrapper do
NeuroLKH original.

A alternativa também não foi validada ponta a ponta: ao executar os testes com
`PYTHONPATH=src`, seis passaram e o teste de integração foi bloqueado pela
ausência do módulo `elkai` no ambiente; essa falha não demonstra defeito lógico
no wrapper. Em uma verificação posterior, instalou-se o wheel do Elkai 2.0.1
para Python 3.12 em um diretório isolado e uma chamada mínima direta à extensão
nativa LKH passou. Ainda não foi executado o teste completo do wrapper com esse
backend. As células do notebook que treinam a rede e chamam o solver também não
têm execução registrada. Portanto, a implementação permanece incompleta em
relação ao requisito original, e o caminho de integração específico do wrapper
continua sem validação ponta a ponta.

## Requisito original e resultado observado

O NeuroLKH upstream combina a Sparse Graph Network (SGN) em Python com o LKH em
C. O README upstream documenta dois modos para conectar os componentes:
execução por subprocesso com arquivos e integração via SWIG. Ele também informa
que a geração dos rótulos de arestas é demorada e que o treinamento de
penalidades de nós requer SWIG; o caminho por subprocesso não atende esse
treinamento sem alterações.

O resultado no projeto divergiu do requisito:

| Requisito ou etapa | Resultado efetivamente entregue |
|---|---|
| Encapsular o NeuroLKH do repositório indicado | O código upstream não foi incorporado, fixado como submódulo ou chamado pelo solver. |
| Usar a SGN do NeuroLKH | Foi criada uma SGN própria em `neuro_lkh_model.py`, com features derivadas das matrizes. |
| Usar o LKH C do NeuroLKH | O solver chama `elkai._elkai.solve_problem`, em vez do executável ou binding C do upstream. |
| Receber matrizes explícitas do projeto | O wrapper serializa a matriz selecionada como TSPLIB `FULL_MATRIX`; essa adaptação pertence à solução Elkai, não prova compatibilidade com NeuroLKH upstream. |
| Demonstrar uso funcional de ponta a ponta | O notebook existe, mas as células de treinamento e chamada LKH não foram executadas com sucesso nesta validação. |

O código personalizado está em
[`neuro_lkh.py`](../../src/monoobjective_algorithms/tsp/heuristics/neuro_lkh.py),
[`neuro_lkh_model.py`](../../src/monoobjective_algorithms/tsp/heuristics/neuro_lkh_model.py),
[`neuro_lkh_features.py`](../../src/monoobjective_algorithms/tsp/heuristics/neuro_lkh_features.py)
e
[`neuro_lkh_training.py`](../../src/monoobjective_algorithms/tsp/heuristics/neuro_lkh_training.py).
O notebook
[`neuro_lkh_tsp.ipynb`](../../notebooks/neuro_lkh_tsp.ipynb) usa essa
implementação e Elkai.

## Como a decisão técnica se desviou

1. A entrada matricial do projeto foi comparada principalmente com o binding
   SWIG do upstream. A incompatibilidade observada nesse caminho foi tratada
   como impedimento para usar o NeuroLKH como um todo.
2. O README upstream, no entanto, documenta também um caminho por subprocesso.
   Essa opção não foi avaliada como possível primeiro wrapper para inferência
   com os modelos pré-treinados, nem foi testada no ambiente do projeto.
3. Quando o escopo evoluiu para treinar uma rede própria e chamar LKH em C,
   Elkai foi selecionado como substituto, em vez de adaptar/buildar o LKH
   integrado ao NeuroLKH.
4. A implementação própria foi documentada e recebeu um notebook sem que a
   chamada do solver pelo wrapper tivesse sido verificada. Mais tarde, um smoke
   test isolado confirmou que a extensão Elkai/LKH executa em Python 3.12; isso
   não comprova a integração pelo wrapper nem a execução no ambiente Python do
   projeto. A demonstração continua incompatível com o objetivo central por
   usar uma SGN/back-end alternativos, não por uma falha lógica já comprovada.

Assim, a incompatibilidade com matrizes explícitas e a dificuldade de build
foram problemas reais a resolver, mas não justificavam abandonar a integração
com o repositório solicitado sem antes verificar e testar seus dois modos de
execução.

## Impeditivos e riscos técnicos

### 1. Contrato de entrada diferente

O projeto representa instâncias como matrizes alinhadas de tempo e distância;
as instâncias versionadas têm 250 nós, com tempo dirigido e distância
simétrica. O fluxo upstream documentado é centrado nos datasets e geradores do
próprio NeuroLKH. O binding SWIG já havia sido identificado durante a conversa
como incompatível diretamente com a matriz explícita do projeto.

Ainda falta um adaptador validado entre `TSPInstance` e a representação esperada
por cada modo upstream. É necessário determinar, no código upstream, se o modo
subprocesso consegue receber uma matriz explícita sem alterar o algoritmo, ou
se a geração de features e os dados de entrada dependem de coordenadas
euclidianas. ATSP é um risco adicional: a documentação pública consultada
descreve TSP, mas não comprova suporte do NeuroLKH upstream a custos dirigidos.

### 2. Inferência e treinamento têm requisitos diferentes

O README upstream oferece subprocesso e SWIG para conectar a SGN ao LKH, mas
declara que o treinamento de penalidades de nós exige SWIG e que o subprocesso
não é suportado nesse fluxo. A geração dos rótulos de arestas é descrita como
custosa (na ordem de dias no fluxo documentado).

Portanto, um wrapper para avaliar pesos pré-treinados pode ter um caminho de
integração distinto daquele necessário para treinar a rede. O trabalho anterior
não separou essas etapas nem comprovou que a interface selecionada serviria às
duas.

### 3. Backend substituto e instalação

O wrapper atual importa a extensão nativa do Elkai. Na validação realizada,
`PYTHONPATH=src .venv/bin/python -m pytest tests/monoobjective_algorithms/test_neuro_lkh.py -q`
resultou em **6 testes aprovados e 1 falha**. O teste restante falhou ao importar
`elkai`, que não estava instalado nesse ambiente. O interpretador desse `.venv`
é **CPython 3.14.2**. A falha ocorreu antes de testar a lógica que chama o
backend: é um bloqueio de dependência/configuração naquele ambiente, não
evidência de defeito lógico no wrapper.

Como verificação adicional, foi instalado o wheel `elkai 2.0.1` para CPython
3.12 em `/tmp/neuro-lkh-validation-py312-site`, sem alterar dependências do
projeto. Uma chamada mínima direta a `elkai._elkai.solve_problem` com matriz
simétrica `FULL_MATRIX` de quatro nós retornou uma rota Hamiltoniana e passou
as asserções. Essa chamada ocorreu fora do `.venv` do projeto, no Python 3.12
do sistema, usando `pip --target`. Não foi possível criar um virtualenv Python
3.12 porque o sistema não tem `ensurepip`; Python 3.13 também não está
disponível nesta máquina.

Esse smoke test comprova que o wheel instala e que a extensão Elkai/LKH executa
um caso TSPLIB básico. Ele **não** verifica `NeuroLKH.solve`, uso de
`CANDIDATE_FILE`/`PI_FILE`, integração com PyTorch, matriz ATSP ou execução
completa do notebook. O smoke test também não remove o bloqueio de instalação
do Elkai no Python 3.14.2 do projeto. Esses comportamentos permanecem sem
comprovação.

A documentação do projeto registra ainda um problema de instalação do Elkai
2.0.1 via sdist no CPython 3.14 e disponibilidade de wheels até CPython 3.13.
Mesmo que a instalação seja corrigida ou realizada em outro Python, Elkai
continua sendo outro binding/LKH e não satisfaz por si só o requisito de
utilizar o repositório NeuroLKH.

### 4. Treinamento personalizado não equivale ao treinamento upstream

O treinamento implementado gera instâncias euclidianas pequenas e rótulos por
Held–Karp, limitado a 18 nós. Usa uma arquitetura/features adaptadas e uma
aproximação para a perda de penalidades em matrizes dirigidas. Isso é um
experimento independente; não valida a arquitetura, o pipeline de rótulos, a
integração C ou a qualidade do NeuroLKH original. Não há evidência de
generalização para as instâncias reais de 250 nós.

### 5. Licença e reprodutibilidade do build

Foi registrada restrição acadêmica/não comercial para o Elkai/LKH. A licença e
as obrigações de redistribuição do código NeuroLKH upstream e da versão do LKH
incluída nele devem ser examinadas diretamente antes de incorporar ou
redistribuir essas fontes. O repositório atual não contém o código upstream nem
um processo reprodutível para compilá-lo.

## Evidências verificadas

- O README upstream documenta os modos subprocesso e SWIG, seus comandos
  básicos, o requisito de SWIG para treinamento das penalidades de nós e o
  custo elevado de gerar rótulos. Referências: [README do NeuroLKH](https://github.com/liangxinedu/NeuroLKH)
  e [setup.sh do SWIG](https://raw.githubusercontent.com/liangxinedu/NeuroLKH/master/setup.sh).
- O commit `cf0bfa1` adiciona os módulos próprios de SGN/treinamento/wrapper,
  testes e dependência Elkai; ele não adiciona fonte upstream. O commit
  `ba1edf0` adiciona o notebook que documenta o fluxo Elkai.
- Na execução dos testes com `PYTHONPATH=src`, seis testes passaram; o teste de
  integração parou ao importar o backend, ausente naquele ambiente, e o wrapper
  reportou `RuntimeError` encadeando `ModuleNotFoundError`. Isso não estabelece
  falha de lógica do wrapper. O executável `.venv/bin/python` usado é CPython
  3.14.2.
- Em Python 3.12, a instalação isolada do wheel Elkai 2.0.1 e uma chamada direta
  ao LKH nativo com TSP simétrico de quatro nós passaram. Não foi executado o
  teste completo do solver NeuroLKH nesse ambiente; o sucesso do smoke test não
  certifica o ambiente CPython 3.14.2 do projeto.
- O ambiente não tem Python 3.13, `uv` ou `pyenv`; Python 3.12 está instalado,
  mas sem `ensurepip`. O Docker CLI e o daemon Docker estão disponíveis.
- O notebook registra instalação/importação de PyTorch e descoberta da raiz do
  projeto. Não registra execução das células que treinam a SGN nem da célula
  que chama LKH.
- A validação anterior da estrutura JSON/sintaxe do notebook não demonstra a
  execução do solver. Nenhum resultado do LKH upstream foi obtido nesta
  conversa.

## Próximos passos propostos

1. **Fixar o alvo de compatibilidade.** Tratar como entregável primário um
   wrapper do NeuroLKH upstream. Separar explicitamente: (a) executar os pesos
   pré-treinados no problema suportado pelo upstream; (b) adaptar o modelo e o
   pipeline para matrizes explícitas; (c) treinar uma rede própria. Não
   considerar a alternativa (c) concluída por apenas treinar outra SGN.
2. **Fazer uma prova de conceito com o upstream, sem substituir sua integração
   por Elkai.** Fixar uma revisão upstream,
   registrar a licença, dependências e compilador, compilar o caminho
   documentado por subprocesso e rodar um caso mínimo oficial com modelo
   pré-treinado. Em seguida, compilar/testar o caminho SWIG, que o upstream
   exige para o treinamento de penalidades.
3. **Mapear os contratos no código upstream.** Documentar formatos de dataset,
   geração de features/candidatos, interface SGN↔LKH, parâmetros e formatos de
   saída. Determinar por teste se a entrada admite matriz explícita ou somente
   instâncias derivadas de coordenadas; não inferir suporte a ATSP a partir do
   suporte a TSP.
4. **Implementar um adaptador mínimo para o contrato comum.** Para começar,
   limitar o wrapper ao domínio comprovadamente suportado pelo upstream.
   Converter o resultado para `SolveResult`, validar ciclo e recalcular os
   objetivos originais. Se a matriz explícita/ATSP não for compatível, declarar
   essa capacidade como não suportada nessa etapa, sem fallback silencioso.
5. **Decidir e implementar a extensão para matrizes.** Se for requisito
   inegociável, adaptar o caminho de entrada/feature generation do NeuroLKH e
   verificar a representação de ATSP no LKH. Só então definir dados de treino
   e rótulos escaláveis; Held–Karp até 18 nós não atende treinamento em 250
   nós. Manter as mudanças ao código upstream isoladas e rastreáveis.
6. **Adicionar validação automatizada por camada.** Incluir smoke test do build
   C/SWIG, inferência com instância suportada, validação de rota e custo; depois
   testes de matriz explícita simétrica e ATSP apenas se esses formatos forem
   implementados. Executar notebook do início ao fim em ambiente fixado.
7. **Concluir a validação de ambiente da alternativa somente se ela continuar
   útil.** O caminho mais direto neste ambiente é usar o Docker disponível com
   uma imagem Python 3.12 ou 3.13, instalar as dependências do projeto e
   executar o teste focado; por exemplo, na raiz do repositório:

   ```bash
   docker run --rm -v "$PWD:/workspace" -w /workspace python:3.12 \
     bash -lc "python -m pip install -r requirements.txt pytest && \
     PYTHONPATH=src python -m pytest tests/monoobjective_algorithms/test_neuro_lkh.py -q"
   ```

   Outra opção é instalar `uv` e criar um ambiente isolado com Python 3.13,
   que tem wheel do Elkai segundo a documentação atual do projeto. Em ambos os
   casos, verificar primeiro a disponibilidade de wheels para todas as
   dependências e o custo/variante de instalação do PyTorch. Executar o teste
   completo do wrapper, incluindo TSP e ATSP, leitura de candidatos e
   penalidades. Mesmo se aprovado, manter essa solução identificada como
   backend alternativo, não como integração do NeuroLKH upstream.

## Conclusão

A entrega atual deve ser considerada uma prova de conceito independente e
incompleta, não um wrapper do NeuroLKH. O próximo avanço deve voltar ao código
upstream: primeiro compilar e executar seu fluxo oficial de inferência; depois
definir, com evidência, a fronteira de adaptação necessária para as matrizes e
para o treinamento no problema deste projeto.

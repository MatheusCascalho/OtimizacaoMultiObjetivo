# Padrão de desenvolvimento dos algoritmos

Este documento define a organização e os contratos dos algoritmos de otimização do projeto. Os pacotes Python devem ser independentes dos adaptadores Flask, Celery, banco de dados e armazenamento de arquivos. A API e os workers chamam serviços de aplicação; esses serviços carregam os dados do problema e delegam a análise/otimização aos pacotes de algoritmos.

## Organização dos módulos

Adotar a seguinte estrutura como referência para o código Python:

```text
src/
  optimization_problems/
    __init__.py
    tsp/
      __init__.py
      instance.py
      models/
        __init__.py
        tsp_biobjective_model_builder.py
  monoobjective_algorithms/
    __init__.py
    interfaces.py
    tsp/
      __init__.py
      instance.py
      heuristics/
        random_heuristic.py
      exact/
  multiobjective_algorithms/
    __init__.py
    dominance.py
    epsilon_constraint.py
notebooks/
data/
  instances/
tests/
  optimization_problems/
  monoobjective_algorithms/
  multiobjective_algorithms/
```

- **`optimization_problems`** contém os modelos matemáticos dos problemas de otimização, organizados por família (por exemplo, `tsp`). Os modelos devem ser implementados com Pyomo. Cada modelo deve ter sua própria classe builder, responsável por construir e configurar o modelo Pyomo a partir da instância e do pedido de solução; builders não devem executar lógica de API, persistência ou visualização.
- **`monoobjective_algorithms`** contém heurísticas e solvers exatos, organizados em um subpacote por família de problemas. Cada implementação procura uma solução para um pedido monoobjetivo. O contrato compartilhado fica na raiz do pacote; tipos e detalhes específicos do problema ficam em seu subpacote (por exemplo, `tsp`).
- **`multiobjective_algorithms`** contém operações reutilizáveis de análise multiobjetivo, como dominância, e métodos de geração de fronteira, como ε-restrição. O pacote recebe um solver pela interface comum, sem importar ou selecionar implementações concretas de TSP ou de outra família.
- **`notebooks/`** guarda notebooks de experimentação, execução reproduzível e visualização. Notebooks orquestram os pacotes, mas não são o local das implementações reutilizáveis nem a dependência dos serviços da aplicação.
- **`data/instances/`** guarda instâncias de teste versionáveis e não sensíveis. Arquivos enviados por usuários e dados de execução não devem ser gravados nessa pasta: seguem o fluxo de armazenamento da aplicação descrito na especificação do workflow de instâncias.
- **`tests/`** espelha os pacotes e mantém testes unitários de builders, modelos, contratos, algoritmos e análise. Testes não devem depender de notebooks ou de serviços externos.

### Modelos Pyomo e builders

Cada modelo matemático deve ser implementado em Pyomo dentro de `optimization_problems`, agrupado pela família de problema e separado dos algoritmos que o executam. Para cada modelo concreto, criar uma classe builder própria, com responsabilidade explícita de traduzir a instância e o `SolveRequest` em um modelo Pyomo pronto para execução. Se houver variantes matemáticas distintas, cada variante deve ter seu próprio builder; não concentrar modelos diferentes em um builder genérico com ramificações implícitas.

O builder constrói e configura variáveis, restrições e objetivo(s) do modelo, respeitando a direção dos objetivos e os limites fornecidos no pedido. A execução do solver, a interpretação de status e a conversão do resultado para `SolveResult` pertencem à implementação monoobjetivo, não ao builder. Essa separação permite que o algoritmo multiobjetivo peça diferentes objetivos principais e limites (como na ε-restrição), enquanto o solver selecionado delega a construção ao builder correspondente.

Os builders e modelos não devem depender de Flask, Celery, banco de dados, armazenamento de arquivos ou notebooks. Testes unitários devem verificar, conforme aplicável, os componentes do modelo gerado — variáveis, função objetivo, restrições, direções e limites — usando instâncias pequenas e determinísticas.

O primeiro modelo concreto segue a formulação MILP do TSP biobjetivo da página 5 de [`trabalho_completo.pdf`](../UFMG/trabalho_completo.pdf): variáveis binárias para arcos dirigidos, restrições de grau de entrada/saída e variáveis MTZ contínuas para os nós diferentes do depósito 1. O modelo mantém expressões de tempo e distância e ativa apenas um objetivo por execução; limites nos objetivos secundários permitem sua utilização por métodos como ε-restrição. O coeficiente MTZ é generalizado pela quantidade de nós (`n - 1` e `n - 2`), em vez de fixar os valores 249 e 248 da instância de 250 nós do documento.

## Contrato monoobjetivo

Toda heurística e todo solver exato deve oferecer a mesma operação `solve`, recebendo a instância da família compatível e um pedido padronizado, e retornando um resultado padronizado. A tipagem pode manter a instância específica da família, sem alterar a forma como o cliente invoca o solver. Em pseudocódigo Python:

```python
class MonoobjectiveSolver(Protocol[InstanceT]):
    @property
    def algorithm_id(self) -> str: ...

    @property
    def capabilities(self) -> SolverCapabilities: ...

    def solve(
        self,
        instance: InstanceT,
        request: SolveRequest,
    ) -> SolveResult: ...
```

`SolveRequest` deve identificar o objetivo principal, seus limites opcionais sobre os demais objetivos e os parâmetros da execução. `SolveResult` deve informar explicitamente o estado da busca e, quando existir, a solução e os valores de seus objetivos; estados como inviável, limite atingido ou falha não podem ser convertidos em uma solução fictícia. O registro da execução conserva `algorithm_id`, parâmetros efetivos e versões relevantes para reprodutibilidade.

Todos os solvers obedecem à mesma assinatura, mas podem declarar capacidades distintas. Por exemplo, ε-restrição exige que o solver aceite limites em objetivos secundários; o serviço deve verificar essa capacidade antes de executar e reportar incompatibilidade claramente, sem fallback silencioso. O cliente seleciona um solver compatível com a família do problema e com as capacidades exigidas pelo método multiobjetivo.

Cada heurística deve ter documentação própria em um arquivo Markdown deste diretório, cobrindo seu problema, comportamento, parâmetros, capacidades e limitações.

## Contrato multiobjetivo e fluxo de execução

Os métodos multiobjetivo recebem a instância, as definições dos objetivos (identificador, direção e unidade), os parâmetros do método e uma implementação de `MonoobjectiveSolver`. Eles não conhecem a representação interna da instância nem chamam diretamente uma heurística ou biblioteca de solver. O solver converte o pedido padronizado para o modelo específico da família.

Para ε-restrição, o método escolhe um objetivo principal por chamada e varia os limites dos outros objetivos, invocando `solve` repetidamente pela interface. Soluções retornadas são agregadas, deduplicadas e filtradas pela análise de dominância. Uma solução domina outra quando não é pior em nenhum objetivo, respeitando a direção de cada objetivo, e é estritamente melhor em pelo menos um; qualquer tolerância numérica deve ser explícita e aplicada consistentemente.

A função `non_dominated_mask` em `multiobjective_algorithms.dominance` aplica essa definição a vetores de objetivos e direções explícitas (`minimize` ou `maximize`), retornando uma máscara alinhada às soluções de entrada. Pontos com vetores de objetivos idênticos não dominam uns aos outros e permanecem não dominados.

O serviço de aplicação valida problema, solver, capacidades e parâmetros, executa o método e entrega progresso, cancelamento e resultados ao worker. Flask e Celery não fazem parte dos contratos dos pacotes de algoritmos. Os valores finais dos objetivos e a representação da solução são persistidos pelo fluxo da aplicação, não pelo notebook.

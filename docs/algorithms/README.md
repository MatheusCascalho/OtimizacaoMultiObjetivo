# Padrão de desenvolvimento dos algoritmos

Este documento define a organização e os contratos dos algoritmos de otimização do projeto. Os pacotes Python devem ser independentes dos adaptadores Flask, Celery, banco de dados e armazenamento de arquivos. A API e os workers chamam serviços de aplicação; esses serviços carregam os dados do problema e delegam a análise/otimização aos pacotes de algoritmos.

## Organização dos módulos

Adotar a seguinte estrutura como referência para o código Python:

```text
src/
  monoobjective_algorithms/
    __init__.py
    interfaces.py
    tsp/
      __init__.py
      instance.py
      heuristics/
      exact/
  multiobjective_algorithms/
    __init__.py
    dominance.py
    epsilon_constraint.py
notebooks/
data/
  instances/
tests/
  monoobjective_algorithms/
  multiobjective_algorithms/
```

- **`monoobjective_algorithms`** contém heurísticas e solvers exatos, organizados em um subpacote por família de problemas. Cada implementação procura uma solução para um pedido monoobjetivo. O contrato compartilhado fica na raiz do pacote; tipos e detalhes específicos do problema ficam em seu subpacote (por exemplo, `tsp`).
- **`multiobjective_algorithms`** contém operações reutilizáveis de análise multiobjetivo, como dominância, e métodos de geração de fronteira, como ε-restrição. O pacote recebe um solver pela interface comum, sem importar ou selecionar implementações concretas de TSP ou de outra família.
- **`notebooks/`** guarda notebooks de experimentação, execução reproduzível e visualização. Notebooks orquestram os pacotes, mas não são o local das implementações reutilizáveis nem a dependência dos serviços da aplicação.
- **`data/instances/`** guarda instâncias de teste versionáveis e não sensíveis. Arquivos enviados por usuários e dados de execução não devem ser gravados nessa pasta: seguem o fluxo de armazenamento da aplicação descrito na especificação do workflow de instâncias.
- **`tests/`** espelha os pacotes e mantém testes unitários de contratos, algoritmos e análise. Testes não devem depender de notebooks ou de serviços externos.

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

## Contrato multiobjetivo e fluxo de execução

Os métodos multiobjetivo recebem a instância, as definições dos objetivos (identificador, direção e unidade), os parâmetros do método e uma implementação de `MonoobjectiveSolver`. Eles não conhecem a representação interna da instância nem chamam diretamente uma heurística ou biblioteca de solver. O solver converte o pedido padronizado para o modelo específico da família.

Para ε-restrição, o método escolhe um objetivo principal por chamada e varia os limites dos outros objetivos, invocando `solve` repetidamente pela interface. Soluções retornadas são agregadas, deduplicadas e filtradas pela análise de dominância. Uma solução domina outra quando não é pior em nenhum objetivo, respeitando a direção de cada objetivo, e é estritamente melhor em pelo menos um; qualquer tolerância numérica deve ser explícita e aplicada consistentemente.

O serviço de aplicação valida problema, solver, capacidades e parâmetros, executa o método e entrega progresso, cancelamento e resultados ao worker. Flask e Celery não fazem parte dos contratos dos pacotes de algoritmos. Os valores finais dos objetivos e a representação da solução são persistidos pelo fluxo da aplicação, não pelo notebook.

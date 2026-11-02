# Laboratório de Trabalhos Computacionais

Ambiente para visualização de resultados e interação com modelos de otimização multiobjetivo desenvolvidos na disciplina de Otimização Multiobjetivo da UFMG, no segundo semestre de 2026.

## Visão geral

A proposta do projeto é permitir que usuários:

- selecionem um tipo de problema de otimização;
- criem instâncias a partir do envio de arquivos de entrada;
- executem os modelos e interpretem os resultados por meio de gráficos e tabelas.

## Arquitetura e tecnologias previstas

O sistema separa interface, serviços da aplicação e algoritmos para manter baixo acoplamento:

- **Front-end:** HTML, CSS e JavaScript vanilla, sem frameworks; interface para seleção de problemas, envio de arquivos e visualização dos resultados.
- **API e serviços da aplicação:** Flask para expor os serviços de execução dos modelos e gerenciar os dados das instâncias; Pydantic para especificação e validação dos dados; SQLite como banco de dados inicial.
- **`monoobjective_algorithms`:** heurísticas e solvers exatos com uma interface comum, separados em subpacotes por família de problemas (por exemplo, TSP).
- **`multiobjective_algorithms`:** ferramentas de análise multiobjetivo e métodos de geração da fronteira de Pareto, agnósticos às implementações concretas de solver.
- **Experimentação e dados:** `notebooks/` para execução e visualização; `data/instances/` para instâncias de teste. Consulte o [padrão de desenvolvimento dos algoritmos](docs/algorithms/README.md).

Pyomo, NumPy e Pandas são opções previstas para modelagem e processamento; Plotly e Seaborn para visualização; Jupyter para experimentação. As implementações concretas e dependências serão definidas conforme os problemas e algoritmos forem integrados.

A arquitetura deve seguir os princípios de Clean Architecture e manter baixo acoplamento para facilitar a substituição do banco de dados, do solver e do framework da API.

## Execução local com Docker

O container atual serve o mockup estático do front-end. A API, o banco de dados e os solvers ainda não estão integrados.

Requisitos: Docker Engine e Docker Compose.

```bash
docker compose up --build
```

Depois, acesse [http://localhost:8080](http://localhost:8080). Para usar outra porta local, defina `PARETOLAB_PORT`, por exemplo: `PARETOLAB_PORT=8090 docker compose up --build`.

Para encerrar, use `Ctrl+C` e depois execute `docker compose down`.

## Testes e desenvolvimento

Os testes unitários estão previstos para utilizar Pytest. Também está prevista a adoção de agentes especializados por módulo e de um agente coordenador para delegar tarefas; seus papéis e fluxos serão detalhados conforme o projeto evoluir.

## Documentação

- [Visão e diretrizes do projeto](visao.md)
- [Feature: workflow de instâncias](docs/features/workflow_instance/README.md)
- [Modelos de otimização](docs/UFMG/)
- [Bibliografia](docs/papers/)

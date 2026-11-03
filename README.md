# Laboratório de Trabalhos Computacionais

Ambiente para visualização de resultados e interação com modelos de otimização multiobjetivo desenvolvidos na disciplina de Otimização Multiobjetivo da UFMG, no segundo semestre de 2026.

## Visão geral

A proposta do projeto é permitir que usuários:

- selecionem um tipo de problema de otimização;
- criem instâncias a partir do envio de arquivos de entrada;
- executem os modelos e interpretem os resultados por meio de gráficos e tabelas.

## Arquitetura e tecnologias

O sistema separa interface, serviços da aplicação e algoritmos para manter baixo acoplamento:

- **Front-end:** HTML, CSS e JavaScript vanilla, sem frameworks; interface para seleção de problemas, envio de arquivos e visualização dos resultados.
- **API e serviços da aplicação:** Flask para expor os serviços de execução dos modelos e gerenciar os dados das instâncias; Pydantic para especificação e validação dos dados; PostgreSQL como banco de dados principal.
- **`optimization_problems`:** modelos matemáticos implementados em Pyomo, organizados por família de problema e com uma classe builder dedicada para cada modelo.
- **`monoobjective_algorithms`:** heurísticas e solvers exatos com uma interface comum, separados em subpacotes por família de problemas (por exemplo, TSP).
- **`multiobjective_algorithms`:** ferramentas de análise multiobjetivo e métodos de geração da fronteira de Pareto, agnósticos às implementações concretas de solver.
- **Experimentação e dados:** `notebooks/` para execução e visualização; `data/instances/` para instâncias de teste. Consulte o [padrão de desenvolvimento dos algoritmos](docs/algorithms/README.md).

O fluxo local implementado cobre o TSP biobjetivo de tempo e distância: catálogo JSON, upload validado de matrizes CSV, persistência PostgreSQL, armazenamento S3 compatível via SILO, execução Celery/Redis com `RandomHeuristic`, resultados paginados e notificações. A heurística aproxima a fronteira por amostragem e não garante o ótimo global.

## Execução local com Docker

O Compose inicia o frontend, API Flask, worker Celery, PostgreSQL, Redis e armazenamento de objetos S3 compatível SILO. O fluxo de criação, análise prévia, execução, cancelamento, resultados e notificações está conectado entre interface e API.

Requisitos: Docker Engine e Docker Compose. Copie `.env.example` para `.env` e substitua os valores `replace-this-*` por credenciais de desenvolvimento locais antes de iniciar os serviços. Mantenha `POSTGRES_PASSWORD` igual à senha da `DATABASE_URL` e `SILO_ROOT_USER`/`SILO_ROOT_PASSWORD` iguais às credenciais `S3_ACCESS_KEY`/`S3_SECRET_KEY`. Não compartilhe essas credenciais nem as versione.

```bash
docker compose up --build
```

Depois, acesse ParetoLab em [http://127.0.0.1:8080](http://127.0.0.1:8080) e o healthcheck da API em [http://127.0.0.1:5000/health/ready](http://127.0.0.1:5000/health/ready). As portas publicadas ficam vinculadas somente ao loopback; PostgreSQL, Redis e SILO não publicam portas no host. Para usar outras portas locais, defina `PARETOLAB_PORT` ou `PARETOLAB_API_PORT` no `.env`.

Para encerrar, use `Ctrl+C` e depois execute `docker compose down`.

Os dados do PostgreSQL e do SILO ficam em volumes Docker persistentes. Para aplicar migrações manualmente, execute `docker compose exec api alembic upgrade head`; na inicialização da API as migrações são aplicadas automaticamente antes do servidor iniciar.

O frontend usa o endpoint padrão `http://127.0.0.1:5000/api/v1`; origens CORS são limitadas a loopback. A versão v1 é single-user local e não possui autenticação; não exponha os serviços à rede.

## Testes e desenvolvimento

Os testes unitários utilizam Pytest. Instale as dependências de desenvolvimento com `pip install -r requirements-dev.txt` e execute `PYTHONPATH=src pytest`.

## Documentação

- [Visão e diretrizes do projeto](visao.md)
- [Feature: workflow de instâncias](docs/features/workflow_instance/README.md)
- [Modelos de otimização](docs/UFMG/)
- [Bibliografia](docs/papers/)

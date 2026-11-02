# Laboratório de Trabalhos Computacionais

Ambiente para visualização de resultados e interação com modelos de otimização multiobjetivo desenvolvidos na disciplina de Otimização Multiobjetivo da UFMG, no segundo semestre de 2026.

## Visão geral

A proposta do projeto é permitir que usuários:

- selecionem um tipo de problema de otimização;
- criem instâncias a partir do envio de arquivos de entrada;
- executem os modelos e interpretem os resultados por meio de gráficos e tabelas.

## Arquitetura e tecnologias previstas

O sistema será organizado em três módulos principais:

- **Front-end:** HTML, CSS e JavaScript vanilla, sem frameworks; interface para seleção de problemas, envio de arquivos e visualização dos resultados.
- **API:** Flask para expor os serviços de execução dos modelos e gerenciar os dados das instâncias; Pydantic para especificação e validação dos dados; SQLite como banco de dados inicial.
- **Modelos e análise:** Pyomo para modelagem da otimização; NumPy e Pandas para processamento de dados; Plotly e Seaborn para visualizações; Jupyter notebooks para experimentação local.

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

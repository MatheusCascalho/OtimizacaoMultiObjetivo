# Laboratório de trabalhos computacionais

O presente projeto tem como objetivo desenvolver um ambiente para vizualização de resultados
e interação com os modelos de otimização desenvolvidos na disciplina de otimização multiobjetivo 
da UFMG, segundo semestre de 2026.

O repositório consiste nos seguintes módulos principais:

* Front-end: 
    * RESPONSABILIDADE:
        * Permitir que o usuário selecione o tipo de problema que deseja analizar
        * Permitir a criação de instâncias por meio do upload de arquivos base;
        * Renderizar os resultados do modelo e gráficos e tabelas adequadas para a melhor interpretação por parte do 
        usuário;
    * TECNOLOGIAS UTILIZADAS:
        * HTML, CSS, JAVASCRIPT VANILLA
        * Não utilizar frameworks;
* API:
    * RESPONSABILIDADE:
        * expor os endpoints que chamam os serviços que executam os modelos de otimização;
        * gerenciar os dados de cada instância de otimização;
    * TECNOLOGIAS UTILIZADAS:
        * Flask API;
        * Banco de dados PostgreSQL;
        * Pydantic para especificação de objetos;
* DOMAIN:
    * RESPONSABILIDADE:
        * Implementar os modelos de otimização;
        * Implementar serviços auxiliares utilizados pela API;
        * 
    * TECNOLOGIAS UTILIZADAS:
        * Pyomo para desenvolvimento dos modelos;
        * Numpy
        * Pandas
        * Plotly e Seaborn; 
        * Jupyter notebook para testes locais dos modelos;

O projeto deve ser desenvolvido utilizando Clean Arch, e deve permitir uma fácil substituição dos seguintes componentes:

* Banco de Dados;
* Solver de otimização;
* framework WEB;

Os modelos de otimização estão descritos na pasta /docs/UFMG, e a bibliografia dos modelos em /docs/papers.
O projeto deve possuir uma pasta de testes unitários, utilizando Pytest como framework de testes;
O projeto deve implementar agentes especializados em cada módulo, bem como um agente gerenciador que saiba delegar tarefas
para os agentes especialistas. 

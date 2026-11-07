# Ampliação e detalhe no gráfico de evolução

**Período coberto:** 06/11/2026

**Origem:** pedido para ajustar a visualização do gráfico de evolução das métricas, com ampliação e detalhe ao passar o cursor. Continua o mesmo dia do relatório `docs/dev_report/2026-11-06-REP02-selecao-algoritmo-curvas.md`.

## O que foi pedido

Permitir que o usuário amplie os gráficos de evolução do hipervolume e do espalhamento Δ e veja o detalhe de cada ponto com hover.

## Decisões seguidas

- Cada figura tem o botão "Ampliar gráfico" / "Recolher gráfico", com `aria-pressed`. A figura ampliada ocupa a largura da seção e a área do desenho passa a `min(62vh, 520px)`. A outra figura permanece abaixo, na altura original, e também pode ser ampliada.
- Sem curvas, o botão fica desabilitado e uma figura ampliada volta ao tamanho normal.
- O tooltip reutiliza `.chart-tooltip`. O texto traz o rótulo da curva, o eixo de amostragens acumuladas e a média do indicador. O ponto mais próximo, até 14 px, recebe um anel amarelo.
- A geometria do hover é a mesma do desenho, em `quality_evolution.js`. O redesenho do destaque não recria a legenda.

## Artefatos

Criado:

- `docs/dev_report/2026-11-06-REP03-grafico-evolucao-hover.md`

Modificados:

- `frontend/mockups/index.html`
- `frontend/mockups/styles.css`
- `frontend/mockups/app.js`
- `frontend/mockups/quality_evolution.js`
- `tests/frontend/test_quality_evolution.js`

## Verificações

- `docker run --rm -v … node:22-alpine node --test tests/frontend/test_quality_evolution.js`: 9 testes passaram. O host não tem `node`; o teste usou a imagem `node:22-alpine`.
- A imagem `paretolab` foi reconstruída e o container recriado. Na primeira imagem, os canvas tinham perdido a classe `quality-evolution-chart` e o desenho passava da área de 168 px. A classe voltou antes da verificação que segue.
- No navegador, em `http://127.0.0.1:8080`, a instância "TSP BIOBJETIVO MULTIFRONTEIRA" mostra cinco curvas NeuroLKH em cada figura. Ampliar o hipervolume troca o botão para "Recolher gráfico", `aria-pressed` verdadeiro, e a área passa de 168 px para 520 px. O espalhamento continua em 168 px, na coluna de baixo.
- O hover no último ponto da rodada 5 mostrou "NeuroLKH · rodada 5", "Amostragens acumuladas na rodada: 50" e "Média do hipervolume: 0.69". Ao sair do gráfico, o tooltip some e recolher devolve a altura de 168 px.
- Com viewport de layout de 360 px, o título e o botão ficam em coluna, o tooltip da rodada 1 no prefixo 30 permanece dentro da tela e o gráfico de espalhamento continua visível abaixo.

## Limitações

Não houve commit. A API e o worker não foram reconstruídos nesta etapa. O anel de destaque é amarelo, a mesma cor da curva da rodada 4, então nesse marcador o contraste do anel é menor.

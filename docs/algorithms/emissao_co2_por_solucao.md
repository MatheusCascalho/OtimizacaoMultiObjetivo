# Critério de estimativa de emissão de CO2 por solução

## Objetivo e escopo

Este documento descreve como o ParetoLab estima a emissão de CO2 de uma rota
do TSP biobjetivo e como interpretar o fator de emissão dependente da
velocidade. A estimativa complementa a análise de soluções; ela não é um
objetivo usado pelo otimizador para gerar ou selecionar a fronteira de Pareto.

O cálculo é determinístico para uma rota e as matrizes de distância e tempo
fornecidas. Na tabela da análise de robustez, os valores de emissão são
associados à rota pelo identificador da solução. A simulação de robustez
perturba os tempos para avaliar métricas de tempo, mas não reotimiza a rota nem
recalcula a emissão em cada cenário.

## Dados e unidades

O cálculo usa:

- distância de cada arco em quilômetros, obtida da matriz de distância;
- tempo nominal de cada arco em horas, obtido da matriz de tempo;
- fator-base de `0,30 kg CO2/km`, usado por padrão.

O fator-base pode ser informado como parâmetro para o cálculo de emissão, mas
deve ser positivo. O valor padrão é uma premissa do modelo, não um fator
universal validado para todo veículo, combustível, carga ou condição de tráfego.

## Fator por velocidade

Para cada arco com distância positiva e tempo positivo, a velocidade estimada é:

```text
velocidade_km_h = distância_km / tempo_h
```

O arco recebe um multiplicador segundo a faixa de velocidade:

| Velocidade estimada | Fator |
|---|---:|
| `0 <= v < 20 km/h` | `1,50` |
| `20 <= v < 40 km/h` | `1,15` |
| `40 <= v < 70 km/h` | `1,00` |
| `v >= 70 km/h` | `1,20` |

Os limites inferiores pertencem à faixa indicada. Por exemplo, exatamente
`40 km/h` usa fator `1,00`, e exatamente `70 km/h` usa `1,20`.

O fator não tem unidade. Ele multiplica a emissão-base do trecho. Nesse modelo,
velocidades baixas podem elevar o fator, enquanto a faixa de 40 a menos de
70 km/h é a referência de fator `1,00`. Velocidades a partir de 70 km/h usam
`1,20`; portanto, não se presume que acelerar sempre reduza a emissão.

## Emissão por arco e por rota

Para um arco `a`, a emissão estimada é:

```text
CO2_a_kg = distância_a_km * fator_base_kg_por_km * fator_velocidade_a
```

A emissão total da solução é a soma sobre os arcos percorridos:

```text
CO2_total_kg = Σ CO2_a_kg
```

O fator de emissão de velocidade mostrado para a rota é a média dos fatores
dos arcos ponderada pelas distâncias:

```text
fator_total =
    CO2_total_kg / (distância_total_km * fator_base_kg_por_km)
```

Como o mesmo fator-base é aplicado a todos os arcos, essa expressão equivale
a:

```text
fator_total = Σ (distância_a_km * fator_velocidade_a) / Σ distância_a_km
```

Assim, trechos mais longos têm maior peso. Um fator total de `1,20` significa
que, sob as premissas do modelo, a emissão estimada é 20% maior que a emissão
calculada usando apenas o fator-base para a mesma distância. Um fator menor que
`1,00` representa emissão abaixo dessa referência.

### Exemplo

Considere uma rota com três trechos de `10 km` cada, cujos fatores de
velocidade são, respectivamente, `1,50`, `1,00` e `1,20`. Com fator-base de
`0,30 kg/km`:

```text
emissão-base = (10 + 10 + 10) * 0,30 = 9,00 kg CO2
CO2_total    = (10 * 0,30 * 1,50) + (10 * 0,30 * 1,00)
               + (10 * 0,30 * 1,20)
             = 11,10 kg CO2
fator_total  = 11,10 / 9,00 = 1,233...
```

O fator total é, portanto, aproximadamente `1,233`, ou cerca de 23,3% acima
da referência-base para essa distância.

## Casos sem velocidade calculável

Arcos com distância não positiva não contribuem para a soma da emissão. Se o
tempo de um arco com distância positiva for zero ou negativo, sua velocidade
não é conhecida; o cálculo usa fator neutro `1,00` para esse trecho e o conta
como velocidade desconhecida. A resposta da API informa essa quantidade no
campo `unknown_speed_arcs`.

Quando a distância total resulta em emissão-base zero, o fator total não é
definido e a API o retorna como indisponível. Rotas ou valores incompatíveis
com as matrizes são rejeitados pelo cálculo, em vez de receberem uma emissão
fictícia.

## Interpretação na análise de robustez

A tabela de robustez apresenta, por solução:

- **CO2 (kg):** emissão total estimada para a rota, com duas casas decimais na
  apresentação;
- **Fator de emissão de velocidade:** razão entre a emissão total e a
  referência-base da rota, exibida com três casas decimais.

O fator auxilia a interpretar como as velocidades estimadas alteram a emissão
em relação à referência-base, mas não substitui o valor em quilogramas. Para
comparar emissões totais entre rotas, considere também a distância: uma rota
mais longa pode emitir mais mesmo com fator total menor.

Os números são estimativas baseadas nas matrizes e nos parâmetros adotados.
Não representam uma medição de escapamento, um inventário completo de ciclo de
vida, nem uma previsão calibrada para um veículo específico. A análise de
robustez de tempo tampouco transforma essa estimativa em emissão estocástica.

## Implementação

A implementação do cálculo está em
[`src/optimization_problems/tsp/emission.py`](../../src/optimization_problems/tsp/emission.py).
Os resumos por solução são expostos pela API em
[`src/api/routes/emission.py`](../../src/api/routes/emission.py) e associados
à tabela de robustez pelo identificador da solução no frontend.

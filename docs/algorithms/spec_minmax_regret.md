# Especificação: Min-max regret normalizado a partir da tabela de métricas

## Objetivo

Escolher, entre as soluções da tabela, aquela cujo **pior arrependimento relativo** (entre distância e tempo) é o menor.

## Colunas usadas da tabela

| Coluna | Uso |
|---|---|
| Distância ($D_k$) | Regret de distância |
| Média | Referência de tempo ($T_{ref}$) |
| Regret médio | Regret de tempo (visão média) |
| Regret P95 | Regret de tempo (visão de cenários ruins) |

## Passo a passo

### 1. Remover soluções dominadas (opcional, recomendado)

Retire soluções com tempo igual ou pior e distância maior que outra (ex.: S8 em relação a S7, S10 em relação a S9). Elas não mudam o resultado aqui, mas poluem o ranking.

### 2. Definir as referências

$$
D_{min} = \min_k D_k, \qquad T_{ref} = \min_k \text{Média}_k
$$

Na tabela: $D_{min}=1223{,}6$ km (S1) e $T_{ref}=17{,}91$ h (S14).

### 3. Regret normalizado de distância

$$
r^D_k = \frac{D_k - D_{min}}{D_{min}}
$$

### 4. Regret normalizado de tempo

$$
r^{T}_k = \frac{\text{Regret médio}_k}{T_{ref}}
\qquad\text{(versão média)}
$$

$$
r^{T,95}_k = \frac{\text{Regret P95}_k}{T_{ref}}
\qquad\text{(versão cenários ruins)}
$$

### 5. Pior dos dois (score min-max)

$$
\text{Score}_k = \max\big(r^D_k,\ r^T_k\big)
\qquad
\text{Score}^{95}_k = \max\big(r^D_k,\ r^{T,95}_k\big)
$$

### 6. Escolher a solução

$$
k^* = \arg\min_k \text{Score}_k
$$

Reporte as duas versões (média e P95). A solução mais robusta é a que vence nas duas.

## Resultado com a tabela fornecida

| Solução | $r^D$ | $r^T$ (média) | Score | $r^{T,95}$ | Score P95 |
|---|---|---|---|---|---|
| S1 | 0,0% | 27,6% | 27,6% | 31,5% | 31,5% |
| S2 | 0,6% | 18,1% | 18,1% | 21,7% | 21,7% |
| S3 | 2,9% | 14,3% | 14,3% | 17,7% | 17,7% |
| S4 | 3,6% | 13,7% | 13,7% | 17,1% | 17,1% |
| S5 | 6,2% | 11,4% | 11,4% | 14,5% | 14,5% |
| S6 | 6,4% | 9,8% | 9,8% | 13,1% | 13,1% |
| **S7** | **7,1%** | **6,4%** | **7,1%** | **9,4%** | **9,4%** |
| S8 | 10,3% | 6,4% | 10,3% | 9,4% | 10,3% |
| S9 | 11,6% | 4,7% | 11,6% | 7,7% | 11,6% |
| S10 | 14,7% | 4,7% | 14,7% | 7,8% | 14,7% |
| S11 | 15,3% | 3,6% | 15,3% | 6,7% | 15,3% |
| S12 | 15,4% | 2,5% | 15,4% | 5,3% | 15,4% |
| S13 | 16,2% | 2,0% | 16,2% | 4,9% | 16,2% |
| S14 | 17,7% | 0,3% | 17,7% | 1,8% | 17,7% |

**Conclusão:** S7 minimiza o pior regret nas duas versões (7,1% na média; 9,4% no P95).

## Ressalvas

- **Normalização aproximada do tempo:** o ideal é calcular, em cada cenário, $\big(T_k^{(n)}-\min_l T_l^{(n)}\big)/\min_l T_l^{(n)}$ e então tirar a média e o P95. Dividir o regret médio por $T_{ref}$ (a menor média) é uma boa aproximação, porque o tempo mínimo varia pouco entre cenários.
- **Depende do conjunto:** os regrets são relativos às soluções existentes. Se o conjunto mudar, recalcule.
- **Critério conservador:** favorece soluções de meio-termo. Se o decisor prioriza só um objetivo, ele não é o mais adequado.
- **Sensibilidade:** repita o cálculo com outros níveis de incerteza (CV, ρ) para verificar se S7 continua vencendo.
- **Arcos de tempo zero:** se forem dados ausentes, corrija-os antes, pois alteram os tempos e, portanto, os regrets.

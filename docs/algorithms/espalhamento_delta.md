O **indicador \\(\Delta\\) (métrica Delta ou métrica de espalhamento)** foi proposto por Deb et al. (2002) para avaliar a **diversidade** de um conjunto aproximado \\(\mathcal{A}\\), medindo simultaneamente a **uniformidade do espaçamento** entre soluções consecutivas e a **extensão/cobertura** da fronteira em relação aos pontos extremos.

---

### 1. Fórmula Matemática

A definição presente no material para um problema com \\(m\\) objetivos é dada por:

\\[
\Delta = \frac{\sum_{i=1}^{m} d_i^e + \sum_{i=1}^{|\mathcal{A}|} |d_i - \bar{d}|}{\sum_{i=1}^{m} d_i^e + |\mathcal{A}| \bar{d}}
\\]

Onde:
* **\\(m\\):** número de objetivos do problema (no seu caso, \\(m = 2\\): tempo e distância).
* **\\(|\mathcal{A}|\\):** quantidade de soluções não dominadas no conjunto aproximado \\(\mathcal{A}\\).
* **\\(d_i^e\\):** distância euclidiana entre a solução extrema do conjunto aproximado \\(\mathcal{A}\\) e a solução extrema correspondente na fronteira ótima \\(\mathcal{A}^*\\) para o \\(i\\)-ésimo objetivo.
* **\\(d_i\\):** distância euclidiana entre soluções consecutivas adjacentes dentro do conjunto \\(\mathcal{A}\\).
* **\\(\bar{d}\\):** distância média entre as soluções consecutivas de \\(\mathcal{A}\\), calculada como:
  \\[
  \bar{d} = \frac{1}{|\mathcal{A}| - 1} \sum_{i=1}^{|\mathcal{A}| - 1} d_i
  \\]

---

### 2. Passo a Passo de Cálculo (Para 2 Objetivos)

1. **Ordenar as soluções:** Ordene os pontos de \\(\mathcal{A}\\) em ordem crescente do primeiro objetivo (\\(f_1\\)).
2. **Calcular as distâncias consecutivas (\\(d_i\\)):** Calcule a distância euclidiana entre cada par de soluções vizinhas:
   \\[
   d_i = \sqrt{(f_1^{(i+1)} - f_1^{(i)})^2 + (f_2^{(i+1)} - f_2^{(i)})^2}, \quad \text{para } i = 1, \dots, |\mathcal{A}| - 1
   \\]
3. **Calcular a média (\\(\bar{d}\\)):** Some todos os \\(d_i\\) e divida por \\(|\mathcal{A}| - 1\\).
4. **Calcular as distâncias aos extremos (\\(d_1^e\\) e \\(d_2^e\\)):** 
   * Localize os pontos extremos da fronteira de referência \\(\mathcal{A}^*\\) (o ponto de menor tempo e o ponto de menor distância).
   * Calcule a distância de cada um deles até o extremo correspondente encontrado em \\(\mathcal{A}\\).
5. **Aplicar a fórmula:** Some as parcelas no numerador e denominador conforme a equação.

---

### 3. Interpretação do Valor
* **\\(\Delta = 0\\):** Representa a distribuição perfeita. Significa que as distâncias consecutivas são idênticas (\\(d_i = \bar{d}\\), logo \\(|d_i - \bar{d}| = 0\\)) e que as soluções abrangem perfeitamente os limites extremos da fronteira verdadeira (\\(d_i^e = 0\\)).
* **Valores maiores de \\(\Delta\\):** Indicam pior diversidade — seja por concentração/aglomeração desigual dos pontos em algumas regiões ou por não alcançar a extensão completa dos extremos.

---

### Exemplo em Python

```python
import numpy as np

def calcular_delta(A, extremos_ref):
    """
    A: array-like de shape (N, 2) com as soluções obtidas.
    extremos_ref: array-like de shape (2, 2) contendo [extremo_f1, extremo_f2] da referência.
    """
    pts = np.array(A)
    ext_ref = np.array(extremos_ref)
    
    # 1. Ordenar por f1
    pts = pts[np.argsort(pts[:, 0])]
    N = len(pts)
    
    if N < 2:
        return 1.0  # Sem diversidade viável para cálculo de distâncias consecutivas
        
    # 2. Distâncias euclidianas consecutivas
    diffs = pts[1:] - pts[:-1]
    d = np.linalg.norm(diffs, axis=1)
    d_bar = np.mean(d)
    
    # 3. Distâncias aos extremos de referência
    # d1_e: distância do primeiro ponto de A ao extremo correspondente de menor f1
    # d2_e: distância do último ponto de A ao extremo correspondente de menor f2
    d1_e = np.linalg.norm(pts - ext_ref)
    d2_e = np.linalg.norm(pts[-1] - ext_ref)
    soma_de = d1_e + d2_e
    
    # 4. Fórmula do indicador Delta
    numerador = soma_de + np.sum(np.abs(d - d_bar))
    denominador = soma_de + (N - 1) * d_bar
    
    return numerador / denominador
```

*(Observação: Como o seu TSP não possui fronteira analítica exata, adote como `extremos_ref` os pontos com o menor tempo e a menor distância encontrados na união de todas as rodadas).*
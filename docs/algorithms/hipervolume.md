A implementação do **indicador S-metric (Hipervolume / \\(HV\\))** parte da definição apresentada no material: ele calcula o volume do espaço de objetivos delimitado pelo conjunto de soluções não dominadas \\(\mathcal{A}\\) e um ponto de referência \\(r\\):

\\[\text{HV}(\mathcal{A}) = \text{vol}\left( \bigcup_{y_i \in \mathcal{A}} [y_i, r] \right)\\]

Ao contrário de métricas que exigem o conhecimento prévio da fronteira ótima \\(\mathcal{A}^*\\) (como \\(GD\\), \\(IGD\\) e \\(\Delta\\)), o Hipervolume depende apenas do **conjunto candidato \\(\mathcal{A}\\)** e da escolha de um **ponto de referência**.

A seguir, apresenta-se o roteiro estruturado de implementação considerando um problema de minimização com dois objetivos (onde o cálculo é analítico e intuitivo) e como ele se estende para mais dimensões.

---

### Passo 1: Filtragem e Normalização do Conjunto Candidato
1. **Garantir não dominância:** Certifique-se de que o conjunto candidato contenha apenas pontos não dominados entre si.
2. **Normalização (recomendado):** Caso os objetivos tenham ordens de grandeza distintas (ex.: um objetivo varia de 0 a 1 e outro de 1.000 a 10.000), normalize os valores para o intervalo \\(\\) para evitar que um único objetivo domine o hipervolume.

---

### Passo 2: Definição do Ponto de Referência (\\(r\\))
O ponto de referência deve ser dominado por todos os pontos do conjunto candidato. 
* Para **minimização**, escolha \\(r = (r_1, r_2, \dots, r_m)\\) tal que \\(r_i > \max_{a \in \mathcal{A}}(f_i(a))\\). 
* Uma convenção prática usual na literatura é adotar \\(r_i = \max(f_i) + \epsilon\\) (ou \\(1.1 \times \max(f_i)\\)), mantendo o mesmo ponto \\(r\\) fixo para todos os algoritmos que estão sendo comparados.

---

### Passo 3: Algoritmo de Cálculo

#### Caso com 2 Objetivos (\\(m = 2\\))
Em duas dimensões, o hipervolume corresponde à soma das áreas de retângulos não sobrepostos formados entre as soluções e o ponto de referência \\(r = (r_1, r_2)\\):

1. Ordene os pontos de \\(\mathcal{A}\\) em ordem crescente do primeiro objetivo \\(f_1\\):
   \\[a^{(1)}, a^{(2)}, \dots, a^{(k)}, \quad \text{onde } f_1(a^{(1)}) < f_1(a^{(2)}) < \dots < f_1(a^{(k)})\\]
   Como os pontos são não dominados, o segundo objetivo estará necessariamente em ordem decrescente:
   \\[f_2(a^{(1)}) > f_2(a^{(2)}) > \dots > f_2(a^{(k)})\\]
2. Divida a área total em faixas retangulares independentes:
   * **Largura** da faixa \\(i\\): \\(f_1(a^{(i+1)}) - f_1(a^{(i)})\\) (para o último ponto, a largura vai até \\(r_1 - f_1(a^{(k)})\\)).
   * **Altura** da faixa \\(i\\): \\(r_2 - f_2(a^{(i)})\\).
3. Some a área de cada retângulo:
   \\[\text{HV}(\mathcal{A}) = (f_1(a^{(2)}) - f_1(a^{(1)})) \cdot (r_2 - f_2(a^{(1)})) + \dots + (r_1 - f_1(a^{(k)})) \cdot (r_2 - f_2(a^{(k)}))\\]

---

### Exemplo de Implementação em Python (2D)

```python
import numpy as np

def calcular_hipervolume_2d(pontos, ref_point):
    """
    pontos: array-like de shape (N, 2) com as soluções do conjunto A.
    ref_point: tupla ou lista [r1, r2] que é dominada por todos os pontos.
    """
    # 1. Converter para array NumPy
    pts = np.array(pontos)
    
    # 2. Filtrar apenas soluções que dominam o ponto de referência
    validos = pts[(pts[:, 0] <= ref_point) & (pts[:, 1] <= ref_point)]
    if len(validos) == 0:
        return 0.0

    # 3. Ordenar os pontos em ordem crescente de f1
    idx = np.argsort(validos[:, 0])
    pts_ord = validos[idx]

    # 4. Cálculo iterativo da soma das áreas retangulares
    hv = 0.0
    for i in range(len(pts_ord)):
        # Largura: distância em f1 até o próximo ponto (ou até ref_point)
        if i < len(pts_ord) - 1:
            largura = pts_ord[i + 1, 0] - pts_ord[i, 0]
        else:
            largura = ref_point - pts_ord[i, 0]
        
        # Altura: distância de f2 até o ponto de referência
        altura = ref_point - pts_ord[i, 1]
        
        hv += largura * altura

    return hv

# Exemplo de teste (minimização):
# Duas frentes candidatas avaliadas com o mesmo ponto de referência
ref = [1.1, 1.1]
frente_A = [[0.2, 0.8], [0.4, 0.5], [0.7, 0.2]]
frente_B = [[0.3, 0.85], [0.5, 0.6], [0.8, 0.3]]

hv_A = calcular_hipervolume_2d(frente_A, ref)
hv_B = calcular_hipervolume_2d(frente_B, ref)

print(f"HV(A) = {hv_A:.4f}")
print(f"HV(B) = {hv_B:.4f}")
```

---

### Extensão para Três ou Mais Objetivos (\\(m \ge 3\\))
Para \\(m > 2\\), os hipervolumes parciais se sobrepõem no espaço multidimensional. A implementação manual torna-se combinatorialmente complexa (*Klee's Measure Problem*). 

Na prática, recomenda-se:
1. **Algoritmos exatos clássicos:** Utilizar o algoritmo **HSO** (*Hypervolume by Slicing Objectives*) ou algoritmos recursivos baseados em partição dimensional (ex.: biblioteca `pygmo` ou `pymoo` em Python).
2. **Aproximação por Monte Carlo:** Para muitos objetivos (muitos-objetivos, \\(m > 5\\)), amostram-se aleatoriamente \\(N\\) pontos uniformes na caixa delimitada pelo ponto ideal e pelo ponto de referência, calculando o Hipervolume como a fração de amostras dominadas pelo conjunto candidato multiplicada pelo volume total da caixa delimitadora.


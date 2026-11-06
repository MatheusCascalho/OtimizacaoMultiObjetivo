# Solução Utópica e Antiutópica em Problemas Biobjetivo

> **Público-alvo:** agente (humano ou de IA) responsável por implementar o cálculo dos pontos utópico e antiutópico em um problema de otimização multiobjetivo com **2 funções objetivo (F.O.)**.
>
> **Escopo:** definições, contexto teórico, algoritmo, pseudocódigo, casos de borda, exemplo numérico e critérios de validação.

---

## 1. Contexto: problema multiobjetivo com 2 F.O.

### 1.1 Formulação geral

Um problema biobjetivo (convenção de **minimização**) é escrito como:

```
min  F(x) = ( f1(x), f2(x) )
s.a. x ∈ X
```

onde:

| Símbolo | Significado |
|---|---|
| `x` | vetor de variáveis de decisão |
| `X` | região viável (espaço de decisão), definida pelas restrições |
| `f1, f2` | as duas funções objetivo |
| `F(x)` | vetor de objetivos de `x`, um ponto no **espaço dos objetivos** `Z = F(X) ⊂ ℝ²` |

> **Convenção deste documento:** todos os objetivos são de **minimização**. Se algum objetivo for de maximização, converta antes (`f' = -f`) e reverta o sinal apenas na apresentação final. Ver seção 7.

### 1.2 Conceitos necessários

- **Dominância de Pareto:** `x¹` domina `x²` se `fi(x¹) ≤ fi(x²)` para `i = 1, 2` e existe ao menos um `i` com desigualdade estrita.
- **Solução Pareto-ótima (eficiente):** solução viável que não é dominada por nenhuma outra solução viável.
- **Conjunto de Pareto:** conjunto de todas as soluções eficientes (no espaço de decisão).
- **Fronteira de Pareto (frente de Pareto):** imagem do conjunto de Pareto no espaço dos objetivos.
- **Objetivos conflitantes:** quando melhorar `f1` piora `f2` (e vice-versa). Só nesse caso a fronteira de Pareto tem mais de um ponto, e só nesse caso os pontos utópico e antiutópico são distintos.

---

## 2. Definições

### 2.1 Ponto utópico (ideal)

É o ponto no espaço dos objetivos formado pelo **melhor valor possível de cada objetivo, otimizado isoladamente** sobre toda a região viável.

```
z^U = ( z1^U , z2^U )

z1^U = min_{x ∈ X} f1(x)
z2^U = min_{x ∈ X} f2(x)
```

Propriedades:

- Representa o **melhor cenário teórico**, em que os dois objetivos são ótimos simultaneamente.
- **Em geral é inalcançável**: se os objetivos são conflitantes, não existe `x ∈ X` tal que `F(x) = z^U`. Por isso é chamado "utópico".
- Domina (ou é igual a) todos os pontos da fronteira de Pareto.
- Cada componente é um **limite inferior** do respectivo objetivo na fronteira de Pareto.

### 2.2 Ponto antiutópico (nadir)

É o ponto formado pelo **pior valor de cada objetivo ao longo da fronteira de Pareto** (e não sobre toda a região viável).

```
z^N = ( z1^N , z2^N )

z1^N = max_{x ∈ X_P} f1(x)
z2^N = max_{x ∈ X_P} f2(x)
```

onde `X_P` é o conjunto de soluções Pareto-ótimas.

Propriedades:

- Cada componente é um **limite superior** do respectivo objetivo na fronteira de Pareto.
- Junto com `z^U`, define o **retângulo (caixa) que envolve a fronteira de Pareto**.
- Normalmente também é inalcançável.

### 2.3 ⚠️ Atenção: nadir ≠ pior ponto

Existe um ponto diferente, às vezes chamado de **pior ponto** ou **anti-ideal** (*worst point*), que usa o máximo sobre **toda** a região viável:

```
z^W_i = max_{x ∈ X} f_i(x)
```

| Ponto | Máximo tomado sobre | Quando usar |
|---|---|---|
| **Nadir** `z^N` | Conjunto Pareto-ótimo `X_P` | Normalização e escalarização (uso padrão) |
| **Pior** `z^W` | Toda a região viável `X` | Apenas se a especificação pedir explicitamente |

Em geral `z^W ≥ z^N` componente a componente. Usar `z^W` no lugar de `z^N` **superestima** a faixa de variação dos objetivos e distorce a normalização.

> **Decisão de projeto:** neste projeto, "solução antiutópica" significa **ponto nadir** (`z^N`), salvo indicação contrária.

### 2.4 Resumo visual (espaço dos objetivos, minimização)

```
 f2
  ^
  |
z2^N  ●───────────●  ← z^N = (z1^N, z2^N)   [antiutópico / nadir]
  |   │  ╲        │
  |   │    ╲  ←── fronteira de Pareto
  |   │      ╲    │
z2^U  ●───────────●
  |  z^U      (z1^N, z2^U)
  +─────────────────────> f1
     z1^U      z1^N

 z^U = (z1^U, z2^U)  [utópico / ideal]  — canto inferior esquerdo
```

---

## 3. Para que servem (motivação)

| Uso | Como os pontos entram |
|---|---|
| **Normalização dos objetivos** | `f̄i = (fi − ziU) / (ziN − ziU)`, levando cada objetivo para `[0, 1]` na fronteira de Pareto |
| **Métodos de escalarização** | Soma ponderada normalizada, Tchebycheff, programação por compromisso, ε-restrito (para definir o intervalo de `ε`) |
| **Escolha da solução de compromisso** | Selecionar o ponto da fronteira mais próximo de `z^U` ou mais distante de `z^N` |
| **Métricas de qualidade** | Hipervolume (usa `z^N` ou um ponto de referência derivado dele), distância ao ponto ideal |
| **Algoritmos evolutivos** | Normalização adaptativa (ex.: NSGA-III, MOEA/D) |

---

## 4. Como calcular — caso de 2 F.O.

### 4.1 Ponto utópico

Basta resolver **dois problemas mono-objetivo independentes**:

```
(P1)  z1^U = min f1(x)   s.a. x ∈ X        → solução x¹*
(P2)  z2^U = min f2(x)   s.a. x ∈ X        → solução x²*
```

### 4.2 Ponto nadir — abordagem correta para 2 objetivos

Com **exatamente 2 objetivos**, o nadir pode ser obtido de forma **exata** por **otimização lexicográfica**. Isso resolve o principal erro de implementação (seção 4.3).

**Passo A — obter `z2^N` (pior valor de f2 na fronteira):**

```
(L1)  min f1(x)  s.a. x ∈ X                       → valor ótimo z1^U
(L2)  min f2(x)  s.a. x ∈ X,  f1(x) = z1^U         → valor ótimo = z2^N
```

Interpretação: entre todas as soluções que atingem o melhor `f1`, escolhe-se a de melhor `f2`. Esse ponto é eficiente e é o extremo da fronteira com o pior `f2`.

**Passo B — obter `z1^N` (pior valor de f1 na fronteira):**

```
(L3)  min f2(x)  s.a. x ∈ X                       → valor ótimo z2^U
(L4)  min f1(x)  s.a. x ∈ X,  f2(x) = z2^U         → valor ótimo = z1^N
```

**Resultado:**

```
z^U = ( z1^U , z2^U )
z^N = ( z1^N , z2^N )
```

Os dois pontos extremos da fronteira de Pareto são `A = (z1^U, z2^N)` e `B = (z1^N, z2^U)`.

### 4.3 ⚠️ Armadilha: tabela de payoff ingênua

Uma abordagem comum, porém **incorreta em geral**, é:

1. Resolver `min f1` → obter `x¹*`; calcular `f2(x¹*)`.
2. Resolver `min f2` → obter `x²*`; calcular `f1(x²*)`.
3. Definir `z^N = ( f1(x²*), f2(x¹*) )`.

**Problema:** se o `min f1` tiver **múltiplas soluções ótimas** (ótimos alternativos), o solver retorna uma qualquer delas, possivelmente **dominada** (não eficiente), com `f2` pior do que o `f2` da solução eficiente. O resultado é um `z^N` **superestimado**. A otimização lexicográfica (4.2) elimina esse problema porque, entre os ótimos de `f1`, escolhe o de menor `f2`.

> Para 2 objetivos, **use sempre a abordagem lexicográfica**. A tabela de payoff ingênua só é aceitável se houver garantia de ótimo único para cada objetivo.

### 4.4 Alternativa à restrição de igualdade

A restrição `f1(x) = z1^U` pode ser numericamente frágil (solvers trabalham com tolerância; em problemas inteiros ou não lineares a igualdade exata pode tornar a região viável vazia). Alternativas:

**(a) Tolerância:** substituir por `f1(x) ≤ z1^U + δ`, com `δ` muito pequeno (ex.: `1e-6 · max(1, |z1^U|)`).

**(b) Função ponderada lexicográfica aproximada (augmentada):**

```
min  f2(x) + ρ · f1(x)    s.a. x ∈ X       (ρ > 0 muito pequeno, ex.: 1e-6)
```

Cuidado: se `ρ` for grande demais, o resultado deixa de ser lexicográfico; se for pequeno demais, perde-se precisão numérica. Para ordenar `f2` primeiro com desempate por `f1`, use `min f2 + ρ f1`; para `f1` primeiro, `min f1 + ρ f2`.

Prefira a abordagem **(a)** ou a restrição de igualdade exata quando o solver permitir.

---

## 5. Pseudocódigo

```text
FUNÇÃO calcular_utopico_e_nadir(problema):
    # Entrada: problema com f1, f2 (minimização), região viável X
    # Saída: z_U = (z1_U, z2_U), z_N = (z1_N, z2_N)

    # ---- Passo A: extremo que otimiza f1 ----
    z1_U  ← resolver( min f1(x) , x ∈ X )
    z2_N  ← resolver( min f2(x) , x ∈ X , f1(x) ≤ z1_U + δ )

    # ---- Passo B: extremo que otimiza f2 ----
    z2_U  ← resolver( min f2(x) , x ∈ X )
    z1_N  ← resolver( min f1(x) , x ∈ X , f2(x) ≤ z2_U + δ )

    z_U ← (z1_U, z2_U)
    z_N ← (z1_N, z2_N)

    # ---- Validações ----
    SE z1_N < z1_U ou z2_N < z2_U:   ERRO "inconsistência numérica"
    SE z1_N − z1_U ≤ ε ou z2_N − z2_U ≤ ε:
        AVISO "objetivo degenerado / não conflitante" (ver seção 6)

    RETORNAR z_U, z_N
```

### 5.1 Esqueleto em Python (ilustrativo)

A biblioteca de resolução (`solve`) deve ser substituída pelo solver do projeto (SciPy, Pyomo, OR-Tools, Gurobi, CPLEX, etc.).

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ReferencePoints:
    utopian: tuple[float, float]   # (z1_U, z2_U)
    nadir:   tuple[float, float]   # (z1_N, z2_N)

def compute_reference_points(problem, delta: float = 1e-6) -> ReferencePoints:
    """
    Calcula os pontos utópico e antiutópico (nadir) de um problema
    biobjetivo de MINIMIZAÇÃO, via otimização lexicográfica.

    `problem` deve expor:
      - problem.solve(objective, extra_constraints=None) -> (x, valor_do_objetivo)
      - problem.f1(x), problem.f2(x)
    """
    # Passo A: otimiza f1; depois f2 restrito ao ótimo de f1
    _, z1_U = problem.solve(problem.f1)
    _, z2_N = problem.solve(
        problem.f2,
        extra_constraints=[lambda x: problem.f1(x) <= z1_U + delta],
    )

    # Passo B: otimiza f2; depois f1 restrito ao ótimo de f2
    _, z2_U = problem.solve(problem.f2)
    _, z1_N = problem.solve(
        problem.f1,
        extra_constraints=[lambda x: problem.f2(x) <= z2_U + delta],
    )

    if z1_N < z1_U - delta or z2_N < z2_U - delta:
        raise ValueError("Inconsistência: nadir menor que utópico.")

    return ReferencePoints(utopian=(z1_U, z2_U), nadir=(z1_N, z2_N))
```

### 5.2 Normalização (uso típico dos pontos)

```python
def normalize(f_vals, ref: ReferencePoints, eps: float = 1e-12):
    """Leva cada objetivo para [0, 1] sobre a fronteira de Pareto."""
    out = []
    for i, f in enumerate(f_vals):
        rng = ref.nadir[i] - ref.utopian[i]
        out.append((f - ref.utopian[i]) / rng if rng > eps else 0.0)
    return tuple(out)
```

---

## 6. Casos de borda e tratamento

| Situação | Sintoma | Tratamento recomendado |
|---|---|---|
| **Objetivos não conflitantes** | `z^U = z^N` em um ou ambos os eixos; a fronteira é um único ponto | Avisar; evitar divisão por zero na normalização (`range ≤ eps` → usar 0 ou 1) |
| **Ótimos alternativos** | Solver devolve soluções diferentes a cada execução | Garantido pela abordagem lexicográfica (seção 4.2) |
| **Problema inviável** | Solver reporta infactibilidade em qualquer etapa | Abortar com erro claro indicando qual etapa (L1–L4) falhou |
| **Problema ilimitado** | `min fi = −∞` | Abortar; `z^U` não está definido. Exigir limites nas variáveis ou objetivos limitados |
| **Restrição de igualdade inviável por tolerância** | L2/L4 infactível mesmo com L1/L3 factível | Usar `≤ z + δ` (4.4a) e, se preciso, aumentar `δ` |
| **Problema não convexo / não linear** | Solver local retorna ótimo local | Usar solver global ou múltiplas inicializações; o resultado é aproximação |
| **Metaheurística (sem solver exato)** | Não há garantia de ótimo | Ver seção 6.1 |
| **Espaço discreto / inteiro** | Igualdade exata pode ser viável apenas por acaso | Para inteiros, a igualdade é adequada; para mistos, usar tolerância |
| **Escalas muito diferentes entre f1 e f2** | Problemas numéricos no solver | Aplicar escalonamento interno, sem alterar os pontos reportados |

### 6.1 Quando só há uma aproximação da fronteira (heurísticas / metaheurísticas)

Se o projeto obtém apenas um conjunto de soluções não dominadas aproximado (ex.: via NSGA-II), então:

- `z^U` aproximado = mínimo de cada objetivo entre as soluções encontradas.
- `z^N` aproximado = máximo de cada objetivo entre as soluções **não dominadas** encontradas.

Isso é uma **estimativa**: pode subestimar o intervalo real. Para 2 objetivos, prefira calcular os extremos **por otimização mono-objetivo/lexicográfica dedicada**, e não depender apenas da população final.

---

## 7. Problemas com objetivo de maximização

Sempre trabalhe internamente em minimização.

1. Para cada objetivo `fi` a maximizar, defina `f'i = −fi`.
2. Calcule `z^U` e `z^N` conforme as seções anteriores usando `f'`.
3. Converta de volta para exibição: `ziU_original = −z'iU` e `ziN_original = −z'iN`.

Resultado conceitual no espaço original:

- **Utópico** = melhor valor possível de cada objetivo (menor para minimização, **maior** para maximização).
- **Nadir** = pior valor de cada objetivo na fronteira (maior para minimização, **menor** para maximização).

---

## 8. Exemplo numérico completo

**Problema** (minimização):

```
min  f1(x) = x²
min  f2(x) = (x − 2)²
s.a. 0 ≤ x ≤ 2
```

**Passo A:**

- `min f1` → `x = 0`, `z1^U = 0`.
- `min f2` com `f1(x) = 0` ⇒ `x = 0` ⇒ `f2(0) = 4` ⇒ `z2^N = 4`.

**Passo B:**

- `min f2` → `x = 2`, `z2^U = 0`.
- `min f1` com `f2(x) = 0` ⇒ `x = 2` ⇒ `f1(2) = 4` ⇒ `z1^N = 4`.

**Resultado:**

```
Ponto utópico (ideal):      z^U = (0, 0)
Ponto antiutópico (nadir):  z^N = (4, 4)
```

**Verificação:** qualquer `x ∈ [0, 2]` é Pareto-ótimo (a fronteira é `f2 = (2 − √f1)²`, para `f1 ∈ [0, 4]`). Os extremos `x = 0 → (0, 4)` e `x = 2 → (4, 0)` confirmam `z^U = (0, 0)` e `z^N = (4, 4)`. Nenhum `x` atinge `(0, 0)`, confirmando que `z^U` é inalcançável.

**Normalização de uma solução** `x = 1 → F = (1, 1)`:

```
f̄1 = (1 − 0)/(4 − 0) = 0,25
f̄2 = (1 − 0)/(4 − 0) = 0,25
```

---

## 9. Requisitos de implementação

### 9.1 Interface sugerida

| Item | Especificação |
|---|---|
| **Entrada** | Definição do problema (f1, f2, região viável X), sentido de cada objetivo (min/max), tolerâncias (`δ`, `ε`) |
| **Saída** | `z^U` e `z^N` como pares `(valor_f1, valor_f2)` no sentido original dos objetivos; opcionalmente as soluções `x` extremas (as que geram `A` e `B`) |
| **Erros** | Inviabilidade, ilimitado, inconsistência (`z^N < z^U`), com indicação da etapa |
| **Avisos** | Objetivos não conflitantes (faixa ≈ 0), uso de solver local, tolerância elevada |

### 9.2 Boas práticas

1. **Separar** o cálculo dos pontos de referência (módulo próprio) do restante do algoritmo de otimização.
2. **Não recalcular** os pontos a cada iteração; calcular uma vez e armazenar.
3. **Registrar** (log) os quatro valores intermediários (`z1^U`, `z2^N`, `z2^U`, `z1^N`) e as soluções `x` extremas.
4. **Parametrizar** as tolerâncias; não deixar números mágicos no código.
5. **Documentar** no código se o ponto de pior caso usado é `nadir` (Pareto) ou `pior` (toda região viável).

### 9.3 Testes de validação (critérios de aceitação)

- [ ] `z1^U ≤ z1^N` e `z2^U ≤ z2^N` em minimização (e sentido invertido em maximização, no espaço original).
- [ ] Toda solução Pareto-ótima conhecida satisfaz `z^U ≤ F(x) ≤ z^N` componente a componente.
- [ ] O exemplo da seção 8 retorna exatamente `z^U = (0, 0)` e `z^N = (4, 4)`.
- [ ] Em um problema com **ótimos alternativos** conhecido, o nadir **não** é superestimado (comparar com a tabela de payoff ingênua).
- [ ] Em um problema com objetivos **não conflitantes**, o código emite aviso e a normalização não gera `NaN`/`Inf`.
- [ ] Resultado **determinístico** entre execuções (com solver determinístico).
- [ ] Teste com um objetivo de maximização retorna valores coerentes no espaço original.

---

## 10. Glossário rápido

| Termo (PT) | Termo (EN) | Observação |
|---|---|---|
| Ponto utópico | Utopia point / Ideal point | Melhor valor de cada objetivo, isoladamente |
| Ponto antiutópico (nadir) | Nadir point | Pior valor de cada objetivo **na fronteira de Pareto** |
| Pior ponto | Worst point / Anti-ideal | Pior valor sobre **toda** a região viável (não é o nadir) |
| Fronteira de Pareto | Pareto front | Imagem das soluções eficientes no espaço dos objetivos |
| Otimização lexicográfica | Lexicographic optimization | Otimiza um objetivo e, entre seus ótimos, otimiza o seguinte |
| Dominância | Dominance | Relação base para definir eficiência |
| Escalarização | Scalarization | Transformar multiobjetivo em mono-objetivo |

---

## 11. Referências sugeridas

- Ehrgott, M. *Multicriteria Optimization*. 2ª ed., Springer, 2005.
- Miettinen, K. *Nonlinear Multiobjective Optimization*. Kluwer, 1999.
- Deb, K.; Miettinen, K.; Chaudhuri, S. "Toward an estimation of nadir objective vector using a hybrid of evolutionary and local search approaches". *IEEE Trans. on Evolutionary Computation*, 2010.
- Ehrgott, M.; Tenfelde-Podehl, D. "Computation of ideal and nadir values and implications for their use in MCDM methods". *European Journal of Operational Research*, 2003.

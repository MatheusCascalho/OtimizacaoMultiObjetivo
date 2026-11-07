# Procedimento de Tomada de Decisão AHP (Analytic Hierarchy Process)

## 1. Visão geral

O **AHP (Processo Analítico Hierárquico)** é um método de apoio à decisão multicritério desenvolvido por Thomas L. Saaty na década de 1970. Ele permite decompor um problema complexo em uma hierarquia de elementos (objetivo, critérios, subcritérios e alternativas) e avaliá-los por meio de **comparações par a par**, combinando julgamentos qualitativos e quantitativos em uma priorização numérica.

**Quando usar:**

- Há vários critérios, muitas vezes conflitantes, para escolher entre alternativas.
- Parte dos critérios é subjetiva ou difícil de medir objetivamente.
- É necessário um processo transparente, documentado e auditável.
- A decisão envolve múltiplos decisores (decisão em grupo).

---

## 2. Etapas do procedimento

### Etapa 1 — Definir o problema e o objetivo

Descreva claramente a decisão a ser tomada e o objetivo global.

> Exemplo: *Selecionar o melhor fornecedor de equipamentos para a empresa.*

### Etapa 2 — Estruturar a hierarquia

Organize o problema em níveis:

```
Nível 1:  Objetivo
             │
Nível 2:  Critérios (C1, C2, ..., Cn)
             │
Nível 3:  Subcritérios (opcional)
             │
Nível 4:  Alternativas (A1, A2, ..., Am)
```

Recomendações:

- Cada critério deve ser **independente** dos demais, na medida do possível.
- Use de **3 a 9 critérios** por nível (acima disso, a consistência dos julgamentos tende a piorar).
- Todas as alternativas devem ser avaliadas em todos os critérios.

### Etapa 3 — Construir as matrizes de comparação par a par

Para cada nível, compare os elementos dois a dois em relação ao elemento do nível superior, usando a **Escala Fundamental de Saaty**:

| Intensidade | Definição | Explicação |
|:-----------:|-----------|------------|
| 1 | Igual importância | Os dois elementos contribuem igualmente |
| 3 | Importância moderada | Um é ligeiramente preferido ao outro |
| 5 | Importância forte | Um é fortemente preferido ao outro |
| 7 | Importância muito forte | Um é muito fortemente preferido, com dominância demonstrada |
| 9 | Importância extrema | Evidência máxima a favor de um elemento |
| 2, 4, 6, 8 | Valores intermediários | Usados quando há necessidade de compromisso |

**Regra da reciprocidade:** se o elemento *i* tem importância *a_ij* em relação ao elemento *j*, então *a_ji = 1 / a_ij*. Além disso, *a_ii = 1*.

Para *n* elementos, a matriz **A** tem a forma:

```
        C1     C2     C3
C1  [   1     a12    a13 ]
C2  [  1/a12   1     a23 ]
C3  [  1/a13  1/a23   1  ]
```

O número de comparações necessárias por matriz é *n(n − 1) / 2*.

### Etapa 4 — Calcular os pesos (prioridades locais)

O vetor de prioridades **w** é o autovetor principal da matriz **A**. Na prática, usa-se um método aproximado:

1. **Somar cada coluna** da matriz.
2. **Normalizar**: dividir cada elemento pela soma de sua coluna.
3. **Calcular a média de cada linha** da matriz normalizada. O resultado é o vetor de pesos **w**.

A soma dos pesos deve ser igual a 1 (ou 100%).

### Etapa 5 — Verificar a consistência dos julgamentos

Julgamentos humanos podem ser inconsistentes (por exemplo, A > B, B > C, mas C > A). O AHP mede isso com a **Razão de Consistência (RC)**.

**5.1 Calcular λ_max (autovalor máximo):**

1. Multiplique a matriz original **A** pelo vetor de pesos **w**, obtendo o vetor **A·w**.
2. Divida cada elemento de **A·w** pelo elemento correspondente de **w**.
3. λ_max é a média desses quocientes.

**5.2 Calcular o Índice de Consistência (IC):**

```
IC = (λ_max − n) / (n − 1)
```

**5.3 Calcular a Razão de Consistência (RC):**

```
RC = IC / IR
```

onde **IR** é o Índice Aleatório, que depende do tamanho *n* da matriz:

| n  | 1 | 2 | 3    | 4    | 5    | 6    | 7    | 8    | 9    | 10   |
|----|---|---|------|------|------|------|------|------|------|------|
| IR | 0 | 0 | 0,58 | 0,90 | 1,12 | 1,24 | 1,32 | 1,41 | 1,45 | 1,49 |

**Interpretação:**

- **RC ≤ 0,10** → julgamentos aceitáveis.
- **RC > 0,10** → julgamentos inconsistentes; **revise as comparações** e refaça o cálculo.

### Etapa 6 — Repetir para todos os níveis

- Compare os **critérios** entre si em relação ao objetivo (obtém-se o vetor de pesos dos critérios).
- Para **cada critério**, compare as **alternativas** entre si (obtém-se uma matriz de pesos das alternativas por critério).
- Se houver subcritérios, repita o procedimento em cada ramo da hierarquia.
- Verifique a consistência de **cada** matriz.

### Etapa 7 — Sintetizar as prioridades globais

Calcule a pontuação final de cada alternativa combinando os pesos dos critérios com o desempenho local das alternativas:

```
Pontuação(Aj) = Σ ( peso_critério_i × peso_local_Aj_no_critério_i )
```

Em forma matricial: multiplique a matriz de pesos das alternativas (m × n) pelo vetor de pesos dos critérios (n × 1).

### Etapa 8 — Ranquear e decidir

- Ordene as alternativas da maior para a menor pontuação global.
- A alternativa com a maior pontuação é a mais indicada segundo os julgamentos fornecidos.

### Etapa 9 — Análise de sensibilidade

Teste a robustez da decisão:

- Varie os pesos dos critérios (por exemplo, ±10% a ±20%) e observe se o ranking muda.
- Identifique critérios cuja alteração de peso inverte a ordem das alternativas.
- Discuta com os decisores se o resultado permanece aceitável.

---

## 3. Exemplo numérico resumido

**Problema:** escolher entre 3 fornecedores (A, B, C) considerando 3 critérios: **Preço**, **Qualidade** e **Prazo**.

### 3.1 Matriz de comparação dos critérios

|          | Preço | Qualidade | Prazo |
|----------|:-----:|:---------:|:-----:|
| Preço    | 1     | 1/3       | 3     |
| Qualidade| 3     | 1         | 5     |
| Prazo    | 1/3   | 1/5       | 1     |
| **Soma** | 4,33  | 1,53      | 9,00  |

### 3.2 Matriz normalizada e pesos

|          | Preço | Qualidade | Prazo | **Peso (média)** |
|----------|:-----:|:---------:|:-----:|:----------------:|
| Preço    | 0,231 | 0,217     | 0,333 | **0,260**        |
| Qualidade| 0,692 | 0,652     | 0,556 | **0,633**        |
| Prazo    | 0,077 | 0,130     | 0,111 | **0,106**        |

### 3.3 Consistência (resumo)

- λ_max ≈ 3,04
- IC = (3,04 − 3) / 2 ≈ 0,02
- RC = 0,02 / 0,58 ≈ **0,03** → **consistente** (RC < 0,10).

### 3.4 Síntese final (valores ilustrativos)

| Alternativa | Preço (0,260) | Qualidade (0,633) | Prazo (0,106) | **Pontuação global** |
|-------------|:-------------:|:-----------------:|:-------------:|:--------------------:|
| Fornecedor A| 0,60          | 0,20              | 0,30          | **0,31**             |
| Fornecedor B| 0,30          | 0,30              | 0,60          | **0,33**             |
| Fornecedor C| 0,10          | 0,50              | 0,10          | **0,35**             |

**Resultado:** Fornecedor C > Fornecedor B > Fornecedor A. Como a **Qualidade** tem o maior peso, o fornecedor com melhor desempenho nesse critério lidera o ranking.

---

## 4. Decisão em grupo

Quando há vários decisores, há duas abordagens comuns:

- **Agregação de julgamentos individuais (AIJ):** combinam-se as matrizes individuais por **média geométrica** elemento a elemento, gerando uma matriz consensual.
- **Agregação de prioridades individuais (AIP):** cada decisor calcula suas prioridades e combinam-se os vetores finais (média aritmética ou geométrica, possivelmente com pesos distintos por decisor).

---

## 5. Vantagens e limitações

**Vantagens**

- Estrutura clara e intuitiva para problemas complexos.
- Integra critérios quantitativos e qualitativos.
- Mede a consistência dos julgamentos.
- Amplamente difundido, com muitas ferramentas de apoio.

**Limitações**

- O número de comparações cresce rapidamente com *n* (quadraticamente).
- Sensível à subjetividade dos julgamentos.
- Possibilidade de *rank reversal* (inversão de ranking) ao incluir ou excluir alternativas.
- A escala de 1 a 9 pode não representar fielmente a preferência real do decisor.
- Pressupõe independência entre critérios (para dependências, considera-se o método ANP).

---

## 6. Checklist de aplicação

- [ ] Problema e objetivo claramente definidos
- [ ] Critérios e alternativas identificados e validados
- [ ] Hierarquia estruturada
- [ ] Matrizes de comparação par a par preenchidas (escala de Saaty)
- [ ] Pesos calculados para cada matriz
- [ ] RC ≤ 0,10 em todas as matrizes (ou julgamentos revisados)
- [ ] Prioridades globais sintetizadas
- [ ] Alternativas ranqueadas
- [ ] Análise de sensibilidade realizada
- [ ] Decisão e justificativa documentadas

---

## 7. Referências

- Saaty, T. L. (1980). *The Analytic Hierarchy Process*. McGraw-Hill.
- Saaty, T. L. (1990). How to make a decision: The Analytic Hierarchy Process. *European Journal of Operational Research*, 48(1), 9–26.
- Saaty, T. L. (2008). Decision making with the analytic hierarchy process. *International Journal of Services Sciences*, 1(1), 83–98.

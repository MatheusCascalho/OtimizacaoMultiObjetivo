# Análise de Robustez de Soluções do TSP Biobjetivo (Distância × Tempo) com Tempos Estocásticos

## 1. Objetivo e escopo

Este documento descreve o procedimento para avaliar a robustez de um **conjunto pré-determinado de soluções** (rotas já obtidas, por exemplo, pontos de uma fronteira de Pareto) de um TSP biobjetivo quando os **tempos de viagem dos arcos são incertos**.

Premissas:

- As rotas são **fixas**: a incerteza não altera a sequência de visitas, apenas o custo realizado.
- A **distância** de cada arco é determinística. O **tempo** de cada arco é uma variável aleatória log-normal.
- A análise é feita por **simulação de Monte Carlo**, reavaliando todas as soluções nos mesmos cenários.

### Notação

| Símbolo | Significado |
|---|---|
| $V$, $A$ | Conjunto de nós e de arcos (i, j) |
| $d_{ij}$ | Distância determinística do arco (i, j) |
| $\bar t_{ij}$ | Tempo nominal do arco (i, j) |
| $T_{ij}$ | Tempo aleatório do arco (i, j) |
| $S_k$, $k=1,\dots,K$ | Solução k (ciclo hamiltoniano), com conjunto de arcos $A_k$ |
| $N$ | Número de cenários de Monte Carlo |
| $T^{(n)}_{ij}$ | Tempo do arco (i, j) no cenário n |
| $D_k$, $T_k^{(n)}$ | Distância total (fixa) e tempo total da solução k no cenário n |

Objetivos de cada solução no cenário n:

$$
D_k = \sum_{(i,j)\in A_k} d_{ij}, \qquad
T_k^{(n)} = \sum_{(i,j)\in A_k} T^{(n)}_{ij}
$$

Como $D_k$ é determinístico, **a incerteza afeta apenas o eixo do tempo**. Se no futuro a distância também for modelada como aleatória, o mesmo procedimento se aplica, com um segundo vetor de amostras.

---

## 2. Modelagem dos tempos estocásticos (log-normal por arco)

### 2.1 Distribuição

Para cada arco $(i,j)$:

$$
T_{ij} = \exp(\mu_{ij} + \sigma_{ij} Z_{ij}), \qquad Z_{ij}\sim\mathcal N(0,1)
$$

A log-normal é adequada porque é estritamente positiva, assimétrica à direita (atrasos grandes são mais prováveis que ganhos grandes) e tem parametrização simples.

### 2.2 Parametrização a partir do tempo nominal e do coeficiente de variação

Escolha de projeto: **a média do tempo aleatório é igual ao tempo nominal**, $E[T_{ij}]=\bar t_{ij}$. Assim, o tempo esperado da solução coincide com o tempo nominal e a análise isola o efeito da **variabilidade**.

Dado o coeficiente de variação $CV_{ij}$ do arco:

$$
\sigma_{ij}^2 = \ln\!\left(1 + CV_{ij}^2\right), \qquad
\mu_{ij} = \ln(\bar t_{ij}) - \tfrac{1}{2}\sigma_{ij}^2
$$

Consequências: $E[T_{ij}]=\bar t_{ij}$, $\mathrm{Var}[T_{ij}] = (CV_{ij}\,\bar t_{ij})^2$ e a mediana é $\bar t_{ij}\,e^{-\sigma_{ij}^2/2} < \bar t_{ij}$.

> Alternativa: interpretar $\bar t_{ij}$ como a **mediana** ($\mu_{ij}=\ln \bar t_{ij}$). Nesse caso, a média passa a ser maior que o nominal. Registre qual convenção foi adotada.

### 2.3 Escolha de $CV_{ij}$

Opções, da mais simples à mais elaborada:

1. **CV global**: $CV_{ij}=CV$ para todos os arcos (ex.: 0,10; 0,20; 0,30). É o ponto de partida e a variável do estudo de sensibilidade.
2. **CV por classe de arco**: por exemplo, arcos urbanos/curtos com CV maior e arcos de rodovia/longos com CV menor, ou CV em função do tempo nominal.
3. **CV calibrado com dados históricos**: estimar $\sigma_{ij}$ pelo desvio-padrão de $\ln(\text{tempo observado})$ por arco ou por classe.

Na ausência de dados, adote a opção 1 e varie o CV (Seção 5.6).

### 2.4 Correlação espacial entre arcos

Arcos próximos tendem a piorar juntos (trânsito, clima, obras). Ignorar isso **subestima a variância do tempo total** (as somas de variáveis independentes se compensam mais do que na realidade).

Abordagem recomendada: **fator comum regional** em espaço gaussiano (cópula gaussiana).

1. Atribua cada arco a uma região $r(i,j)$ (ex.: grade espacial ou clusterização k-means do ponto médio do arco).
2. Defina a correlação intra-regional $\rho\in[0,1)$ (ex.: 0; 0,3; 0,6).
3. Gere:

$$
Z_{ij} = \sqrt{\rho}\; G_{r(i,j)} + \sqrt{1-\rho}\;\varepsilon_{ij},
\qquad G_r,\ \varepsilon_{ij}\overset{iid}{\sim}\mathcal N(0,1)
$$

Cada $Z_{ij}$ continua com distribuição $\mathcal N(0,1)$, então as marginais log-normais da Seção 2.2 são preservadas. A correlação entre arcos da mesma região no espaço logarítmico é $\rho$; arcos de regiões diferentes são independentes.

Opcionalmente, adicione um **fator global** $G_0$ (evento que afeta toda a rede):

$$
Z_{ij} = \sqrt{\rho_0}\,G_0 + \sqrt{\rho_r}\,G_{r(i,j)} + \sqrt{1-\rho_0-\rho_r}\;\varepsilon_{ij}
$$

com $\rho_0+\rho_r<1$.

### 2.5 Sobre arcos assimétricos e arcos não utilizados

- Se a matriz de tempos for assimétrica, trate $(i,j)$ e $(j,i)$ como arcos distintos (mas podem compartilhar o mesmo fator regional).
- Para a avaliação das soluções, só é necessário amostrar os **arcos que aparecem em pelo menos uma solução**: $A_{\text{uso}}=\bigcup_k A_k$. Isso reduz muito o custo (de $O(|V|^2)$ para $O(K|V|)$ arcos). A matriz completa só é necessária se houver reotimização por cenário (Seção 4.3).

---

## 3. Simulação de Monte Carlo para o conjunto de soluções

### 3.1 Entradas

- Matrizes (ou listas de arcos) de distância $d_{ij}$ e tempo nominal $\bar t_{ij}$.
- Conjunto de soluções $\{S_1,\dots,S_K\}$, cada uma como sequência de nós.
- Parâmetros de incerteza: $CV$ (global ou por arco), $\rho$ (e $\rho_0$), mapeamento arco → região.
- Número de cenários $N$ e semente do gerador aleatório.
- Opcional: limite de tempo $T_{\lim}$ (prazo) e pontos de referência para hipervolume.

### 3.2 Procedimento

1. **Extrair os arcos** de cada solução: $A_k=\{(s_1,s_2),(s_2,s_3),\dots,(s_m,s_1)\}$ e formar $A_{\text{uso}}$.
2. **Calcular $D_k$** e o **tempo nominal** $\bar T_k=\sum_{A_k}\bar t_{ij}$ de cada solução.
3. **Calcular $\mu_{ij}$ e $\sigma_{ij}$** para $(i,j)\in A_{\text{uso}}$ (Seção 2.2).
4. Para cada cenário $n=1,\dots,N$:
   1. Sortear $G_0^{(n)}$, $G_r^{(n)}$ (um por região) e $\varepsilon_{ij}^{(n)}$ (um por arco).
   2. Calcular $Z_{ij}^{(n)}$ e $T_{ij}^{(n)}=\exp(\mu_{ij}+\sigma_{ij}Z_{ij}^{(n)})$.
   3. Calcular $T_k^{(n)}=\sum_{A_k}T_{ij}^{(n)}$ **para todas as soluções k no mesmo cenário**.
5. Armazenar a matriz de resultados $\mathbf T\in\mathbb R^{N\times K}$ e o vetor $\mathbf D\in\mathbb R^{K}$.

### 3.3 Pontos de atenção

- **Números aleatórios comuns (CRN):** todas as soluções devem ser avaliadas nos **mesmos** cenários. Isso reduz a variância das comparações entre soluções e torna válidas as métricas de dominância, ranking e regret. Soluções que compartilham arcos ficam corretamente correlacionadas.
- **Tamanho da amostra:** $N$ entre 5.000 e 20.000 costuma bastar. Verifique a convergência: o erro-padrão da média é $s/\sqrt N$, e métricas de cauda (P95, CVaR) convergem mais lentamente. Estabilize rodando com sementes diferentes ou acompanhando a métrica em função de $N$.
- **Reprodutibilidade:** fixe e registre a semente.
- **Vetorização:** monte uma matriz de incidência $\mathbf B\in\{0,1\}^{K\times|A_{\text{uso}}|}$ (1 se o arco pertence à solução k). Com a matriz de tempos amostrados $\mathbf X\in\mathbb R^{N\times|A_{\text{uso}}|}$, obtém-se $\mathbf T=\mathbf X\mathbf B^\top$ em uma única multiplicação.
- **Verificação de sanidade:** com $\sigma\to0$ o resultado deve reproduzir os tempos nominais. Com a convenção de média preservada, a média amostral de $T_k$ deve ficar próxima de $\bar T_k$.

### 3.4 Esqueleto em Python

```python
import numpy as np

def simular_cenarios(rotas, dist, tempo_nom, regiao_arco, cv=0.2,
                     rho=0.3, rho0=0.0, N=10_000, seed=42):
    """
    rotas: lista de listas de nós (ciclo; o retorno ao início é implícito)
    dist, tempo_nom: matrizes (n x n)
    regiao_arco: dict {(i, j): id_regiao}
    Retorna T (N x K), D (K,), T_nominal (K,)
    """
    rng = np.random.default_rng(seed)

    # 1) arcos de cada solução e união de arcos
    arcos_rota = [[(r[i], r[(i + 1) % len(r)]) for i in range(len(r))] for r in rotas]
    arcos_uso = sorted({a for ar in arcos_rota for a in ar})
    idx = {a: m for m, a in enumerate(arcos_uso)}
    M, K = len(arcos_uso), len(rotas)

    # 2) matriz de incidência B (K x M)
    B = np.zeros((K, M))
    for k, ar in enumerate(arcos_rota):
        for a in ar:
            B[k, idx[a]] = 1.0

    # 3) parâmetros log-normais (média preservada)
    t_nom = np.array([tempo_nom[i, j] for (i, j) in arcos_uso])
    sigma = np.sqrt(np.log(1.0 + cv**2)) * np.ones(M)
    mu = np.log(t_nom) - 0.5 * sigma**2

    # 4) fatores regionais
    regs = np.array([regiao_arco[a] for a in arcos_uso])
    ids_reg, reg_idx = np.unique(regs, return_inverse=True)
    G0 = rng.standard_normal((N, 1))
    Gr = rng.standard_normal((N, len(ids_reg)))[:, reg_idx]
    eps = rng.standard_normal((N, M))
    rho_r = rho
    Z = (np.sqrt(rho0) * G0 + np.sqrt(rho_r) * Gr
         + np.sqrt(1.0 - rho0 - rho_r) * eps)

    # 5) tempos por arco e totais por solução (mesmos cenários para todas)
    X = np.exp(mu + sigma * Z)          # N x M
    T = X @ B.T                         # N x K

    D = np.array([sum(dist[i, j] for (i, j) in ar) for ar in arcos_rota])
    T_nominal = B @ t_nom
    return T, D, T_nominal
```

---

## 4. Métricas de robustez

Com $\mathbf T$ ($N\times K$), $\mathbf D$ ($K$) e $\bar{\mathbf T}$ (tempos nominais), calculam-se as métricas abaixo. Elas se dividem em **individuais** (cada solução isolada) e **comparativas** (relação entre soluções nos mesmos cenários).

### 4.1 Métricas individuais do tempo

Para cada solução k:

| Métrica | Definição | Interpretação |
|---|---|---|
| Média | $\hat\mu_k=\frac1N\sum_n T_k^{(n)}$ | Desempenho esperado |
| Desvio-padrão | $\hat s_k$ | Dispersão absoluta |
| Coeficiente de variação | $\hat s_k/\hat\mu_k$ | Dispersão relativa (permite comparar rotas de tempos diferentes) |
| Percentis | $P_{50}, P_{90}, P_{95}, P_{99}$ | Comportamento em cenários adversos |
| Pior caso amostral | $\max_n T_k^{(n)}$ | Sensível a $N$; use apenas como referência |
| **VaR**$_\alpha$ | percentil $\alpha$ de $T_k$ (ex.: $\alpha=0{,}95$) | Tempo não excedido com probabilidade $\alpha$ |
| **CVaR**$_\alpha$ | média dos $T_k^{(n)}$ que excedem o VaR$_\alpha$ | Gravidade média da cauda (mais informativo que o VaR) |
| Prob. de violação | $\hat P(T_k>T_{\lim})=\frac1N\sum_n \mathbf 1[T_k^{(n)}>T_{\lim}]$ | Risco de estourar um prazo |
| Degradação do P95 | $(P_{95,k}-\bar T_k)/\bar T_k$ | Quanto o nominal "mente" no cenário adverso |
| Intervalo de confiança da média | $\hat\mu_k\pm 1{,}96\,\hat s_k/\sqrt N$ | Precisão da estimativa |

**Distância:** como $D_k$ é determinística, não há métrica de dispersão para ela. Ela entra nas métricas comparativas e na leitura final do compromisso.

### 4.2 Métricas comparativas entre soluções (aspecto biobjetivo)

Em cada cenário n, cada solução k tem o ponto $(D_k, T_k^{(n)})$.

**a) Frequência de melhor solução em tempo.** Fração de cenários em que k tem o menor tempo:

$$
w_k=\frac1N\sum_n \mathbf 1\!\left[k=\arg\min_{l} T_l^{(n)}\right]
$$

Compare com a ordenação nominal. Se a solução nominalmente mais rápida só for a mais rápida em poucos cenários, o ranking é frágil.

**b) Distribuição de ranks.** Para cada k, a frequência de cada posição (1º, 2º, ...) no ordenamento por tempo. Resume a estabilidade da ordem.

**c) Matriz de dominância.** Para cada par $(a,b)$:

$$
\Pi_{ab}=\frac1N\sum_n \mathbf 1\!\left[(D_a\le D_b)\wedge(T_a^{(n)}\le T_b^{(n)})\wedge\big((D_a<D_b)\vee(T_a^{(n)}<T_b^{(n)})\big)\right]
$$

É a probabilidade de $a$ dominar $b$. Como $D$ é fixo, se $D_a<D_b$ então $a$ domina $b$ exatamente nos cenários em que $T_a\le T_b$; no caso contrário a relação depende do sinal inverso. Pares em que $\Pi_{ab}$ e $\Pi_{ba}$ são ambos pequenos mantêm o status de "não dominados entre si" na maioria dos cenários.

**d) Probabilidade de pertencer à fronteira de Pareto do conjunto.** Em cada cenário, identifique as soluções não dominadas dentro do conjunto de K e calcule:

$$
\pi_k=\frac1N\sum_n \mathbf 1\!\left[S_k \text{ é não dominada no cenário } n\right]
$$

Uma solução com $\pi_k$ próximo de 1 é **robustamente eficiente**; com $\pi_k$ baixo, ela perde a eficiência sob incerteza.

**e) Regret (arrependimento) em relação ao melhor do conjunto.** Por objetivo, no cenário n:

$$
R_k^{T,(n)}=T_k^{(n)}-\min_l T_l^{(n)}
$$

Reporte média, P95 e máximo de $R_k^{T}$. Para distância o regret é constante: $R_k^{D}=D_k-\min_l D_l$. O regret mede o custo de ter escolhido k em vez da melhor opção *do cenário*.

**f) Hipervolume por cenário.** Fixe um ponto de referência $\mathbf r=(r_D,r_T)$ pior que todas as soluções em todos os cenários (por exemplo, o máximo de $D$ e o máximo de $T$ na amostra, com folga de 5%). Em cada cenário calcule o hipervolume $HV^{(n)}$ da fronteira formada pelo conjunto e reporte média e desvio-padrão. Para medir a **contribuição** de k, calcule $HV^{(n)}$ com e sem k:

$$
\Delta HV_k=\frac1N\sum_n\left(HV^{(n)}-HV^{(n)}_{-k}\right)
$$

Em 2 objetivos o hipervolume é uma soma de retângulos após ordenar os pontos não dominados por $D$.

### 4.3 Distância à fronteira de referência do cenário (opcional)

Se for possível reotimizar (ou aproximar por heurística) a fronteira de Pareto em um **subconjunto de cenários** (ex.: 100 a 200, dada a alta complexidade do TSP biobjetivo), calcule o **indicador ε multiplicativo** de cada solução contra a fronteira de referência $F^{(n)}$ do cenário:

$$
\varepsilon_k^{(n)}=\min_{\varepsilon\ge 1}\ \Big\{\ \forall f\in F^{(n)}\ \ \exists\ \text{ponto } (D_k,T_k^{(n)}):\ D_k\le\varepsilon f_D \ \wedge\ T_k^{(n)}\le\varepsilon f_T\Big\}
$$

Interpretação: $\varepsilon=1{,}03$ significa que a solução fica, no máximo, 3% acima de um ponto da fronteira daquele cenário em cada objetivo. Esse indicador mede a perda de qualidade em relação ao **ótimo possível** (e não apenas relativa ao conjunto), mas é caro. Use-o como validação em amostra reduzida.

### 4.4 Arcos críticos

Identifica quais arcos concentram o risco de cada solução:

- **Contribuição à variância** (caso independente, $\rho=0$):

  $$
  c_{ij}=\frac{\mathrm{Var}[T_{ij}]}{\sum_{A_k}\mathrm{Var}[T_{ij}]}=\frac{(CV\,\bar t_{ij})^2}{\sum_{A_k}(CV\,\bar t_{ij})^2}
  $$

  Para CV global, depende do quadrado do tempo nominal: poucos arcos longos dominam a variância.
- **Correlação empírica** entre $T_{ij}^{(n)}$ e $T_k^{(n)}$ (ou índice de Sobol / regressão padronizada de $T_k$ sobre os tempos dos arcos), que já incorpora a correlação regional.
- Liste os top-10 arcos por solução e compare entre soluções: arcos críticos **exclusivos** de uma solução são fonte de fragilidade específica dela.

### 4.5 Resumo e agregação

Monte uma tabela final por solução com, no mínimo:

| Solução | $D_k$ | $\bar T_k$ | $\hat\mu_k$ | CV | P95 | CVaR$_{95}$ | $P(T>T_{\lim})$ | $w_k$ | $\pi_k$ | Regret médio | Regret P95 | $\Delta HV_k$ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|

Se for necessário **ranquear** as soluções, combine métricas conforme o perfil do decisor, por exemplo:

- **Avesso a risco:** priorizar CVaR$_{95}$, regret P95 e $\pi_k$.
- **Neutro ao risco:** priorizar $\hat\mu_k$ e regret médio.
- **Orientado a prazo:** priorizar $P(T>T_{\lim})$.

Evite colapsar tudo em um único escore sem explicitar os pesos.

---

## 5. Procedimento completo (passo a passo)

1. **Preparar os dados:** carregar $d_{ij}$, $\bar t_{ij}$ e as rotas; validar que cada rota é um ciclo hamiltoniano e recalcular $D_k$ e $\bar T_k$ (devem coincidir com os valores reportados pelo otimizador).
2. **Definir a incerteza:** escolher CV, $\rho$ (e $\rho_0$), regiões, convenção de média/mediana (Seção 2).
3. **Simular:** gerar $N$ cenários com CRN e obter $\mathbf T$ (Seção 3).
4. **Verificar a simulação:** sanidade com $\sigma\to 0$, média amostral ≈ nominal, convergência das métricas de cauda em função de $N$.
5. **Calcular as métricas individuais** (Seção 4.1).
6. **Calcular as métricas comparativas** (Seção 4.2): ranking, dominância, $\pi_k$, regret, hipervolume.
7. **Identificar arcos críticos** (Seção 4.4).
8. **(Opcional) Validar contra a fronteira reotimizada** em subamostra (Seção 4.3).
9. **Estudo de sensibilidade:** repetir os passos 3 a 7 variando
   - $CV\in\{0{,}05;\,0{,}10;\,0{,}20;\,0{,}30\}$,
   - $\rho\in\{0;\,0{,}3;\,0{,}6\}$,
   - a convenção (média vs. mediana).

   Registre o **ponto de inversão**: a partir de qual CV (ou $\rho$) o ranking de soluções muda ou uma solução deixa de ser eficiente.
10. **Reportar:** tabela-resumo, gráficos (abaixo) e conclusão sobre qual solução é mais robusta e sob quais condições.

### 5.1 Gráficos recomendados

- **Nuvem de pontos** $(D_k,T_k^{(n)})$ por solução, com elipses de confiança ou contornos de densidade.
- **Boxplot/violino** de $T_k$ por solução, com o tempo nominal marcado.
- **Mapa de calor** da matriz de dominância $\Pi_{ab}$.
- **Barras empilhadas** da distribuição de ranks por solução.
- **Curvas de sensibilidade:** métrica (P95, CVaR, $\pi_k$, $w_k$) em função do CV e de $\rho$.
- **Função de attainment empírica** da fronteira do conjunto sob incerteza.

---

## 6. Interpretação e limitações

- **Efeito do número de arcos:** com $\rho=0$, rotas com muitos arcos curtos tendem a ter CV total menor (compensação por soma de variáveis independentes, aproximadamente $CV_{\text{rota}}\approx CV/\sqrt{m}$ para $m$ arcos de tempos parecidos). Com $\rho$ alto, esse benefício diminui. Por isso a correlação não deve ser omitida.
- **Soluções com tempos nominais próximos:** pequenas diferenças nominais serão facilmente invertidas por CVs moderados. Isso é um resultado válido da análise (as soluções são praticamente equivalentes em tempo) e não um erro.
- **Premissa de $E[T]=\bar t$:** se o tempo nominal vem de um roteamento "sem trânsito", a média real tende a ser **maior** que o nominal. Nesse caso, use a convenção de mediana ou aplique um fator de calibração $\kappa>1$ a $\bar t_{ij}$.
- **Soluções fixas:** a análise mede a robustez das rotas dadas, não a do problema. Em uma variação de dados real, o decisor poderia reotimizar. A comparação com a fronteira reotimizada (Seção 4.3) quantifica o quanto se perde por não reotimizar.
- **Cauda da soma de log-normais:** a soma não é log-normal. Aproximações analíticas (Fenton-Wilkinson) podem servir como verificação rápida, mas as métricas de cauda devem vir da simulação.
- **Incerteza na própria calibração:** $CV$ e $\rho$ são estimados ou assumidos. A análise de sensibilidade (passo 9) é o que protege a conclusão contra erros nessas premissas.

---

## 7. Parâmetros a registrar em cada execução

| Parâmetro | Valor |
|---|---|
| Número de cenários $N$ | |
| Semente | |
| CV (global ou regra por arco) | |
| $\rho$ intra-região / $\rho_0$ global | |
| Definição de regiões | |
| Convenção (média ou mediana = nominal) | |
| Nível $\alpha$ de VaR/CVaR | |
| Prazo $T_{\lim}$ | |
| Ponto de referência do hipervolume | |
| Versão do conjunto de soluções | |

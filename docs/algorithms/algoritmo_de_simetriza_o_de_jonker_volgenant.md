# Guia de Implementação: Simetrização de Jonker-Volgenant ($2n$ Nós)

Este documento descreve o passo a passo detalhado para implementar o método de **simetrização de Jonker-Volgenant**, que converte uma instância do **Problema do Caixeiro Viajante Assimétrico (ATSP)** com $n$ nós em um **Problema do Caixeiro Viajante Simétrico (STSP)** equivalente com $2n$ nós.

---

## 1. Visão Geral do Método

Em uma instância de ATSP com $n$ vértices, a matriz de custos $C \in \mathbb{R}^{n \times n}$ não é simétrica ($c_{ij} \neq c_{ji}$). 

A técnica de Jonker-Volgenant duplica cada nó $i \in \{1, \dots, n\}$ em dois sub-nós:
* $i_{out}$ (representando a **saída** ou partida do nó $i$)
* $i_{in}$ (representando a **entrada** ou chegada no nó $i$)

O grafo resultante $G' = (V', E')$ terá $|V'| = 2n$ nós e uma matriz de custos simétrica $C' \in \mathbb{R}^{2n \times 2n}$.

---

## 2. Passo a Passo da Implementação

### Passo 1: Mapeamento de Índices
Defina uma convenção clara para indexar os $2n$ nós na nova matriz $C'$ de tamanho $2n \times 2n$:
* Os primeiros $n$ índices ($1$ até $n$) representam os nós de **saída** ($i_{out}$).
* Os últimos $n$ índices ($n+1$ até $2n$) representam os nós de **entrada** ($i_{in}$).

---

### Passo 2: Definição das Constantes de Penalidade
Defina um valor muito alto $M$ (ex: $\infty$ ou a soma de todos os custos da matriz original $+ 1$) para simular a proibição de certas arestas no grafo simétrico.

---

### Passo 3: Construção da Matriz de Custos Simétrica $C'$

A nova matriz $C'$ é composta por 4 blocos de tamanho $n \times n$:

$$
C' = 
\begin{bmatrix}
C_{11} & C_{12} \\
C_{21} & C_{22}
\end{bmatrix}
=
\begin{bmatrix}
M & C \\
C^T & M
\end{bmatrix}
$$

#### Regras de Preenchimento dos Blocos:

1. **Bloco Superior Esquerdo ($C_{11}$): Conexões entre Saídas ($i_{out} \to j_{out}$)**
   * Defina todas as posições como $M$.
   * *Motivo:* Não é permitido ir diretamente de uma saída para outra saída.

2. **Bloco Inferior Direito ($C_{22}$): Conexões entre Entradas ($i_{in} \to j_{in}$)**
   * Defina todas as posições como $M$.
   * *Motivo:* Não é permitido ir diretamente de uma entrada para outra entrada.

3. **Bloco Superior Direito ($C_{12}$): Conexões de Saída para Entrada ($i_{out} \to j_{in}$)**
   * Para $i \neq j$: Defina $C'_{i, n+j} = c_{ij}$ (o custo original do nó $i$ para o nó $j$).
   * Para $i = j$: Defina $C'_{i, n+i} = -M$ (ou $0$, dependendo da formulação exata e das restrições do solver, para forçar/favorecer a correspondência direta entre o nó de saída e seu par de entrada).

4. **Bloco Inferior Esquerdo ($C_{21}$): Conexões de Entrada para Saída ($i_{in} \to j_{out}$)**
   * Garanta a simetria fazendo $C'_{n+i, j} = C'_{j, n+i}$.
   * Consequentemente, para $i \neq j$, $C'_{n+j, i} = c_{ij}$.

---

## 3. Resumo da Estrutura da Matriz $C'$

| Posição $(r, c)$ | Intervalo de $r, c$ | Valor de $C'_{r,c}$ |
| :--- | :--- | :--- |
| $r \le n, c \le n$ | Saída $\to$ Saída | $M$ |
| $r > n, c > n$ | Entrada $\to$ Entrada | $M$ |
| $r \le n, c > n$ ($r \neq c - n$) | Saída $i \to$ Entrada $j$ | $c_{i, c-n}$ |
| $r > n, c \le n$ ($r - n \neq c$) | Entrada $j \to$ Saída $i$ | $c_{c, r-n}$ |
| $r = c - n$ ou $r - n = c$ | Conexão Interna do Nó ($i_{out} \leftrightarrow i_{in}$) | $-M$ (ou $0$) |

---

## 4. Reconstrução do Tour Original (Pós-Processamento)

Após resolver a instância simétrica com $2n$ nós usando um solver de STSP (ex: Concorde, Gurobi, OR-Tools):

1. Obtenha a sequência de visitação do ciclo hamiltoniano simétrico de $2n$ nós: $T' = (v_1, v_2, \dots, v_{2n}, v_1)$.
2. Identifique os pares de transição entre os nós originais.
3. Filtre as conexões internas (arestas entre $i_{out}$ e $i_{in}$) para extrair a ordem de visita das cidades do problema $n$-assimétrico original.

---

## 5. Exemplo de Código em Python

```python
import numpy as np

def transform_atsp_to_stsp(c_matrix: np.ndarray, M: float = 1e6) -> np.ndarray:
    """
    Converte uma matriz de custos de ATSP (n x n) em uma matriz STSP (2n x 2n)
    utilizando a simetrização de Jonker-Volgenant.
    """
    n = c_matrix.shape[0]
    c_prime = np.full((2 * n, 2 * n), M, dtype=float)

    # Preenchimento do Bloco C12 (i_out -> j_in) e C21 (j_in -> i_out)
    for i in range(n):
        for j in range(n):
            if i != j:
                # Transição da cidade i para a cidade j
                c_prime[i, n + j] = c_matrix[i, j]
                c_prime[n + j, i] = c_matrix[i, j]
            else:
                # Aresta de acoplamento do mesmo nó (i_out <-> i_in)
                c_prime[i, n + i] = -M
                c_prime[n + i, i] = -M

    return c_prime

# Exemplo de uso
if __name__ == "__main__":
    # Matriz assimétrica 3x3 de exemplo
    atsp_matrix = np.array([
        [0, 10, 15],
        [20, 0, 5],
        [9, 12, 0]
    ])

    stsp_matrix = transform_atsp_to_stsp(atsp_matrix)
    print("Matriz Simétrica de 2n x 2n (6x6):\n", stsp_matrix)
```
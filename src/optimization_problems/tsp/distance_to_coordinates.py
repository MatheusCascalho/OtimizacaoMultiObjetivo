import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def torgerson_mds(dist: np.ndarray, n_components: int = 2) -> pd.DataFrame:
    """
    MDS clássico (Torgerson, 1952) a partir de uma matriz de distâncias.

    Parâmetros
    ----------
    dist : np.ndarray
        Matriz quadrada simétrica (n x n) de distâncias entre cidades.
    n_components : int
        Número de dimensões (2 => x, y).

    Retorna
    -------
    pd.DataFrame
        Índice = label da cidade (índice da linha/coluna); colunas 'x', 'y'.
    """
    D = np.asarray(dist, dtype=float)

    if D.ndim != 2 or D.shape[0] != D.shape[1]:
        raise ValueError("A matriz de distâncias deve ser quadrada.")
    if not np.allclose(D, D.T, atol=1e-8):
        raise ValueError("A matriz de distâncias deve ser simétrica.")
    if not np.allclose(np.diag(D), 0, atol=1e-8):
        raise ValueError("A diagonal da matriz de distâncias deve ser zero.")

    n = D.shape[0]

    # 1) Distâncias ao quadrado
    D2 = D ** 2

    # 2) Dupla centralização: B = -1/2 * J D² J
    J = np.eye(n) - np.ones((n, n)) / n
    B = -0.5 * J @ D2 @ J

    # 3) Autovalores/autovetores (B é simétrica => eigh)
    eigvals, eigvecs = np.linalg.eigh(B)

    # Ordena em ordem decrescente
    idx = np.argsort(eigvals)[::-1]
    eigvals, eigvecs = eigvals[idx], eigvecs[:, idx]

    # 4) Coordenadas: autovetores * sqrt(autovalores) das k maiores dimensões
    #    (autovalores negativos, devidos a distâncias não-euclidianas, viram 0)
    top_vals = np.clip(eigvals[:n_components], a_min=0, a_max=None)
    coords = eigvecs[:, :n_components] * np.sqrt(top_vals)

    cols = ["x", "y"] if n_components == 2 else [f"dim{i+1}" for i in range(n_components)]
    return pd.DataFrame(coords, columns=cols, index=pd.RangeIndex(n, name="cidade"))


def plot_graph(
    df: pd.DataFrame,
    k_neighbors: int = 2,
    dist: np.ndarray | None = None,
    filename: str = "grafo.png",
    show_labels: bool = True,
) -> None:
    """
    Gera uma imagem do grafo de cidades, conectando cada nó aos seus
    k vizinhos mais próximos e anotando a distância em cada aresta.

    Parâmetros
    ----------
    df : pd.DataFrame
        Saída de torgerson_mds (colunas 'x' e 'y', índice = label da cidade).
    k_neighbors : int
        Número de vizinhos mais próximos por nó a serem desenhados.
        Use n-1 (ou mais) para o grafo completo.
    dist : np.ndarray | None
        Matriz de distâncias original. Se None, usa as distâncias
        euclidianas calculadas a partir das coordenadas de df.
    filename : str
        Caminho da imagem de saída.
    show_labels : bool
        Se True, escreve o valor da distância sobre cada aresta.
    """
    coords = df[["x", "y"]].to_numpy()
    labels = df.index.to_numpy()
    n = len(df)

    if not isinstance(k_neighbors, int) or k_neighbors < 1:
        raise ValueError("k_neighbors deve ser um inteiro >= 1.")
    k = min(k_neighbors, n - 1)

    D = cdist(coords, coords) if dist is None else np.asarray(dist, dtype=float)
    if D.shape != (n, n):
        raise ValueError("A matriz de distâncias deve ter shape (n, n).")

    # Arestas: para cada nó, liga aos k mais próximos (sem duplicar i-j / j-i)
    edges = set()
    for i in range(n):
        d = D[i].copy()
        d[i] = np.inf  # ignora o próprio nó
        for j in np.argsort(d)[:k]:
            edges.add((min(i, j), max(i, j)))

    fig, ax = plt.subplots(figsize=(8, 8))

    # Arestas
    for i, j in edges:
        (x1, y1), (x2, y2) = coords[i], coords[j]
        ax.plot([x1, x2], [y1, y2], color="gray", lw=1, zorder=1)
        if show_labels:
            ax.text(
                (x1 + x2) / 2, (y1 + y2) / 2, f"{D[i, j]:.1f}",
                fontsize=8, color="firebrick", ha="center", va="center",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=0.5),
                zorder=2,
            )

    # Nós
    ax.scatter(coords[:, 0], coords[:, 1], s=500, c="skyblue",
               edgecolors="black", zorder=3)
    for (x, y), lab in zip(coords, labels):
        ax.text(x, y, str(lab), ha="center", va="center",
                fontsize=10, fontweight="bold", zorder=4)

    ax.set_aspect("equal")
    ax.set_title(f"Grafo de cidades ({k} vizinho(s) mais próximo(s) por nó)")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(filename, dpi=150)
    plt.close(fig)
    print(f"Imagem salva em: {filename}")


# ---------------------------------------------------------------------------
# Teste
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    filepath = "../../../data/instances/distancia.csv"
    D = pd.read_csv(filepath, header=None).to_numpy()


    df = torgerson_mds(D)
    print(df)
    
    # Grafo com 2 vizinhos por nó
    plot_graph(df, k_neighbors=2, dist=D, filename="grafo_k2.png")

    # Grafo completo (todos conectados a todos)
    plot_graph(df, k_neighbors=20, dist=D, filename="grafo_completo.png")

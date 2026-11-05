# Guia de Integração e Uso do NeuroLKH como Dependência

Este documento especifica a arquitetura e os procedimentos necessários para integrar o [NeuroLKH](https://github.com/liangxinedu/NeuroLKH) como um submódulo/dependência em seu próprio projeto Python.

## 1. Requisito Crítico: Versão do Python e Downgrade

> **ATENÇÃO:** O projeto **NÃO deve utilizar o Python 3.12**. É obrigatório realizar o downgrade/configuração do ambiente para **Python 3.10** (ou 3.11).

### Motivo do Downgrade (Python 3.12 vs C-API / SWIG)

1. **Remoção de Macros da C-API:** O Python 3.12 removeu definitivamente diversas funções e macros legadas da C-API (como `PyUnicode_GET_SIZE`, `PyEval_InitThreads` e estruturas opacas de `PyObject`). O código da interface C/C++ do LKH gerado pelo SWIG no repositório NeuroLKH depende dessas rotinas. Tentar compilar ou rodar o wrapper em C no Python 3.12 resultará em erros fatais de compilação C (`incomplete type`, `undeclared identifier`) ou *Segmentation Faults*.
2. **Compatibilidade PyTorch / PyG:** As dependências de rede neural esparsa do repositório possuem extensões em C++ otimizadas para versões anteriores da ABI do Python.

---

### 1.1 Configuração do Ambiente Virtual Local (Python 3.10)

No ambiente de desenvolvimento local, crie e ative um ambiente utilizando o **Python 3.10**:

#### Via Conda / Mamba (Recomendado):
```bash
conda create -n neurolkh_env python=3.10 -y
conda activate neurolkh_env
```

#### Via Virtualenv (no Linux/macOS):
```bash
# Garantir que o python3.10 está instalado no SO (ex: sudo apt install python3.10 python3.10-dev)
python3.10 -m venv venv
source venv/bin/activate
```

---

### 1.2 Configuração do Container Docker (Downgrade na Imagem)

Se a sua aplicação roda dentro de um container Docker, certifique-se de definir a imagem base com **Python 3.10**. 

Exemplo de `Dockerfile` configurado para a integração:

```dockerfile
# Utilizar imagem oficial com Python 3.10
FROM python:3.10-slim

# Instalar dependências de sistema necessárias para compilação SWIG e C
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    swig \
    python3.10-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar arquivos do projeto
COPY . /app

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Compilar o LKH C via SWIG
RUN bash third_party/NeuroLKH/build_neurolkh_swig.sh

CMD ["python", "main.py"]
```

---

## 2. Estrutura e Inclusão do Submódulo no seu Projeto

Para gerenciar o NeuroLKH de forma modular, adicione-o como um **Git Submodule** dentro do seu projeto.

### 2.1 Adicionando o Submódulo

No terminal da raiz do seu projeto:

```bash
git submodule add https://github.com/liangxinedu/NeuroLKH.git third_party/NeuroLKH
git submodule update --init --recursive
```

### 2.2 Estrutura do Projeto Recomendada

```
seu_projeto/
│
├── third_party/
│   └── NeuroLKH/            # Repositório clonado como submódulo
│       ├── LKH-3.0.6/
│       ├── pretrained/      # Modelos pré-treinados
│       ├── setup.sh
│       ├── train.py
│       └── ...
│
├── data/                    # Instâncias de teste/treino do TSP (.pkl ou .tsp)
├── src/
│   └── solver_wrapper.py    # Seu código chamando o NeuroLKH
├── Dockerfile               # Configurado com Python 3.10
├── requirements.txt
└── main.py
```

---

## 3. Compilação do LKH via SWIG (Python 3.10)

Com o Python 3.10 ativo (no container ou venv), compile o wrapper C do LKH executando o SWIG.

### 3.1 Script de Automação de Build (`build_neurolkh_swig.sh`)

Crie este script na raiz do seu projeto ou dentro da pasta do submódulo:

```bash
#!/usr/bin/env bash
set -e

echo "=== Compilando C-LKH com SWIG para Python 3.10 ==="

cd third_party/NeuroLKH/LKH-3.0.6

# 1. Gerar a interface C/Python via SWIG
swig -python LKH.i

# 2. Obter diretório de inclusão dos headers do Python 3.10
PYTHON_INC=$(python3 -c "import sysconfig; print(sysconfig.get_path('include'))")

# 3. Compilar os objetos C e a biblioteca compartilhada
gcc -O3 -fPIC -c LKH.c LKH_wrap.c -I"${PYTHON_INC}"
gcc -shared LKH.o LKH_wrap.o -o _LKH.so

echo "=== Compilação concluída com sucesso! ==="
```

---

## 4. Fluxo de Treinamento de um Modelo para 250 Nós (Customers)

Os modelos pré-treinados em `pretrained/neurolkh.pt` geralmente foram treinados para instâncias menores (ex: TSP-100) e finetunados/testados para tamanhos maiores. Para obter o desempenho máximo focado especificamente em **250 clientes**, execute os passos abaixo no seu ambiente Python 3.10:

### Step 1: Gerar o Dataset de Treino e Validação

Gere dados sintéticos de TSP com 250 nós:

```bash
cd third_party/NeuroLKH

# Gera instâncias de treino (com soluções para rotulagem de arestas via LKH)
python data_generate.py -train --n_nodes 250 --n_samples 10000 --save_dir data/tsp250_train.pkl

# Gera instâncias de validação
python data_generate.py -val --n_nodes 250 --n_samples 100 --save_dir data/tsp250_val.pkl
```

### Step 2: Treinar a Sparse Graph Network (SGN)

Execute o treinamento configurando os parâmetros de nó para 250:

```bash
CUDA_VISIBLE_DEVICES="0" python train.py \
  --file_path data/tsp250_train.pkl \
  --eval_file_path data/tsp250_val.pkl \
  --n_nodes 250 \
  --eval_batch_size 50 \
  --save_dir saved/tsp250_neurolkh \
  --learning_rate 0.0001
```

### Step 3: Finetune da Decodificação de Nós (Node Decoder)

Para ajustar o decodificador de penalidades aos grafos de tamanho 250:

```bash
CUDA_VISIBLE_DEVICES="0" python finetune_node.py \
  --model_path saved/tsp250_neurolkh/best_model.pt \
  --n_nodes 250
```

*O checkpoint resultante em `saved/tsp250_neurolkh/best_model.pt` será o seu modelo dedicado para 250 clientes.*

---

## 5. Executando a Otimização no Seu Projeto (Python Integration)

Abaixo está o módulo em Python dentro da sua aplicação (`src/solver_wrapper.py`) importando o NeuroLKH e utilizando as chamadas C via SWIG no ambiente Python 3.10.

```python
import sys
import os
import torch
import numpy as np

# Adicionar a pasta do NeuroLKH e LKH ao sys.path para importação de submódulos
NEUROLKH_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../third_party/NeuroLKH"))
LKH_BUILD_DIR = os.path.join(NEUROLKH_DIR, "LKH-3.0.6")

for path in [NEUROLKH_DIR, LKH_BUILD_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Importar componentes de C via SWIG e módulos PyTorch do NeuroLKH
try:
    import LKH  # Modulo C envelopado via SWIG
except ImportError as e:
    raise RuntimeError("Módulo SWIG LKH não compilado. Execute o script de build primeiro.") from e

from net.sg_net import SparseGraphNet

class NeuroLKHSolver:
    def __init__(self, model_path: str, device: str = "cuda"):
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        self.model = SparseGraphNet(n_layers=3).to(self.device)
        
        if os.path.exists(model_path):
            checkpoint = torch.load(model_path, map_location=self.device)
            self.model.load_state_dict(checkpoint['model'] if 'model' in checkpoint else checkpoint)
            self.model.eval()
            print(f"[NeuroLKH] Modelo carregado com sucesso de: {model_path}")
        else:
            raise FileNotFoundError(f"Modelo não encontrado em: {model_path}")

    def solve_instance(self, node_coords: np.ndarray, lkh_trials: int = 1000) -> tuple[float, list[int]]:
        """
        Executa a otimização NeuroLKH para uma lista de coordenadas 2D.
        :param node_coords: Array numpy de shape (N, 2) contendo coordenadas normalizadas [0, 1].
        :param lkh_trials: Número de tentativas para a heurística LKH.
        :return: Tupla contendo (distância_total, lista_indices_da_rota)
        """
        num_nodes = len(node_coords)
        tensor_coords = torch.tensor(node_coords, dtype=torch.float32).unsqueeze(0).to(self.device)

        # 1. Inferência com a rede neural (Cálculo de penalidades de nó e scores de aresta)
        with torch.no_grad():
            edge_index, edge_scores, node_penalties = self.model(tensor_coords)

        # 2. Transforma as predições para entradas formatadas para a C-API do LKH via SWIG
        edge_scores_np = edge_scores.squeeze(0).cpu().numpy()
        node_penalties_np = node_penalties.squeeze(0).cpu().numpy()
        
        # 3. Chamada ao Solver C (SWIG)
        tour, tour_length = LKH.solve_tsp(
            node_coords.tolist(),
            edge_scores_np.tolist(),
            node_penalties_np.tolist(),
            lkh_trials
        )

        return tour_length, tour

# Exemplo de uso direto
if __name__ == "__main__":
    # Instância sintética com 250 clientes
    np.random.seed(42)
    sample_nodes = np.random.rand(250, 2)

    model_file = os.path.join(NEUROLKH_DIR, "pretrained/neurolkh.pt")
    solver = NeuroLKHSolver(model_path=model_file)
    
    cost, tour = solver.solve_instance(sample_nodes, lkh_trials=500)
    print(f"Custo total da rota: {cost}")
    print(f"Tamanho da rota encontrada: {len(tour)} nós")
```

---

## 6. Checklist de Resolução de Problemas (Troubleshooting)

1. **`Erros de compilação no SWIG / C-API`**
   * Verifique se o ambiente (local ou container) está rodando estritamente com **Python 3.10** (`python --version`). Se estiver no Python 3.12, o erro persistirá.

2. **`ModuleNotFoundError: No module named '_LKH'`**
   * Confirme que o arquivo `_LKH.so` gerado pelo GCC está no diretório `third_party/NeuroLKH/LKH-3.0.6` e que essa pasta foi adicionada ao `sys.path`.

3. **`Fatal error: Python.h: No such file or directory`**
   * Certifique-se de instalar os pacotes dev no sistema operacional (`python3.10-dev`).
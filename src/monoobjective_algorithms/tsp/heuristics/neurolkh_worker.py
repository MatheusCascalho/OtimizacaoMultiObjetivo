#!/usr/bin/env python3
"""Python 3.11 entry point for one NeuroLKH solve.

The project interpreter is 3.12, which cannot import the SWIG module. This
process loads the pretrained SparseGCNModel, asks LKH for edge features, and
calls the wrapped solver on the explicit integer cost matrix.

Real entry points, matching upstream ``swig_test.py``:

- ``SRC_swig.LKH.featureGenerate``
- ``SRC_swig.LKH.main`` (imported there as ``LKH``)
- ``net.sgcn_model.SparseGCNModel.forward``

``LKH.solve_tsp`` does not exist in the upstream repository.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import numpy as np


N_EDGES = 20


def _fail(output_path: Path, message: str) -> None:
    output_path.write_text(json.dumps({"ok": False, "error": message}), encoding="utf-8")
    print(message, file=sys.stderr)
    raise SystemExit(1)


def _load_model(model_path: Path, device: object):
    import torch
    from net.sgcn_model import SparseGCNModel

    if not model_path.is_file():
        raise FileNotFoundError(f"pretrained NeuroLKH checkpoint not found: {model_path}")
    network = SparseGCNModel()
    network.to(device)
    try:
        checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    except TypeError:
        checkpoint = torch.load(model_path, map_location=device)
    if isinstance(checkpoint, dict) and "model" in checkpoint:
        state = checkpoint["model"]
    else:
        state = checkpoint
    network.load_state_dict(state)
    network.eval()
    return network


def _features(coordinates: np.ndarray, seed: int):
    from SRC_swig.LKH import featureGenerate

    node_count = int(coordinates.shape[0])
    invec = np.concatenate(
        [
            np.asarray(coordinates, dtype=np.float64).reshape(-1) * 1_000_000.0,
            np.zeros(node_count * (3 * N_EDGES - 2), dtype=np.float64),
        ]
    )
    invec = np.ascontiguousarray(invec, dtype=np.float64)
    featureGenerate(int(seed), invec)
    edge_index = invec[: node_count * N_EDGES].reshape(1, node_count, N_EDGES)
    edge_feat = (
        invec[node_count * N_EDGES : node_count * N_EDGES * 2].reshape(1, node_count, N_EDGES)
        / 100_000_000.0
    )
    inverse_edge_index = invec[
        node_count * N_EDGES * 2 : node_count * N_EDGES * 3
    ].reshape(1, node_count, N_EDGES)
    return edge_index, edge_feat, inverse_edge_index


def _candidates(network, coordinates: np.ndarray, edge_index, edge_feat, inverse_edge_index):
    import torch

    node_count = int(coordinates.shape[0])
    node_feat = torch.tensor(coordinates, dtype=torch.float32).unsqueeze(0)
    edge_feat_tensor = torch.tensor(edge_feat, dtype=torch.float32).view(1, -1, 1)
    edge_index_tensor = torch.tensor(edge_index, dtype=torch.float32).view(1, -1)
    inverse_tensor = torch.tensor(inverse_edge_index, dtype=torch.float32).view(1, -1)
    with torch.no_grad():
        edge_scores, _, node_penalties = network.forward(
            node_feat,
            edge_feat_tensor,
            edge_index_tensor,
            inverse_tensor,
            None,
            None,
            N_EDGES,
        )
    scores = edge_scores[:, :, 1].reshape(1, node_count, N_EDGES).detach().cpu().numpy()
    order = np.argsort(-scores, axis=-1)
    chosen = np.take_along_axis(edge_index, order, axis=-1)[:, :, :5]
    penalties = node_penalties.detach().cpu().numpy().reshape(node_count)
    return chosen, penalties


def _solve_lkh(coordinates, candidates, penalties, integer_costs, trials: int, seed: int):
    from SRC_swig.LKH import main as lkh_main

    node_count = int(integer_costs.shape[0])
    body = np.concatenate(
        [
            np.asarray(coordinates, dtype=np.float64).reshape(-1) * 1_000_000.0,
            np.asarray(candidates, dtype=np.float64).reshape(-1),
            np.asarray(penalties, dtype=np.float64).reshape(-1) * 1_000_000.0,
            np.asarray(integer_costs, dtype=np.float64).reshape(-1),
        ]
    )
    length = max(int(body.size), 2 * int(trials))
    if body.size < length:
        body = np.concatenate([body, np.zeros(length - body.size, dtype=np.float64)])
    invec = np.ascontiguousarray(body, dtype=np.float64)
    lkh_main(1, int(trials), int(seed), node_count, invec)
    tour = [int(round(float(node))) for node in invec[:node_count]]
    if sorted(tour) != list(range(1, node_count + 1)):
        raise RuntimeError(f"LKH did not return a Hamiltonian cycle on {node_count} nodes: {tour}")
    return tour


def _c_seed(seed: int) -> int:
    value = int(seed) % (2**32)
    if value >= 2**31:
        value -= 2**32
    return value


def solve(payload: dict) -> dict:
    from neurolkh_costs import coordinates_from_symmetric_costs, scale_symmetric_costs

    matrix = np.asarray(payload["cost_matrix"], dtype=float)
    trials = int(payload["trials"])
    seed = payload.get("seed")
    c_seed = 1234 if seed is None else _c_seed(int(seed))
    model_path = Path(payload["model_path"])
    integer_costs, _scale = scale_symmetric_costs(matrix)
    coordinates = coordinates_from_symmetric_costs(matrix)

    import torch

    device = torch.device("cpu")
    network = _load_model(model_path, device)
    edge_index, edge_feat, inverse_edge_index = _features(coordinates, c_seed)
    candidates, penalties = _candidates(
        network, coordinates, edge_index, edge_feat, inverse_edge_index
    )
    tour = _solve_lkh(coordinates, candidates, penalties, integer_costs, trials, c_seed)
    return {"ok": True, "tour": tour}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: neurolkh_worker.py OUTPUT.json")
    output_path = Path(sys.argv[1])
    root = Path.cwd()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "SRC_swig"))
    try:
        payload = json.load(sys.stdin)
        result = solve(payload)
    except Exception as error:
        _fail(output_path, f"{type(error).__name__}: {error}\n{traceback.format_exc()}")
    output_path.write_text(json.dumps(result), encoding="utf-8")


if __name__ == "__main__":
    main()

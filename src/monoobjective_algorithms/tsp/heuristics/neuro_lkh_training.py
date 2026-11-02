from __future__ import annotations

import argparse
import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch import Tensor
from torch.nn import functional as F
from torch.utils.data import DataLoader, TensorDataset

from monoobjective_algorithms.tsp.heuristics.neuro_lkh_features import (
    build_graph_features,
)
from monoobjective_algorithms.tsp.heuristics.neuro_lkh_model import SparseGCNModel
from optimization_problems.tsp import TSPInstance

_MAX_EXACT_NODES = 18


@dataclass(frozen=True)
class TrainingExample:
    costs: np.ndarray
    node_features: np.ndarray
    edge_features: np.ndarray
    edge_index: np.ndarray
    inverse_edge_index: np.ndarray
    target_edges: np.ndarray


def generate_synthetic_instance(
    node_count: int,
    rng: np.random.Generator,
) -> TSPInstance:
    if isinstance(node_count, bool) or not isinstance(node_count, int):
        raise ValueError("node_count must be an integer")
    if not 3 <= node_count <= _MAX_EXACT_NODES:
        raise ValueError(f"node_count must be between 3 and {_MAX_EXACT_NODES}")

    coordinates = rng.uniform(0, 1, size=(node_count, 2))
    differences = coordinates[:, None, :] - coordinates[None, :, :]
    distances = np.rint(np.sqrt(np.square(differences).sum(axis=-1)) * 1000)
    speed = rng.uniform(0.65, 1.35, size=(node_count, node_count))
    times = np.divide(
        distances,
        speed,
        out=np.zeros_like(distances),
        where=distances != 0,
    )
    np.fill_diagonal(distances, 0)
    np.fill_diagonal(times, 0)
    return TSPInstance(time_matrix=times, distance_matrix=distances)


def held_karp_tour(costs: Sequence[Sequence[float]]) -> tuple[int, ...]:
    matrix = np.asarray(costs, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("cost matrix must be square")
    n_nodes = len(matrix)
    if not 3 <= n_nodes <= _MAX_EXACT_NODES:
        raise ValueError(f"exact labels support 3 to {_MAX_EXACT_NODES} nodes")
    if not np.isfinite(matrix).all():
        raise ValueError("cost matrix must contain only finite numbers")

    subset_count = n_nodes - 1
    state_count = 1 << subset_count
    dynamic = np.full((state_count, subset_count), np.inf, dtype=np.float64)
    parent = np.full((state_count, subset_count), -1, dtype=np.int16)

    for last in range(subset_count):
        dynamic[1 << last, last] = matrix[0, last + 1]

    for mask in range(1, state_count):
        for last in range(subset_count):
            last_bit = 1 << last
            if not mask & last_bit or mask == last_bit:
                continue
            previous_mask = mask ^ last_bit
            previous_nodes = [
                node for node in range(subset_count) if previous_mask & (1 << node)
            ]
            previous_costs = [
                dynamic[previous_mask, previous]
                + matrix[previous + 1, last + 1]
                for previous in previous_nodes
            ]
            best_index = min(
                range(len(previous_nodes)),
                key=lambda index: (previous_costs[index], previous_nodes[index]),
            )
            dynamic[mask, last] = previous_costs[best_index]
            parent[mask, last] = previous_nodes[best_index]

    full_mask = state_count - 1
    final_nodes = range(subset_count)
    last = min(
        final_nodes,
        key=lambda node: (
            dynamic[full_mask, node] + matrix[node + 1, 0],
            node,
        ),
    )
    route_reversed = [last + 1]
    mask = full_mask
    while True:
        previous = int(parent[mask, last])
        mask ^= 1 << last
        if previous < 0:
            break
        route_reversed.append(previous + 1)
        last = previous
    return (0, *reversed(route_reversed))


def _minimum_one_tree_degrees(
    costs: np.ndarray,
    penalties: np.ndarray,
) -> np.ndarray:
    symmetric_costs = (costs + costs.T) / 2
    modified = symmetric_costs + penalties[:, None] + penalties[None, :]
    np.fill_diagonal(modified, np.inf)
    n_nodes = len(modified)
    degrees = np.zeros(n_nodes, dtype=np.float32)

    in_tree = np.zeros(n_nodes, dtype=bool)
    in_tree[1] = True
    best_edges = modified[1].copy()
    best_edges[0] = np.inf
    for _ in range(n_nodes - 2):
        next_node = min(
            (node for node in range(1, n_nodes) if not in_tree[node]),
            key=lambda node: (best_edges[node], node),
        )
        parent_node = int(np.argmin(np.where(in_tree, modified[next_node], np.inf)))
        degrees[next_node] += 1
        degrees[parent_node] += 1
        in_tree[next_node] = True
        best_edges = np.minimum(best_edges, modified[next_node])

    root_neighbors = sorted(
        range(1, n_nodes), key=lambda node: (modified[0, node], node)
    )[:2]
    degrees[0] = 2
    for node in root_neighbors:
        degrees[node] += 1
    return degrees


def generate_training_examples(
    sample_count: int,
    node_count: int,
    seed: int = 1234,
) -> list[TrainingExample]:
    if isinstance(sample_count, bool) or not isinstance(sample_count, int):
        raise ValueError("sample_count must be an integer")
    if sample_count < 1:
        raise ValueError("sample_count must be positive")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")

    rng = np.random.default_rng(seed)
    examples = []
    for _ in range(sample_count):
        instance = generate_synthetic_instance(node_count, rng)
        objective = ("time", "distance")[int(rng.integers(0, 2))]
        costs = np.asarray(
            instance.time_matrix if objective == "time" else instance.distance_matrix,
            dtype=np.float64,
        )
        tour = held_karp_tour(costs)
        node_features, edge_features, edge_index, inverse, _ = build_graph_features(
            costs, node_count - 1
        )
        positions = {
            (source, int(target)): position
            for source, neighbors in enumerate(edge_index[0])
            for position, target in enumerate(neighbors)
        }
        targets = np.asarray(
            [
                positions[source, tour[(index + 1) % node_count]]
                for index, source in enumerate(tour)
            ],
            dtype=np.int64,
        )
        examples.append(
            TrainingExample(
                costs=costs.astype(np.float32),
                node_features=node_features[0],
                edge_features=edge_features[0],
                edge_index=edge_index[0],
                inverse_edge_index=inverse[0],
                target_edges=targets,
            )
        )
    return examples


def _to_tensor_dataset(examples: Sequence[TrainingExample]) -> TensorDataset:
    if not examples:
        raise ValueError("at least one training example is required")
    return TensorDataset(
        torch.from_numpy(np.stack([item.costs for item in examples])),
        torch.from_numpy(np.stack([item.node_features for item in examples])),
        torch.from_numpy(np.stack([item.edge_features for item in examples])),
        torch.from_numpy(np.stack([item.edge_index for item in examples])),
        torch.from_numpy(np.stack([item.inverse_edge_index for item in examples])),
        torch.from_numpy(np.stack([item.target_edges for item in examples])),
    )


def train_model(
    examples: Sequence[TrainingExample],
    *,
    epochs: int = 20,
    batch_size: int = 16,
    learning_rate: float = 1e-4,
    node_penalty_weight: float = 1.0,
    seed: int = 1234,
    hidden_dim: int = 128,
    gcn_layers: int = 30,
    mlp_layers: int = 3,
    device: str = "cpu",
) -> tuple[SparseGCNModel, list[float]]:
    for name, value in (("epochs", epochs), ("batch_size", batch_size)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if learning_rate <= 0 or not np.isfinite(learning_rate):
        raise ValueError("learning_rate must be finite and positive")
    if node_penalty_weight < 0 or not np.isfinite(node_penalty_weight):
        raise ValueError("node_penalty_weight must be finite and non-negative")
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but is not available")

    torch.manual_seed(seed)
    loader = DataLoader(
        _to_tensor_dataset(examples),
        batch_size=batch_size,
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    model = SparseGCNModel(
        hidden_dim=hidden_dim,
        n_gcn_layers=gcn_layers,
        n_mlp_layers=mlp_layers,
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    history = []

    for _ in range(epochs):
        model.train()
        epoch_losses = []
        for costs, nodes, edges, edge_index, inverse_index, targets in loader:
            costs = costs.to(device)
            nodes = nodes.to(device)
            edges = edges.to(device).view(len(nodes), -1, 1)
            edge_index = edge_index.to(device).reshape(len(nodes), -1)
            inverse_index = inverse_index.to(device)
            targets = targets.to(device)

            edge_probabilities, predicted_penalties = model(
                nodes,
                edges,
                edge_index,
                inverse_index,
                examples[0].edge_index.shape[1],
            )
            edge_loss = F.nll_loss(
                torch.log(edge_probabilities.clamp_min(1e-8)).reshape(-1, edge_probabilities.shape[-1]),
                targets.reshape(-1),
            )

            degrees = np.stack(
                [
                    _minimum_one_tree_degrees(
                        costs[index].detach().cpu().numpy(),
                        predicted_penalties[index, :, 0].detach().cpu().numpy(),
                    )
                    for index in range(len(nodes))
                ]
            )
            degree_tensor = torch.from_numpy(degrees).to(device)
            penalty_loss = -(
                (degree_tensor - 2) * predicted_penalties[:, :, 0]
            ).mean()
            loss = edge_loss + node_penalty_weight * penalty_loss
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            epoch_losses.append(float(loss.detach().cpu()))
        history.append(float(np.mean(epoch_losses)))

    return model, history


def save_checkpoint(
    model: SparseGCNModel,
    path: str | Path,
    *,
    node_count: int,
    candidate_count: int,
) -> None:
    checkpoint_path = Path(path)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model": model.cpu().state_dict(),
            "model_config": {
                "node_dim": 4,
                "hidden_dim": model.nodes_embedding.out_features,
                "gcn_layers": len(model.gcn_layers),
                "mlp_layers": model.mlp_edges.L,
                "candidate_count": candidate_count,
                "training_node_count": node_count,
            },
        },
        checkpoint_path,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a NeuroLKH SGN on synthetic TSPs")
    parser.add_argument("--samples", type=int, default=2048)
    parser.add_argument("--nodes", type=int, default=12)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--node-penalty-weight", type=float, default=1.0)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--gcn-layers", type=int, default=30)
    parser.add_argument("--mlp-layers", type=int, default=3)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", type=Path, default=Path("models/neuro_lkh.pt"))
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    examples = generate_training_examples(args.samples, args.nodes, args.seed)
    model, history = train_model(
        examples,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        node_penalty_weight=args.node_penalty_weight,
        seed=args.seed,
        hidden_dim=args.hidden_dim,
        gcn_layers=args.gcn_layers,
        mlp_layers=args.mlp_layers,
        device=args.device,
    )
    save_checkpoint(
        model,
        args.output,
        node_count=args.nodes,
        candidate_count=args.nodes - 1,
    )
    print(f"saved {args.output}; final_loss={history[-1]:.6f}")


if __name__ == "__main__":
    main()

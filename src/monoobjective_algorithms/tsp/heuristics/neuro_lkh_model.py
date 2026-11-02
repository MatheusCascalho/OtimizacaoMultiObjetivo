from __future__ import annotations

import torch
from torch import Tensor, nn
from torch.nn import functional as F


class _BatchNormNode(nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.batch_norm = nn.BatchNorm1d(hidden_dim, track_running_stats=False)

    def forward(self, values: Tensor) -> Tensor:
        return self.batch_norm(values.transpose(1, 2).contiguous()).transpose(1, 2)


class _NodeFeatures(nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.node_embedding = nn.Linear(hidden_dim, hidden_dim)
        self.to_embedding = nn.Linear(hidden_dim, hidden_dim)
        self.edge_embedding = nn.Linear(hidden_dim, hidden_dim)

    def forward(
        self,
        nodes: Tensor,
        edges: Tensor,
        edge_index: Tensor,
        n_edges: int,
    ) -> Tensor:
        batch_size, n_nodes, hidden_dim = nodes.shape
        node_update = self.node_embedding(nodes)
        neighbor_embeddings = self.to_embedding(nodes)[
            torch.arange(batch_size).view(-1, 1), edge_index
        ]
        edge_weights = F.softmax(
            self.edge_embedding(edges).view(batch_size, n_nodes, n_edges, hidden_dim),
            dim=2,
        ).view(batch_size, n_nodes * n_edges, hidden_dim)
        aggregated = (edge_weights * neighbor_embeddings).view(
            batch_size, n_nodes, n_edges, hidden_dim
        ).sum(2)
        return node_update + aggregated


class _EdgeFeatures(nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.U = nn.Linear(hidden_dim, hidden_dim)
        self.V_from = nn.Linear(hidden_dim, hidden_dim)
        self.V_to = nn.Linear(hidden_dim, hidden_dim)
        self.inverse_U = nn.Linear(hidden_dim, hidden_dim)
        self.W_placeholder = nn.Parameter(torch.empty(hidden_dim))
        nn.init.uniform_(self.W_placeholder, -1, 1)

    def forward(
        self,
        nodes: Tensor,
        edges: Tensor,
        edge_index: Tensor,
        inverse_edge_index: Tensor,
        n_edges: int,
    ) -> Tensor:
        batch_size, n_nodes, hidden_dim = nodes.shape
        embedded_edges = self.U(edges)
        inverse_embeddings = torch.cat(
            (
                self.inverse_U(edges),
                self.W_placeholder.view(1, 1, hidden_dim).expand(batch_size, 1, -1),
            ),
            dim=1,
        )
        inverse_embeddings = inverse_embeddings[
            torch.arange(batch_size).view(-1, 1), inverse_edge_index
        ]
        from_embeddings = self.V_from(nodes)
        to_embeddings = self.V_to(nodes)[
            torch.arange(batch_size).view(-1, 1), edge_index
        ]
        endpoint_embeddings = (
            to_embeddings.view(batch_size, n_nodes, n_edges, hidden_dim)
            + from_embeddings.view(batch_size, n_nodes, 1, hidden_dim)
        ).view(batch_size, n_nodes * n_edges, hidden_dim)
        return embedded_edges + endpoint_embeddings + inverse_embeddings


class _SparseGCNLayer(nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.node_feat = _NodeFeatures(hidden_dim)
        self.edge_feat = _EdgeFeatures(hidden_dim)
        self.bn_node = _BatchNormNode(hidden_dim)
        self.bn_edge = _BatchNormNode(hidden_dim)

    def forward(
        self,
        nodes: Tensor,
        edges: Tensor,
        edge_index: Tensor,
        inverse_edge_index: Tensor,
        n_edges: int,
    ) -> tuple[Tensor, Tensor]:
        updated_nodes = nodes + F.relu(
            self.bn_node(self.node_feat(nodes, edges, edge_index, n_edges))
        )
        updated_edges = edges + F.relu(
            self.bn_edge(
                self.edge_feat(
                    updated_nodes, edges, edge_index, inverse_edge_index, n_edges
                )
            )
        )
        return updated_nodes, updated_edges


class _MLP(nn.Module):
    def __init__(self, hidden_dim: int, output_dim: int, n_layers: int) -> None:
        super().__init__()
        self.L = n_layers
        self.U = nn.ModuleList(
            nn.Linear(hidden_dim, hidden_dim) for _ in range(n_layers - 1)
        )
        self.V = nn.Linear(hidden_dim, output_dim)

    def forward(self, values: Tensor) -> Tensor:
        for layer in self.U:
            values = F.relu(layer(values))
        return self.V(values)


class SparseGCNModel(nn.Module):
    """CPU-capable SGN inference model compatible with NeuroLKH TSP weights."""

    def __init__(
        self,
        node_dim: int = 4,
        hidden_dim: int = 128,
        n_gcn_layers: int = 30,
        n_mlp_layers: int = 3,
    ) -> None:
        super().__init__()
        self.nodes_embedding = nn.Linear(node_dim, hidden_dim, bias=False)
        self.edges_embedding = nn.Linear(1, hidden_dim, bias=False)
        self.gcn_layers = nn.ModuleList(
            _SparseGCNLayer(hidden_dim) for _ in range(n_gcn_layers)
        )
        self.mlp_edges = _MLP(hidden_dim, 1, n_mlp_layers)
        self.mlp_nodes = _MLP(hidden_dim, 1, n_mlp_layers)

    def forward(
        self,
        node_features: Tensor,
        edge_features: Tensor,
        edge_index: Tensor,
        inverse_edge_index: Tensor,
        n_edges: int,
    ) -> tuple[Tensor, Tensor]:
        batch_size, n_nodes, _ = node_features.shape
        nodes = self.nodes_embedding(node_features)
        edges = self.edges_embedding(edge_features)
        for layer in self.gcn_layers:
            nodes, edges = layer(
                nodes, edges, edge_index, inverse_edge_index, n_edges
            )
        edge_logits = self.mlp_edges(edges).view(batch_size, n_nodes, n_edges)
        edge_probabilities = F.softmax(edge_logits, dim=2)
        node_penalties = 10 * torch.tanh(self.mlp_nodes(nodes))
        return edge_probabilities, node_penalties

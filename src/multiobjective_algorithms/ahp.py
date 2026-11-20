"""Analytic Hierarchy Process for ranking mapped TSP solutions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isclose, isfinite
from numbers import Real


CRITERIA = (
    {"id": "distance", "label": "Distância", "source": "distance"},
    {"id": "nominalTime", "label": "Tempo", "source": "nominal_time"},
    {"id": "co2Kg", "label": "Emissão de CO2", "source": "co2_kg"},
    {"id": "minmax", "label": "Min-Max Regret", "source": "minmax_regret"},
)
SAATY_SCALE = tuple(
    sorted(
        {
            1.0,
            *(float(value) for value in range(2, 10)),
            *(1.0 / value for value in range(2, 10)),
        }
    )
)
RANDOM_INDEX = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}


def build_pairwise_matrix(
    ids: Sequence[str],
    judgments: Mapping[str, Real] | None = None,
) -> list[list[float]]:
    if not ids:
        raise ValueError("A matriz de comparação precisa ter ao menos um critério.")
    if len(set(ids)) != len(ids):
        raise ValueError("Os identificadores dos critérios devem ser únicos.")
    if judgments is not None and not isinstance(judgments, Mapping):
        raise ValueError("As comparações devem ser informadas como um objeto.")

    provided = judgments or {}
    expected = {f"{ids[row]}:{ids[column]}" for row in range(len(ids)) for column in range(row + 1, len(ids))}
    unknown = set(provided) - expected
    if unknown:
        raise ValueError(f"Comparação desconhecida: {sorted(unknown)[0]}.")

    matrix = [[1.0] * len(ids) for _ in ids]
    for row in range(len(ids)):
        for column in range(row + 1, len(ids)):
            key = f"{ids[row]}:{ids[column]}"
            value = provided.get(key, 1.0)
            if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
                raise ValueError(f"A comparação {key} deve ser um valor finito da escala de Saaty.")
            if not any(isclose(value, option, rel_tol=1e-9, abs_tol=1e-12) for option in SAATY_SCALE):
                raise ValueError(f"A comparação {key} deve usar a escala de Saaty de 1/9 a 9.")
            matrix[row][column] = float(value)
            matrix[column][row] = 1.0 / float(value)
    return matrix


def priority_vector(matrix: Sequence[Sequence[Real]]) -> list[float]:
    count = len(matrix)
    if not count or any(len(row) != count for row in matrix):
        raise ValueError("A matriz de comparação precisa ser quadrada e não vazia.")
    values = []
    for row in matrix:
        numeric_row = []
        for value in row:
            if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value) or value <= 0:
                raise ValueError("A matriz deve conter apenas valores positivos e finitos.")
            numeric_row.append(float(value))
        values.append(numeric_row)
    column_sums = [sum(values[row][column] for row in range(count)) for column in range(count)]
    return [
        sum(values[row][column] / column_sums[column] for column in range(count)) / count
        for row in range(count)
    ]


def consistency(matrix: Sequence[Sequence[Real]], weights: Sequence[Real]) -> dict[str, float]:
    count = len(matrix)
    if count != len(weights) or count not in RANDOM_INDEX:
        raise ValueError("A razão de consistência exige uma matriz de até dez elementos e pesos correspondentes.")
    if count < 3:
        return {"lambda_max": float(count), "consistency_index": 0.0, "ratio": 0.0}
    lambda_max = sum(
        sum(float(value) * float(weights[column]) for column, value in enumerate(row)) / float(weights[index])
        for index, row in enumerate(matrix)
    ) / count
    consistency_index = max(0.0, (lambda_max - count) / (count - 1))
    return {
        "lambda_max": lambda_max,
        "consistency_index": consistency_index,
        "ratio": consistency_index / RANDOM_INDEX[count],
    }


def performance_ratings(values: Sequence[Real]) -> list[float]:
    if not values:
        raise ValueError("É necessário ao menos um desempenho para comparar alternativas.")
    minimum = min(values)
    maximum = max(values)
    if minimum == maximum:
        return [1.0] * len(values)
    return [9.0 - 8.0 * (value - minimum) / (maximum - minimum) for value in values]


def _validated_solutions(solutions: Sequence[Mapping[str, object]]) -> list[dict]:
    if not isinstance(solutions, Sequence) or isinstance(solutions, (str, bytes)) or not solutions:
        raise ValueError("Não há soluções mapeadas para ranquear.")
    if len(solutions) > 10_000:
        raise ValueError("O ranking AHP aceita até 10.000 soluções por execução.")

    normalized_solutions = []
    for index, solution in enumerate(solutions):
        if not isinstance(solution, Mapping):
            raise ValueError(f"A solução na posição {index + 1} deve ser um objeto.")
        values = {}
        missing = []
        for criterion in CRITERIA:
            value = solution.get(criterion["source"])
            if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value) or value < 0:
                missing.append(criterion["label"])
            else:
                values[criterion["id"]] = float(value)
        if missing:
            solution_id = solution.get("solution_id", f"S{index + 1}")
            raise ValueError(f"A solução {solution_id} não tem valores válidos para: {', '.join(missing)}.")
        normalized_solutions.append(
            {
                **values,
                "id": str(solution.get("solution_id") or f"solution-{index + 1}"),
                "name": str(solution.get("solution_id") or f"Solução {index + 1}"),
                "label": str(solution.get("label") or f"S{index + 1}"),
            }
        )
    return normalized_solutions


def calculate_alternative_matrix(
    solutions: Sequence[Mapping[str, object]],
    criterion_id: str,
    row_offset: int = 0,
    column_offset: int = 0,
    limit: int = 12,
) -> dict:
    criterion = next((item for item in CRITERIA if item["id"] == criterion_id), None)
    if criterion is None:
        raise ValueError("O critério da matriz de alternativas não é válido.")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (row_offset, column_offset)):
        raise ValueError("Os deslocamentos da matriz devem ser inteiros não negativos.")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("O tamanho do bloco da matriz deve ser um inteiro entre 1 e 50.")

    normalized_solutions = _validated_solutions(solutions)
    ratings = performance_ratings([solution[criterion_id] for solution in normalized_solutions])
    total = len(ratings)
    row_end = min(row_offset + limit, total)
    column_end = min(column_offset + limit, total)
    if row_offset >= total or column_offset >= total:
        raise ValueError("O deslocamento da matriz está fora do intervalo de alternativas.")
    matrix = [
        [ratings[row] / ratings[column] for column in range(column_offset, column_end)]
        for row in range(row_offset, row_end)
    ]
    return {
        "criterion": criterion_id,
        "total": total,
        "row_offset": row_offset,
        "column_offset": column_offset,
        "matrix": matrix,
    }


def calculate_ahp(
    solutions: Sequence[Mapping[str, object]],
    judgments: Mapping[str, Real] | None = None,
) -> dict:
    normalized_solutions = _validated_solutions(solutions)

    criterion_ids = [criterion["id"] for criterion in CRITERIA]
    criteria_matrix = build_pairwise_matrix(criterion_ids, judgments)
    criteria_weights = priority_vector(criteria_matrix)
    local_weights = {}
    for criterion_id in criterion_ids:
        ratings = performance_ratings([solution[criterion_id] for solution in normalized_solutions])
        total_rating = sum(ratings)
        local_weights[criterion_id] = [rating / total_rating for rating in ratings]

    ranking = []
    for index, solution in enumerate(normalized_solutions):
        local = {criterion_id: local_weights[criterion_id][index] for criterion_id in criterion_ids}
        score = sum(criteria_weights[position] * local[criterion_id] for position, criterion_id in enumerate(criterion_ids))
        ranking.append(
            {
                "solution_id": solution["id"],
                "name": solution["name"],
                "label": solution["label"],
                "distance": solution["distance"],
                "nominal_time": solution["nominalTime"],
                "co2_kg": solution["co2Kg"],
                "minmax_regret": solution["minmax"],
                "local": local,
                "score": score,
            }
        )
    ranking.sort(key=lambda solution: (-solution["score"], solution["solution_id"]))

    return {
        "criteria": list(CRITERIA),
        "criteria_matrix": criteria_matrix,
        "criteria_weights": dict(zip(criterion_ids, criteria_weights, strict=True)),
        "consistency": consistency(criteria_matrix, criteria_weights),
        "ranking": ranking,
    }

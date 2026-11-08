import pytest

from multiobjective_algorithms.ahp import (
    build_pairwise_matrix,
    calculate_alternative_matrix,
    calculate_ahp,
    consistency,
    priority_vector,
)


def _solutions() -> list[dict]:
    return [
        {
            "solution_id": "route-a",
            "label": "S1",
            "distance": 4,
            "nominal_time": 9,
            "co2_kg": 12,
            "minmax_regret": 0.08,
        },
        {
            "solution_id": "route-b",
            "label": "S2",
            "distance": 6,
            "nominal_time": 7,
            "co2_kg": 10,
            "minmax_regret": 0.03,
        },
    ]


def test_saaty_documentation_example_weights_and_consistency() -> None:
    matrix = build_pairwise_matrix(
        ["price", "quality", "time"],
        {"price:quality": 1 / 3, "price:time": 3, "quality:time": 5},
    )
    weights = priority_vector(matrix)

    assert weights == pytest.approx([0.26, 0.633, 0.106], abs=0.01)
    assert consistency(matrix, weights)["ratio"] <= 0.1


def test_inconsistent_judgments_are_reported_by_consistency_ratio() -> None:
    matrix = build_pairwise_matrix(
        ["a", "b", "c"],
        {"a:b": 9, "a:c": 1, "b:c": 9},
    )

    assert consistency(matrix, priority_vector(matrix))["ratio"] > 0.1


def test_ahp_ranks_routes_using_all_four_criteria() -> None:
    result = calculate_ahp(
        _solutions(),
        {
            "distance:nominalTime": 3,
            "distance:co2Kg": 1 / 3,
            "distance:minmax": 5,
            "nominalTime:co2Kg": 1 / 5,
            "nominalTime:minmax": 1 / 3,
            "co2Kg:minmax": 7,
        },
    )

    assert [item["solution_id"] for item in result["ranking"]] == ["route-b", "route-a"]
    assert sum(result["criteria_weights"].values()) == pytest.approx(1)
    assert sum(item["score"] for item in result["ranking"]) == pytest.approx(1)
    assert set(result["ranking"][0]["local"]) == {"distance", "nominalTime", "co2Kg", "minmax"}
    assert len(result["criteria_matrix"]) == 4
    assert "local_matrices" not in result


def test_alternative_matrix_returns_only_the_requested_page() -> None:
    solutions = _solutions() * 8
    page = calculate_alternative_matrix(
        solutions,
        "distance",
        row_offset=12,
        column_offset=12,
    )

    assert page["total"] == 16
    assert page["row_offset"] == 12
    assert page["column_offset"] == 12
    assert len(page["matrix"]) == 4
    assert len(page["matrix"][0]) == 4


@pytest.mark.parametrize(
    ("judgments", "message"),
    [
        ({"distance:nominalTime": 2.5}, "escala de Saaty"),
        ({"unknown:pair": 3}, "desconhecida"),
        ({"distance:nominalTime": True}, "finito"),
    ],
)
def test_invalid_pairwise_judgments_are_rejected(judgments: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        calculate_ahp(_solutions(), judgments)


def test_missing_metric_does_not_produce_a_fake_ranking() -> None:
    solution = _solutions()[0]
    solution["co2_kg"] = None

    with pytest.raises(ValueError, match="Emissão de CO2"):
        calculate_ahp([solution])

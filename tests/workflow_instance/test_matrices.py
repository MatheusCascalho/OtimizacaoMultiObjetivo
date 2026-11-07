import pytest

from workflow_instance.domain.matrices import (
    MatrixValidationError,
    parse_matrix_csv,
    validate_matrix_pair,
)


def test_parse_matrix_accepts_utf8_bom_and_preserves_asymmetry() -> None:
    matrix = parse_matrix_csv(
        b"\xef\xbb\xbf0,2\n3,0\n",
        "time.csv",
    )

    assert matrix == ((0.0, 2.0), (3.0, 0.0))


@pytest.mark.parametrize(
    ("content", "code", "row", "column"),
    [
        (b"0,1\n2\n", "invalid_matrix_dimensions", None, None),
        (b"0,-1\n2,0\n", "invalid_matrix_value", 1, 2),
        (b"0,nan\n2,0\n", "invalid_matrix_value", 1, 2),
        (b"1,2\n2,0\n", "invalid_matrix_diagonal", 1, 1),
        (b"0,abc\n2,0\n", "invalid_matrix_value", 1, 2),
        (b"0,1\n", "invalid_matrix_dimensions", None, None),
    ],
)
def test_parse_matrix_rejects_invalid_content(
    content: bytes,
    code: str,
    row: int | None,
    column: int | None,
) -> None:
    with pytest.raises(MatrixValidationError) as error:
        parse_matrix_csv(content, "matrix.csv")

    assert error.value.code == code
    assert error.value.details[0].get("row") == row
    assert error.value.details[0].get("column") == column


def test_parse_matrix_rejects_oversized_and_non_utf8_files() -> None:
    with pytest.raises(MatrixValidationError, match="limite") as oversized:
        parse_matrix_csv(b"0,0\n0,0\n", "matrix.csv", max_bytes=3)
    assert oversized.value.code == "file_too_large"

    with pytest.raises(MatrixValidationError) as invalid_encoding:
        parse_matrix_csv(b"\xff", "matrix.csv")
    assert invalid_encoding.value.code == "invalid_matrix_encoding"


def test_validate_matrix_pair_requires_matching_node_counts() -> None:
    time_matrix = parse_matrix_csv(b"0,1\n1,0\n", "time.csv")
    distance_matrix = parse_matrix_csv(b"0,1,2\n1,0,3\n2,3,0\n", "distance.csv")

    with pytest.raises(MatrixValidationError) as error:
        validate_matrix_pair(time_matrix, distance_matrix)

    assert error.value.code == "matrix_dimension_mismatch"
    assert error.value.details == [{"file": "distance_matrix"}]
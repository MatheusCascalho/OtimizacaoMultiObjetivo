import csv
import io
from math import isfinite


DEFAULT_MAX_MATRIX_BYTES = 10 * 1024 * 1024


class MatrixValidationError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        file_name: str,
        row: int | None = None,
        column: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = [{key: value for key, value in {
            "file": file_name,
            "row": row,
            "column": column,
        }.items() if value is not None}]


def parse_matrix_csv(
    content: bytes,
    file_name: str,
    max_bytes: int = DEFAULT_MAX_MATRIX_BYTES,
) -> tuple[tuple[float, ...], ...]:
    if len(content) > max_bytes:
        raise MatrixValidationError(
            "file_too_large",
            "O arquivo excede o limite de tamanho permitido.",
            file_name,
        )

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise MatrixValidationError(
            "invalid_matrix_encoding",
            "O arquivo deve usar codificação UTF-8.",
            file_name,
        ) from error

    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error as error:
        raise MatrixValidationError(
            "invalid_matrix_csv",
            "O arquivo não contém um CSV válido.",
            file_name,
        ) from error

    size = len(rows)
    if size < 2 or any(len(row) != size for row in rows):
        raise MatrixValidationError(
            "invalid_matrix_dimensions",
            "A matriz deve ser quadrada e conter ao menos dois nós.",
            file_name,
        )

    matrix: list[tuple[float, ...]] = []
    for row_index, row in enumerate(rows):
        values: list[float] = []
        for column_index, raw_value in enumerate(row):
            try:
                value = float(raw_value)
            except (TypeError, ValueError, OverflowError) as error:
                raise MatrixValidationError(
                    "invalid_matrix_value",
                    "Cada célula da matriz deve conter um número finito.",
                    file_name,
                    row_index + 1,
                    column_index + 1,
                ) from error
            if not isfinite(value) or value < 0:
                raise MatrixValidationError(
                    "invalid_matrix_value",
                    "Cada célula da matriz deve conter um número finito não negativo.",
                    file_name,
                    row_index + 1,
                    column_index + 1,
                )
            if row_index == column_index and value != 0:
                raise MatrixValidationError(
                    "invalid_matrix_diagonal",
                    "A diagonal principal da matriz deve ser zero.",
                    file_name,
                    row_index + 1,
                    column_index + 1,
                )
            values.append(value)
        matrix.append(tuple(values))
    return tuple(matrix)


def validate_matrix_pair(
    time_matrix: tuple[tuple[float, ...], ...],
    distance_matrix: tuple[tuple[float, ...], ...],
) -> None:
    if len(time_matrix) != len(distance_matrix):
        raise MatrixValidationError(
            "matrix_dimension_mismatch",
            "As matrizes de tempo e distância devem ter as mesmas dimensões.",
            "distance_matrix",
        )
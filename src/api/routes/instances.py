from __future__ import annotations

import math
from datetime import UTC, datetime
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select
from sqlalchemy.orm import Session

from infrastructure.persistence.postgres.models import CityLayout, Instance, InstanceFile, TemporaryUpload
from workflow_instance.domain.matrices import parse_matrix_csv


instances_blueprint = Blueprint("instances", __name__, url_prefix="/api/v1")


def _error(code: str, message: str, status: int, details: list[dict] | None = None):
    return (
        jsonify(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or [],
                }
            }
        ),
        status,
    )


def _objective_payload(problem_type: dict, objective_id: str) -> dict | None:
    if not problem_type:
        return None
    for objective in problem_type.get("objectives", []):
        if objective["id"] == objective_id:
            return {
                "id": objective["id"],
                "name": objective["name"],
                "unit": objective.get("unit"),
                "direction": objective.get("direction"),
            }
    return None


def _build_city_layout(node_count: int) -> list[dict[str, float | int]]:
    if node_count <= 0:
        return []
    points: list[dict[str, float | int]] = []
    for city_index in range(node_count):
        angle = (2 * math.pi * city_index) / node_count
        radius = 100.0
        x = round(100.0 + radius * math.cos(angle), 4)
        y = round(100.0 + radius * math.sin(angle), 4)
        points.append({"city_index": city_index, "x": x, "y": y})
    return points


def _ensure_city_layout(instance_id: str, node_count: int, session: Session) -> list[dict[str, float | int]]:
    existing = session.scalars(
        select(CityLayout).where(CityLayout.instance_id == instance_id).order_by(CityLayout.city_index.asc())
    ).all()
    if len(existing) == node_count:
        return [{"city_index": row.city_index, "x": row.x, "y": row.y} for row in existing]

    to_delete = session.scalars(select(CityLayout).where(CityLayout.instance_id == instance_id)).all()
    for row in to_delete:
        session.delete(row)

    layout_points = _build_city_layout(node_count)
    for point in layout_points:
        session.add(
            CityLayout(
                id=f"cl_{uuid4().hex}",
                instance_id=instance_id,
                city_index=int(point["city_index"]),
                x=float(point["x"]),
                y=float(point["y"]),
            )
        )
    session.commit()
    return layout_points


def _get_instance_matrix(instance_id: str, role: str) -> tuple[tuple[float, ...], ...]:
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        file_row = session.scalar(
            select(InstanceFile).where(InstanceFile.instance_id == instance_id, InstanceFile.role == role)
        )
        if file_row is None:
            raise KeyError(f"No {role} matrix file for instance {instance_id}")
        storage = current_app.extensions["paretolab_object_storage"]
        content = storage.get(file_row.object_key)
        matrix = parse_matrix_csv(content, file_row.object_key)
    return matrix


def _instance_payload(instance_id: str, *, include_files: bool = True) -> dict | None:
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        instance = session.get(Instance, instance_id)
        if instance is None:
            return None
        files = session.scalars(
            select(InstanceFile).where(InstanceFile.instance_id == instance_id)
        ).all()
    payload = {
        "instance_id": instance.instance_id,
        "problem_type_id": instance.problem_type_id,
        "catalog_version": instance.catalog_version,
        "name": instance.name,
        "status": instance.status,
        "node_count": instance.node_count,
        "algorithm_id": instance.configuration.get("algorithm_id"),
        "configuration": instance.configuration,
        "created_at": instance.created_at.isoformat(),
    }
    if include_files:
        payload["files"] = {
            row.role: {"upload_id": row.upload_id, "sha256": row.sha256, "size_bytes": row.size_bytes}
            for row in files
        }
    return payload


@instances_blueprint.get("/instances")
def list_instances():
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = max(int(request.args.get("offset", 0)), 0)
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        rows = session.scalars(
            select(Instance).order_by(Instance.created_at.desc()).limit(limit).offset(offset)
        ).all()
    return (
        jsonify(
            {
                "instances": [
                    {
                        "instance_id": row.instance_id,
                        "problem_type_id": row.problem_type_id,
                        "name": row.name,
                        "status": row.status,
                        "node_count": row.node_count,
                        "created_at": row.created_at.isoformat(),
                    }
                    for row in rows
                ],
                "limit": limit,
                "offset": offset,
            }
        ),
        200,
    )


@instances_blueprint.get("/instances/<instance_id>")
def get_instance(instance_id: str):
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        instance = session.get(Instance, instance_id)
        if instance is None:
            return _error("instance_not_found", "A instância solicitada não existe.", 404)
        files = session.scalars(
            select(InstanceFile).where(InstanceFile.instance_id == instance_id)
        ).all()

    return (
        jsonify(
            {
                "instance_id": instance.instance_id,
                "problem_type_id": instance.problem_type_id,
                "catalog_version": instance.catalog_version,
                "name": instance.name,
                "status": instance.status,
                "node_count": instance.node_count,
                "algorithm_id": instance.configuration.get("algorithm_id"),
                "configuration": instance.configuration,
                "files": {
                    row.role: {"upload_id": row.upload_id, "sha256": row.sha256, "size_bytes": row.size_bytes}
                    for row in files
                },
                "created_at": instance.created_at.isoformat(),
            }
        ),
        200,
    )


@instances_blueprint.post("/instances")
def create_instance():
    payload = request.get_json(silent=True) or {}
    problem_type_id = payload.get("problem_type_id")
    name = payload.get("name")
    files = payload.get("files") or {}
    node_order_confirmed = payload.get("node_order_confirmed")
    configuration = payload.get("configuration") or {}

    if not problem_type_id or not name:
        return _error("missing_instance_fields", "Informe o tipo do problema e o nome da instância.", 400)
    if node_order_confirmed is not True:
        return _error("node_order_not_confirmed", "Confirme a ordem dos nós antes de criar a instância.", 422)

    catalog = current_app.extensions["paretolab_catalog"]
    problem_type = catalog.get_problem_type(problem_type_id)
    if problem_type is None:
        return _error("problem_type_not_found", "O tipo de problema solicitado não existe.", 404)

    algorithm_id = configuration.get("algorithm_id")
    available_algorithms = {item["id"] for item in problem_type.get("algorithms", [])}
    if algorithm_id not in available_algorithms:
        return _error("unsupported_algorithm", "O algoritmo selecionado não está disponível para este tipo de problema.", 422)

    upload_ids = {
        "time_matrix": files.get("time_matrix"),
        "distance_matrix": files.get("distance_matrix"),
    }
    if not all(upload_ids.values()):
        return _error("missing_instance_files", "Os arquivos de tempo e distância são obrigatórios.", 422)

    engine = current_app.extensions["paretolab_database_engine"]
    response_configuration = {
        "preview": (request.get_json(silent=True) or {}).get("configuration", {}).get("preview", []),
        "result_views": (request.get_json(silent=True) or {}).get("configuration", {}).get("result_views", []),
        "algorithm_id": (request.get_json(silent=True) or {}).get("configuration", {}).get("algorithm_id"),
    }
    with Session(engine) as session:
        uploads = session.scalars(
            select(TemporaryUpload).where(TemporaryUpload.id.in_([upload for upload in upload_ids.values() if upload]))
        ).all()
        upload_by_id = {upload.id: upload for upload in uploads}
        missing = [role for role, upload_id in upload_ids.items() if upload_id not in upload_by_id]
        if missing:
            return _error("upload_not_found", "Um ou mais uploads não foram encontrados.", 404)

        for role, upload_id in upload_ids.items():
            upload = upload_by_id[upload_id]
            if upload.problem_type_id != problem_type_id:
                return _error("upload_problem_type_mismatch", "O upload não pertence ao tipo de problema selecionado.", 422)
            if upload.role != role:
                return _error("upload_role_mismatch", "O papel do upload não corresponde ao role requisitado.", 422)
            if upload.status != "valid":
                return _error("invalid_upload_status", "O upload não está em estado válido.", 422)

        time_upload = upload_by_id[upload_ids["time_matrix"]]
        distance_upload = upload_by_id[upload_ids["distance_matrix"]]
        if time_upload.node_count != distance_upload.node_count:
            return _error(
                "invalid_upload_dimensions",
                "Os uploads de tempo e distância devem ter o mesmo número de nós.",
                422,
            )

        time_upload_node_count = time_upload.node_count
        instance_id = f"inst_{uuid4().hex}"
        now = datetime.now(UTC)
        instance = Instance(
            instance_id=instance_id,
            problem_type_id=problem_type_id,
            catalog_version=problem_type["version"],
            name=name,
            status="ready",
            configuration=response_configuration,
            node_count=time_upload_node_count,
            created_at=now,
            updated_at=now,
        )
        session.add(instance)
        for role, upload_id in upload_ids.items():
            upload = upload_by_id[upload_id]
            session.add(
                InstanceFile(
                    id=f"if_{uuid4().hex}",
                    instance_id=instance_id,
                    upload_id=upload_id,
                    role=role,
                    object_key=upload.object_key,
                    sha256=upload.sha256,
                    size_bytes=upload.size_bytes,
                    created_at=now,
                )
            )
            upload.consumed_at = now
        layout_points = _ensure_city_layout(instance_id, time_upload_node_count, session)
        session.commit()

    return (
        jsonify(
            {
                "instance_id": instance_id,
                "problem_type_id": problem_type_id,
                "catalog_version": problem_type["version"],
                "name": name,
                "status": "ready",
                "node_count": time_upload_node_count,
                "algorithm_id": response_configuration["algorithm_id"],
                "files": {
                    role: {"upload_id": upload_id}
                    for role, upload_id in upload_ids.items()
                },
                "layout": layout_points,
                "configuration": response_configuration,
                "created_at": now.isoformat(),
            }
        ),
        201,
    )


@instances_blueprint.get("/instances/<instance_id>/analysis/input/matrix")
def get_instance_analysis_matrix(instance_id: str):
    objective_id = request.args.get("objective", "time")
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        instance = session.get(Instance, instance_id)
        if instance is None:
            return _error("instance_not_found", "A instância solicitada não existe.", 404)
        catalog = current_app.extensions["paretolab_catalog"]
        problem_type = catalog.get_problem_type(instance.problem_type_id)
        if problem_type is None:
            return _error("problem_type_not_found", "O tipo de problema associado não foi encontrado.", 404)
        objective = _objective_payload(problem_type, objective_id)
        if objective is None:
            return _error(
                "unsupported_objective",
                "O objetivo solicitado não está disponível para este tipo de problema.",
                422,
            )
        role = f"{objective_id}_matrix"
        try:
            matrix = _get_instance_matrix(instance_id, role)
        except KeyError:
            return _error("missing_instance_matrix", "A matriz solicitada não está disponível para a instância.", 404)
        layout = _ensure_city_layout(instance_id, instance.node_count, session)

    response_nodes = [
        {"id": city_index + 1, "label": str(city_index + 1), "x": point["x"], "y": point["y"]}
        for city_index, point in enumerate(layout)
    ]
    return (
        jsonify(
            {
                "instance_id": instance_id,
                "objective": objective,
                "nodes": response_nodes,
                "matrix": [list(row) for row in matrix],
            }
        ),
        200,
    )


@instances_blueprint.get("/instances/<instance_id>/analysis/input/graph")
def get_instance_analysis_graph(instance_id: str):
    objective_id = request.args.get("objective", "time")
    neighbors_per_city = request.args.get("neighbors_per_city", default="20", type=int)
    if neighbors_per_city is None or neighbors_per_city < 1:
        return _error("invalid_neighbors_per_city", "O número de vizinhos deve ser maior que zero.", 422)

    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        instance = session.get(Instance, instance_id)
        if instance is None:
            return _error("instance_not_found", "A instância solicitada não existe.", 404)
        catalog = current_app.extensions["paretolab_catalog"]
        problem_type = catalog.get_problem_type(instance.problem_type_id)
        if problem_type is None:
            return _error("problem_type_not_found", "O tipo de problema associado não foi encontrado.", 404)
        objective = _objective_payload(problem_type, objective_id)
        if objective is None:
            return _error(
                "unsupported_objective",
                "O objetivo solicitado não está disponível para este tipo de problema.",
                422,
            )
        role = f"{objective_id}_matrix"
        try:
            matrix = _get_instance_matrix(instance_id, role)
        except KeyError:
            return _error("missing_instance_matrix", "A matriz solicitada não está disponível para a instância.", 404)
        layout = _ensure_city_layout(instance_id, instance.node_count, session)

    effective_neighbors = min(neighbors_per_city, max(instance.node_count - 1, 0))
    edges: list[dict[str, int | float]] = []
    for city_index, row in enumerate(matrix):
        ranked = [
            (target_index, value)
            for target_index, value in enumerate(row)
            if target_index != city_index and value >= 0
        ]
        ranked.sort(key=lambda item: (item[1], item[0]))
        for target_index, value in ranked[:effective_neighbors]:
            edges.append({"source": city_index + 1, "target": target_index + 1, "weight": float(value)})

    response_nodes = [
        {"id": city_index + 1, "label": str(city_index + 1), "x": point["x"], "y": point["y"]}
        for city_index, point in enumerate(layout)
    ]
    return (
        jsonify(
            {
                "instance_id": instance_id,
                "objective": objective,
                "neighbors_per_city": {
                    "requested": neighbors_per_city,
                    "effective": effective_neighbors,
                },
                "nodes": response_nodes,
                "edges": edges,
            }
        ),
        200,
    )

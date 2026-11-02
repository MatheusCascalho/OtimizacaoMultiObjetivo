from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select
from sqlalchemy.orm import Session

from infrastructure.persistence.postgres.models import Instance, InstanceFile, TemporaryUpload


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
                "configuration": response_configuration,
                "created_at": now.isoformat(),
            }
        ),
        201,
    )

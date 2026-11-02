import logging
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from werkzeug.exceptions import RequestEntityTooLarge

from infrastructure.persistence.postgres.models import TemporaryUpload
from workflow_instance.domain.matrices import MatrixValidationError, parse_matrix_csv


uploads_blueprint = Blueprint("uploads", __name__, url_prefix="/api/v1")
logger = logging.getLogger(__name__)


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


@uploads_blueprint.app_errorhandler(RequestEntityTooLarge)
def request_too_large(_: RequestEntityTooLarge):
    return _error(
        "file_too_large",
        "O arquivo excede o limite de tamanho permitido.",
        413,
    )


@uploads_blueprint.post("/uploads")
def create_upload():
    problem_type_id = request.form.get("problem_type_id", "")
    role = request.form.get("role", "")
    uploaded_file = request.files.get("file")
    if not problem_type_id or not role or uploaded_file is None:
        return _error(
            "missing_upload_fields",
            "Informe o tipo de problema, o papel e o arquivo.",
            400,
        )

    catalog = current_app.extensions["paretolab_catalog"]
    problem_type = catalog.get_problem_type(problem_type_id)
    if problem_type is None:
        return _error("problem_type_not_found", "O tipo de problema não existe.", 404)
    input_roles = {item["role"] for item in problem_type["inputs"]}
    if role not in input_roles:
        return _error("invalid_file_role", "O papel não é aceito para este tipo de problema.", 422)

    file_name = uploaded_file.filename or ""
    if not file_name or Path(file_name).suffix.lower() != ".csv":
        return _error("invalid_file_format", "Envie um arquivo com extensão CSV.", 422)
    if len(file_name) > 255:
        return _error("invalid_file_name", "O nome do arquivo excede o limite permitido.", 422)

    settings = current_app.extensions["paretolab_settings"]
    content = uploaded_file.stream.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        return _error("file_too_large", "O arquivo excede o limite de tamanho permitido.", 413)
    try:
        matrix = parse_matrix_csv(content, file_name, settings.max_upload_bytes)
    except MatrixValidationError as error:
        status = 413 if error.code == "file_too_large" else 422
        return _error(error.code, str(error), status, error.details)

    upload_id = f"upl_{uuid4().hex}"
    object_key = f"temporary-uploads/{uuid4().hex}"
    digest = sha256(content).hexdigest()
    content_type = "text/csv"
    object_storage = current_app.extensions["paretolab_object_storage"]
    try:
        object_storage.put(
            object_key,
            content,
            content_type,
            {"sha256": digest, "problem-type-id": problem_type_id, "role": role},
        )
    except (BotoCoreError, ClientError):
        logger.exception("Could not store temporary upload")
        return _error("object_storage_unavailable", "O armazenamento está indisponível.", 503)

    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=settings.temporary_upload_ttl_seconds)
    upload = TemporaryUpload(
        id=upload_id,
        problem_type_id=problem_type_id,
        catalog_version=problem_type["version"],
        role=role,
        original_filename=file_name,
        object_key=object_key,
        size_bytes=len(content),
        sha256=digest,
        content_type=content_type,
        node_count=len(matrix),
        status="valid",
        created_at=now,
        expires_at=expires_at,
    )
    try:
        with Session(current_app.extensions["paretolab_database_engine"]) as session:
            session.add(upload)
            session.commit()
    except SQLAlchemyError:
        logger.exception("Could not persist temporary upload metadata")
        try:
            object_storage.delete(object_key)
        except (BotoCoreError, ClientError):
            logger.exception("Could not clean up object after metadata persistence failure")
        return _error("upload_persistence_unavailable", "Não foi possível registrar o upload.", 503)

    return (
        jsonify(
            {
                "upload_id": upload_id,
                "problem_type_id": problem_type_id,
                "role": role,
                "size_bytes": len(content),
                "sha256": digest,
                "node_count": len(matrix),
                "status": "valid",
                "expires_at": expires_at.isoformat(),
            }
        ),
        201,
    )
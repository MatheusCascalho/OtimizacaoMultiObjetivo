from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select
from sqlalchemy.orm import Session

from infrastructure.persistence.postgres.models import Notification


notifications_blueprint = Blueprint("notifications", __name__, url_prefix="/api/v1")


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


@notifications_blueprint.get("/notifications")
def list_notifications():
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = max(int(request.args.get("offset", 0)), 0)
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        rows = session.scalars(
            select(Notification).order_by(Notification.created_at.desc()).limit(limit).offset(offset)
        ).all()
        payload = {
            "notifications": [
                {
                    "notification_id": row.notification_id,
                    "instance_id": row.instance_id,
                    "run_id": row.run_id,
                    "title": row.title,
                    "message": row.message,
                    "is_read": bool(row.is_read),
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ],
            "limit": limit,
            "offset": offset,
        }
    return jsonify(payload), 200


@notifications_blueprint.patch("/notifications/<notification_id>")
def mark_notification_read(notification_id: str):
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        notification = session.get(Notification, notification_id)
        if notification is None:
            return _error("notification_not_found", "A notificação solicitada não existe.", 404)
        notification.is_read = True
        session.commit()
        payload = {
            "notification_id": notification.notification_id,
            "instance_id": notification.instance_id,
            "run_id": notification.run_id,
            "title": notification.title,
            "message": notification.message,
            "is_read": True,
            "created_at": notification.created_at.isoformat(),
        }
    return jsonify(payload), 200

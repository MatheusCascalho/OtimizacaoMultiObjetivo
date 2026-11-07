from flask import Blueprint, current_app, jsonify


problem_types_blueprint = Blueprint("problem_types", __name__, url_prefix="/api/v1")


@problem_types_blueprint.get("/problem-types")
def list_problem_types():
    catalog = current_app.extensions["paretolab_catalog"]
    return jsonify({"problem_types": catalog.list_problem_types()}), 200


@problem_types_blueprint.get("/problem-types/<problem_type_id>")
def get_problem_type(problem_type_id: str):
    catalog = current_app.extensions["paretolab_catalog"]
    problem_type = catalog.get_problem_type(problem_type_id)
    if problem_type is None:
        return (
            jsonify(
                {
                    "error": {
                        "code": "problem_type_not_found",
                        "message": "O tipo de problema solicitado não existe.",
                        "details": [],
                    }
                }
            ),
            404,
        )
    return jsonify(problem_type), 200
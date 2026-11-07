from flask import current_app, request


def get_pagination_args() -> tuple[int, int] | None:
    settings = current_app.extensions.get("paretolab_settings")
    default_limit = getattr(settings, "default_page_size", 50)
    maximum_limit = getattr(settings, "maximum_page_size", 200)
    try:
        limit = int(request.args.get("limit", default_limit))
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        return None
    if limit < 1 or limit > maximum_limit or offset < 0:
        return None
    return limit, offset
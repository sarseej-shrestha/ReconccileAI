"""Preserve large integer amounts when a JSON consumer uses JavaScript numbers."""

from fastapi.responses import JSONResponse

MAX_SAFE_INTEGER = 2**53 - 1


def exact_json(value):
    if isinstance(value, int) and abs(value) > MAX_SAFE_INTEGER:
        return str(value)
    if isinstance(value, dict):
        return {key: exact_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [exact_json(item) for item in value]
    return value


class ExactJSONResponse(JSONResponse):
    def render(self, content):
        return super().render(exact_json(content))

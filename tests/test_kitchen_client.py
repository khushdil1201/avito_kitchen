import httpx

from restaurant_api.kitchen_client import _parse_error_response


def test_kitchen_client_parses_structured_error_envelope() -> None:
    response = httpx.Response(
        409,
        json={
            "error": {
                "code": "conflict",
                "message": "Недопустимый переход статуса",
                "details": {"current": "created", "target": "ready"},
                "request_id": "upstream-request-id",
            }
        },
    )

    error = _parse_error_response(response)

    assert error.status_code == 409
    assert error.message == "Недопустимый переход статуса"
    assert error.details == {"current": "created", "target": "ready"}


def test_kitchen_client_handles_non_json_upstream_error() -> None:
    response = httpx.Response(502, text="Bad Gateway")

    error = _parse_error_response(response)

    assert error.status_code == 502
    assert error.message == "Bad Gateway"
    assert error.details is None

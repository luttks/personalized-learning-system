from app.main import app


def test_auth_routes_are_registered() -> None:
    paths = app.openapi()["paths"]

    assert "post" in paths["/api/v1/auth/register"]
    assert "post" in paths["/api/v1/auth/login"]
    assert "get" in paths["/api/v1/auth/me"]


def test_auth_me_uses_http_bearer_authentication() -> None:
    schema = app.openapi()

    assert schema["components"]["securitySchemes"] == {
        "HTTPBearer": {
            "type": "http",
            "description": (
                "Nhập access_token nhận được từ "
                "POST /api/v1/auth/login."
            ),
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    assert schema["paths"]["/api/v1/auth/me"]["get"][
        "security"
    ] == [{"HTTPBearer": []}]

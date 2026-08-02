from app.main import app


def test_adaptive_learning_routes_are_registered() -> None:
    paths = app.openapi()["paths"]

    assert "get" in paths["/api/v1/learners/me"]
    assert "patch" in paths["/api/v1/learners/me"]
    assert "post" in paths["/api/v1/learners/me/understand-input"]
    assert "get" in paths["/api/v1/learners/me/mastery"]
    assert "post" in paths["/api/v1/learners/me/learning-events"]
    assert "post" in paths["/api/v1/learners/me/roadmaps"]

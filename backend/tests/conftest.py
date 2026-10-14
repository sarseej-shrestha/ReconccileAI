import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/test.db", llm_api_key=""))
    with TestClient(app) as client:
        yield client


@pytest.fixture
def loaded(client):
    response = client.post("/api/demo/load")
    assert response.status_code == 200, response.text
    return client

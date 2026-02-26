import pytest
from fastapi.testclient import TestClient


class TestExampleItemEndpoints:
    BASE = "/api/v1/items"

    def test_list_items_empty(self, client: TestClient) -> None:
        response = client.get(self.BASE)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_item(self, client: TestClient) -> None:
        payload = {"name": "Test Item", "description": "A test item"}
        response = client.post(self.BASE, json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == payload["name"]
        assert data["description"] == payload["description"]
        assert "id" in data

    def test_get_item_by_id(self, client: TestClient) -> None:
        created = client.post(self.BASE, json={"name": "Fetch Me"}).json()
        response = client.get(f"{self.BASE}/{created['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    def test_get_item_not_found(self, client: TestClient) -> None:
        response = client.get(f"{self.BASE}/99999")
        assert response.status_code == 404

    def test_update_item(self, client: TestClient) -> None:
        created = client.post(self.BASE, json={"name": "Old Name"}).json()
        response = client.patch(f"{self.BASE}/{created['id']}", json={"name": "New Name"})
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

    def test_delete_item(self, client: TestClient) -> None:
        created = client.post(self.BASE, json={"name": "Delete Me"}).json()
        response = client.delete(f"{self.BASE}/{created['id']}")
        assert response.status_code == 204
        # Confirm it's gone
        assert client.get(f"{self.BASE}/{created['id']}").status_code == 404

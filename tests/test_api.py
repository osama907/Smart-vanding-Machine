import pytest
from fastapi.testclient import TestClient

from vending_machine.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VENDING_DATABASE_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as test_client:
        yield test_client


def test_seeded_sports_nutrition_catalog(client):
    response = client.get("/api/v1/supplements")
    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert "Whey Protein" in names
    assert "Electrolyte Drink Mix" in names


def test_recommendations_retrieve_activity_and_goal_matches(client):
    response = client.post(
        "/api/v1/recommendations/text",
        json={
            "message": "I do strength training at the gym and want to build muscle",
            "dietary_preference": "vegan",
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["input_mode"] == "text"
    assert "gym" in result["activity"]
    assert "muscle_gain" in result["goal"]
    assert result["recommendations"][0]["name"] == "Plant Protein Blend"
    assert "not medical" in result["safety_notice"]


def test_recommendations_filter_allergens_and_out_of_stock(client):
    supplements = client.get("/api/v1/supplements").json()
    whey = next(item for item in supplements if item["name"] == "Whey Protein")
    response = client.post(
        "/api/v1/recommendations/text",
        json={
            "message": "gym muscle gain",
            "allergies": ["milk"],
        },
    )
    assert response.status_code == 200
    assert all(item["id"] != whey["id"] for item in response.json()["recommendations"])


def test_purchase_is_atomic_and_creates_history(client):
    whey = next(
        item for item in client.get("/api/v1/supplements").json()
        if item["name"] == "Whey Protein"
    )
    response = client.post(
        "/api/v1/purchases",
        json={"product_id": whey["id"], "quantity": 2},
    )
    assert response.status_code == 201
    assert response.json()["total"] == 59.98
    assert response.json()["remaining_stock"] == whey["stock"] - 2
    assert client.get("/api/v1/purchases").json()[0]["quantity"] == 2

    unavailable = client.post(
        "/api/v1/purchases",
        json={"product_id": whey["id"], "quantity": 13},
    )
    assert unavailable.status_code == 409


def test_voice_endpoint_validates_audio_before_optional_transcriber(client):
    response = client.post(
        "/api/v1/recommendations/voice",
        files={"audio": ("noise.wav", b"not a wav file", "audio/wav")},
    )
    assert response.status_code == 415


def test_image_endpoint_validates_upload_before_optional_model(client):
    response = client.post(
        "/api/v1/recommendations/image",
        files={"image": ("not-an-image.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 415

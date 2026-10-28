from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from backend.main import app
from tools.media import get_media_record, send_image


def test_send_image_returns_small_descriptor_and_http_bytes(tmp_path: Path):
    source = tmp_path / "demo.png"
    Image.new("RGB", (3, 2), (20, 40, 60)).save(source)

    descriptor = send_image(str(source), "测试图")
    assert descriptor["kind"] == "aios.image"
    assert descriptor["url"].startswith("/api/v1/media/")
    assert "base64" not in str(descriptor).lower()
    assert len(str(descriptor)) < 1000
    assert get_media_record(descriptor["media_id"])

    with TestClient(app) as client:
        response = client.get(descriptor["url"])
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_send_image_rejects_non_image(tmp_path: Path):
    source = tmp_path / "not-image.txt"
    source.write_text("hello", encoding="utf-8")
    try:
        send_image(str(source))
    except ValueError as exc:
        assert "不支持" in str(exc)
    else:
        raise AssertionError("non-image file was accepted")

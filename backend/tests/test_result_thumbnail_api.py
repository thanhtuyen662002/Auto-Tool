from pathlib import Path

from fastapi.testclient import TestClient

import app.api as api_module
from app import database
from app.api import create_app


def test_result_thumbnail_endpoint_generates_thumbnail_for_known_output_video(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "autotool.db")
    monkeypatch.setenv("AUTO_TOOL_DATA_DIR", str(tmp_path / "app-data"))
    database.init_db()
    database.create_project("project-1", {"project_name": "Thumbnail Test"})
    database.create_job("job-1", "project-1", preview_only=False, total_outputs=1)

    output_video = tmp_path / "outputs" / "video_001.mp4"
    output_video.parent.mkdir(parents=True)
    output_video.write_bytes(b"fake mp4")
    database.update_job(
        "job-1",
        results_json='{"outputs":[{"index":1,"path":"' + str(output_video).replace("\\", "\\\\") + '","status":"success"}]}',
    )

    class FakeThumbnailService:
        def generate_thumbnail(self, video_path, output_folder, at_second=1.0, media_id=None):
            target = Path(output_folder) / f"{media_id}.jpg"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"jpg")
            return str(target)

    monkeypatch.setattr(api_module, "SourceMediaThumbnailService", FakeThumbnailService)

    client = TestClient(create_app())
    response = client.get("/api/files/thumbnail", params={"path": str(output_video)})

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == b"jpg"

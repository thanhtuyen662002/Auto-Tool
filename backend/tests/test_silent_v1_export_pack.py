from types import SimpleNamespace

from app.tools import silent_mode_v1_rc_test
from backend.tests.silent_v1_rc_test_support import install_fake_flow, make_args, make_config


def test_rc_export_pack_creates_manifest(tmp_path, monkeypatch):
    config, source, output = make_config(tmp_path, ["clip.mp4"])
    install_fake_flow(monkeypatch, silent_mode_v1_rc_test, [source / "clip.mp4"])

    class FakeExportPackService:
        def create_export_pack_for_job(self, _job_id, _platform, output_dir=None):
            target = output / "export_pack"
            target.mkdir(parents=True, exist_ok=True)
            (target / "export_manifest.json").write_text('{"status":"success"}', encoding="utf-8")
            return SimpleNamespace(output_dir=str(target))

    monkeypatch.setattr(silent_mode_v1_rc_test, "ExportPackService", FakeExportPackService)
    result = silent_mode_v1_rc_test.run_rc_test(
        make_args(config, auto_render=True, export_pack=True, review_mode=False)
    )

    assert result["export_pack_created"] is True
    assert (output / "export_pack" / "export_manifest.json").exists()


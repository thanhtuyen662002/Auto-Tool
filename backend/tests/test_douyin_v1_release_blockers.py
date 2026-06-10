from __future__ import annotations

from pathlib import Path


def test_v1_release_blocker_document_exists_and_lists_critical_rules() -> None:
    content = Path("docs/DOUYIN_REUP_V1_RELEASE_BLOCKERS.md").read_text(encoding="utf-8")

    assert "App crash toàn batch" in content
    assert "Render không tạo được output" in content
    assert "Export Pack thiếu video final" in content
    assert "Không block release" in content

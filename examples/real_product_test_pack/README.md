# Real Product Test Pack

This pack is for the Auto Tool v0.2 release-candidate QA pass. It keeps real
videos out of git, but gives stable configs and product inputs for repeatable
local testing.

## Folders

Put source videos in:

```txt
examples/sample_videos/real_product_test_pack/projector_kaw_xmax10/
examples/sample_videos/real_product_test_pack/handheld_fan_jisulife/
examples/sample_videos/real_product_test_pack/sunscreen_jacket_guno/
examples/sample_videos/real_product_test_pack/home_gadget_generic/
```

Use only videos you have the right to edit or remix. The tool does not download
videos, remove watermarks, bypass copyright, or post to any platform.

## Smoke Test

From `backend/`:

```bash
python -m app.tools.v02_smoke_test --config ../examples/real_product_test_pack/configs/projector_kaw_xmax10.json --preview-only --skip-tts-online
```

If the source folder is empty, the smoke test creates temporary synthetic video
inputs and returns `success_with_warnings`. When real videos are present, it uses
those videos.

For full batch:

```bash
python -m app.tools.v02_smoke_test --config ../examples/real_product_test_pack/configs/projector_kaw_xmax10.json --full
```

## Product Cases

| Case | Expected industry | Expected visual style |
| --- | --- | --- |
| `projector_kaw_xmax10` | `tech_electronics` | `tech_dark_neon` |
| `handheld_fan_jisulife` | `home_lifestyle` or `general_product` | `clean_review_light` or `cute_pastel_shop` |
| `sunscreen_jacket_guno` | `fashion_accessories` | `fashion_minimal` |
| `home_gadget_generic` | `home_lifestyle` | `clean_review_light` |

## QA Flow

1. Import product info from `product_inputs/`.
2. Confirm industry preset, timeline template, visual style, and TTS voice.
3. Scan source videos.
4. Review source media and segments.
5. Render preview.
6. Edit script if needed.
7. Render full batch.
8. Review quality and rerender bad outputs.
9. Build captions and export content plan.

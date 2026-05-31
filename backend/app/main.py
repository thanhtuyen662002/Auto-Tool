from __future__ import annotations

import argparse

from app.config import load_project_config
from app.api import create_app
from app.modules.render_worker.render_worker import render_project
from app.utils.logger import configure_logging, get_logger


logger = get_logger(__name__)
app = create_app()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auto Tool backend MVP renderer")
    parser.add_argument("--config", required=True, help="Path to project config JSON")
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()

    try:
        config = load_project_config(args.config)
    except Exception as exc:
        logger.error("Failed to load config: %s", exc)
        return 1

    try:
        summary = render_project(
            config,
            progress_callback=lambda payload: logger.info(
                "%s | progress=%s%%",
                payload.get("current_step"),
                payload.get("progress"),
            ),
            log_callback=lambda level, message: getattr(logger, level, logger.info)(message),
        )
    except Exception as exc:
        logger.exception("Project failed")
        return 1

    return 0 if summary["failed_outputs"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

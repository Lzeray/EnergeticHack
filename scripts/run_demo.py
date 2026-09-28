"""End-to-end CLI demo: seeds fixtures if needed, builds a digest for every
demo profile without starting the web server, and prints where the Markdown
landed. This is the fastest way to show "publications in -> digest out".

Usage: python -m scripts.run_demo [--period daily|monthly]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app import models
from app.config import settings
from app.db import SessionLocal, init_db
from app.digest.builder import build_digest
from app.llm.factory import build_provider
from scripts.seed_fixtures import seed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", choices=["daily", "monthly"], default="daily")
    args = parser.parse_args()

    init_db()
    seed()

    provider = build_provider(
        settings.llm_provider,
        settings.llm_model,
        ollama_base_url=settings.ollama_base_url,
        openai_base_url=settings.openai_base_url,
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
        anthropic_model=settings.anthropic_model,
        timeout=settings.llm_timeout_seconds,
    )
    print(f"LLM provider: {provider.name} (falls back to extractive summaries if unreachable)\n")

    with SessionLocal() as session:
        profiles = list(session.execute(select(models.Profile)).scalars())
        for profile in profiles:
            digest_run = build_digest(session, profile, args.period, provider)
            print(f"[{profile.name}] -> {digest_run.markdown_path}")
            print(f"  stats: {digest_run.stats}")

    print("\nГотово. Markdown-файлы лежат в data/digests/.")


if __name__ == "__main__":
    main()

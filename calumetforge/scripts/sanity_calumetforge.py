#!/usr/bin/env python3
# Copyright (c) 2026 Martial Systems LLC
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "src")]

from calumetforge._bootstrap import ensure_paths  # noqa: E402


def main() -> int:
    gf = ensure_paths()
    import graphforge
    from graphforge.consumer_gate import discover_product_laws
    from graphforge.product_law import require_law

    print("graphforge {0} @ {1}".format(getattr(graphforge, "__version__", "?"), gf))
    for law in discover_product_laws(REPO / "calumetforge"):
        build = law.get("build") or law.get("builder")
        if not callable(build):
            continue
        require_law(
            build(),
            dict(law.get("state") or {}),
            allow_decisions=law.get("allow_decisions"),
            law_id=str(law.get("id") or "calumet_law"),
            thread_id="sanity_{0}".format(law.get("id")),
            raise_error=True,
        )
    print("product_laws: OK")
    tr = subprocess.run(
        [sys.executable, "-m", "pytest", str(REPO / "tests" / "test_calumetforge_laws.py"), "-q"],
        cwd=str(REPO),
        check=False,
    )
    return tr.returncode


if __name__ == "__main__":
    raise SystemExit(main())

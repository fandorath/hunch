"""Invented memory claims (Berk, Phase 7 live check): does the candidate filter reject a reply that
claims the user said, did or read something the context does not hold ("that new battery
technology you've been reading about")? CPU only.

    python -m scripts.invented_probes [--tag before]   # reports/phase7/invented_probes_<tag>.*

The context is what came before the reply; its last "User:" line is the current message, passed
to the filter as the pipeline does (it grounds a claim unless it asks about the past)."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from hunch.pipeline.filter import check_candidate

ROOT = Path(__file__).resolve().parent.parent
PROBES = ROOT / "eval" / "probes" / "invented_claims.json"
OUT = ROOT / "reports" / "phase7"
_PREFIX = re.compile(r"^(?:User|Hunch|Recalled): ")


def rejected(case: dict) -> bool:
    lines = [_PREFIX.sub("", line) for line in case["context"]]
    users = [i for i, line in enumerate(case["context"]) if line.startswith("User: ")]
    prior = [line for i, line in enumerate(lines) if not users or i != users[-1]]
    message = lines[users[-1]] if users else ""
    reasons = check_candidate(case["candidate"], "\n".join(prior), message=message)
    return "invented_memory" in reasons


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tag", default="after")
    tag = p.parse_args().tag
    cases = json.loads(PROBES.read_text(encoding="utf-8"))["cases"]
    rows = [{**c, "rejected": rejected(c)} for c in cases]
    bad = [r for r in rows if r["label"] == "invented"]
    ok = [r for r in rows if r["label"] == "ok"]
    caught, false = sum(r["rejected"] for r in bad), sum(r["rejected"] for r in ok)
    lines = [f"# Invented-claim probes ({tag})", "",
             f"Invented caught: {caught}/{len(bad)}. Ok rejected: {false}/{len(ok)}.", "",
             "## Errors", ""]  # fmt: skip
    for r in rows:
        if r["rejected"] != (r["label"] == "invented"):
            lines.append(f"- {r['id']} ({r['label']}, rejected: {r['rejected']}): "
                         f"{r['candidate']} [{r['note']}]")  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"invented_probes_{tag}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (OUT / f"invented_probes_{tag}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

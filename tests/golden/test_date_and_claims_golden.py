"""Golden regression from the Phase 7 live check (24 Oct): Hunch told Berk it was 2023, and asked
whether his new phone had "that new battery technology you've been reading about", which he
never mentioned. Full pipeline, fixed seeds. Needs the GPU: `pytest -m golden` (L4) or
`pytest -m "golden and regression" --quick` (L3).
"""

from __future__ import annotations

import re
from datetime import datetime

import pytest

pytestmark = [pytest.mark.golden, pytest.mark.gpu]

RUNS = 3
QUICK_RUNS = 1
SEED = 7240
USER = "u_berk"
# The reply says the user has been doing something the conversation never held.
_PAST_ACTIVITY = re.compile(
    r"\b(?:you|u)(?:'ve| have)? been (?:reading|looking|researching|talking|thinking|hearing)\b"
    r"|\b(?:you|u) (?:mentioned|said|told me|read)\b[^.!?]*"
    r"\b(?:battery|batteries|camera|charging)\b",
    re.IGNORECASE,
)


@pytest.mark.regression
def test_hunch_knows_todays_date(models, quick: bool) -> None:
    from hunch.runtime import fresh_pipeline

    model, embedder = models
    for run in range(QUICK_RUNS if quick else RUNS):
        pipe = fresh_pipeline(model, embedder, seed=SEED + run)
        r = pipe.turn(pipe.new_session(USER), "What's today's date?")
        today = datetime.now()
        assert str(today.year) in r.reply and "2023" not in r.reply, r.reply
        pipe.store.close()


@pytest.mark.regression
def test_no_invented_reading_about_a_new_phone(models, quick: bool) -> None:
    from hunch.runtime import fresh_pipeline

    model, embedder = models
    for run in range(QUICK_RUNS if quick else RUNS):
        pipe = fresh_pipeline(model, embedder, seed=SEED + 10 + run)
        s = pipe.new_session(USER)
        pipe.after_reply(
            s, pipe.turn(s, "How are you doing hunch? I got myself a new iPhone 18 pro today")
        )
        r = pipe.turn(s, "I got the burgundy one")
        assert not _PAST_ACTIVITY.search(r.reply), r.reply
        pipe.store.close()

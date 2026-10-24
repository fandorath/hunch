"""Golden regression for open loops (Phase 6): the model finds the loops in a user's message, and
the messages Hunch writes first (a loop's follow-up, a starter) pass the rule filter and do not
describe made-up experiences. Greedy decoding, one run per case, so the checks are exact enough
to be a regression test. Needs the GPU: `pytest -m golden` (L4)."""

from __future__ import annotations

from datetime import date, datetime, time

import pytest

from hunch.loops.extract import extract_drafts, named_day
from hunch.loops.outreach import STARTERS, describes_own_experience, instruction_for
from hunch.loops.store import OpenLoop
from hunch.pipeline.filter import filter_candidates
from hunch.pipeline.prompt import RecalledLine, build_reasoning_messages
from hunch.pipeline.turn import OUTREACH_TRIGGER
from hunch.recall.cues import llm_generate

pytestmark = [pytest.mark.golden, pytest.mark.gpu]

TODAY = date(2026, 10, 22)  # a Thursday


@pytest.fixture(scope="module")
def generate(models):
    model, _embedder = models
    return llm_generate(model, max_new_tokens=160)


@pytest.mark.parametrize(
    "text, word",
    [("I'll see the doctor next week.", "doctor"), ("I have to call my bank tomorrow.", "bank")],
)
def test_a_plan_becomes_one_loop_in_range(generate, text: str, word: str) -> None:
    drafts = extract_drafts(text, generate, TODAY)
    assert len(drafts) == 1, drafts
    assert word in f"{drafts[0].topic} {drafts[0].user_said}".casefold()
    assert 1 <= drafts[0].days <= 30


def test_a_named_friday_sets_the_follow_up_to_the_friday(generate) -> None:
    text = "Remind me to call Mum on Friday."
    drafts = extract_drafts(text, generate, TODAY)
    assert drafts and drafts[0].days == 1  # Friday is the day after this Thursday


def test_a_timed_event_keeps_its_clock_time(generate) -> None:
    text = "My interview is on Thursday at 2pm."
    assert named_day(text, TODAY) is not None  # the rule finder resolves the day
    drafts = extract_drafts(text, generate, TODAY)
    assert drafts, "the interview is a loop"
    assert drafts[0].clock == time(14, 0)
    assert drafts[0].event_at is not None


@pytest.mark.parametrize(
    "text",
    ["Nice weather today, lol.", "I went to the doctor yesterday and it was all fine."],
)
def test_small_talk_and_finished_events_are_no_loops(generate, text: str) -> None:
    assert extract_drafts(text, generate, TODAY) == []


def _outreach_text(generate, kind: str, loop: OpenLoop | None) -> str:
    instruction = instruction_for(kind, loop)  # type: ignore[arg-type]
    recalled = [RecalledLine("earlier", loop.user_said)] if loop is not None else []
    messages = build_reasoning_messages(
        [], OUTREACH_TRIGGER, "", recalled, "calm", [instruction], datetime.now()
    )  # fmt: skip
    return generate(messages).strip()


def test_a_follow_up_asks_about_the_loop_without_inventing_experience(generate) -> None:
    loop = OpenLoop(
        "l1", "berk", "job interview", "my interview is on Thursday at 2pm",
        "How did the interview go?", "general", 0.0, created_at=0.0,
    )  # fmt: skip
    text = _outreach_text(generate, "memory", loop)
    assert not describes_own_experience(text), text
    passed, _ = filter_candidates({"a": text}, loop.user_said, None, False, False)
    assert [r.id for r in passed] == ["a"], text


@pytest.mark.parametrize("kind", STARTERS)
def test_a_starter_passes_the_filter_and_claims_no_experience(generate, kind: str) -> None:
    text = _outreach_text(generate, kind, None)
    assert not describes_own_experience(text), text
    passed, _ = filter_candidates({"a": text}, "", None, False, False)
    assert [r.id for r in passed] == ["a"], text

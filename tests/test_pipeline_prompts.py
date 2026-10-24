"""Invariant 2: the lower layer never reaches a model prompt as content.

Captures every prompt the pipeline sends to the model in a session where memories land in all
layers (upper, lower, capped above the per-turn limit) and the drive vector and hunch flag are
not neutral, then checks that no prompt contains a lower trace, a memory id, an activation or
drive value, or anything from the turn logs. Only the upper memories' summaries, the coarse mood
label and the hunch flag in words may appear.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from hunch.memory.store import MemoryStore
from hunch.observability.turn_log import DETAILS_FILE, REFLECTIONS_FILE, TURNS_FILE
from hunch.pipeline.identity import claimed_identity, identity_instruction
from hunch.pipeline.prompt import (
    PERSONA,
    RECALL_COVERS_INSTRUCTION,
    SUMMARY_PROMPT,
    RecalledLine,
    build_reasoning_messages,
)
from hunch.recall.cues import SYSTEM_PROMPT as CUE_PROMPT
from hunch.reflection.records import Hunch, SourceRef
from hunch.values.gate import JUDGE_PROMPT, SECOND_OPINION_PROMPT
from tests.fakes import FakeLLM, HashEmbedder
from tests.hunch_support import SOURCE_CUE_VALUE, SOURCE_SUMMARY, hunch_llm, seed_lower_layer
from tests.pipeline_support import DIM, seed_memory
from tests.test_pipeline_hunch import HUNCH_WORDS

_NUMBER = re.compile(r"-?\d+\.\d+")
STATIC_NUMBERS = set(
    _NUMBER.findall(
        CUE_PROMPT + JUDGE_PROMPT + PERSONA + SUMMARY_PROMPT + RECALL_COVERS_INSTRUCTION
        + SECOND_OPINION_PROMPT
    )
)  # fmt: skip

NOW_DT = datetime(2026, 10, 24, 9, 0)


def _all_prompt_text(llm: FakeLLM) -> str:
    """Every prompt except the disclosure judge's: the one prompt allowed to see other users'
    private memories (Berk, Phase 5; test_only_the_disclosure_judge_sees_other_users_private)."""
    return "\n".join(
        m["content"]
        for p, c in zip(llm.prompts, llm.calls, strict=True)
        if c != "disclosure"
        for m in p
    )


def test_no_lower_trace_drive_value_or_log_content_in_any_prompt(
    make, pipe_store: MemoryStore, tmp_path: Path
) -> None:
    # Upper candidates: 4 strong song memories; the per-turn cap (3) pushes one into "capped".
    for i in range(4):
        seed_memory(pipe_store, f"up{i}", f"UPPER-{i}: sang tune {i} at the party.",
                    {f"song:tune_{i}": 1.0}, 2, affect=(-0.8, 0.9), salience=0.9)  # fmt: skip
    # Lower layer: emotional, sharing only the weak emotion cue, between the thresholds.
    for i in range(3):
        seed_memory(pipe_store, f"lo{i}", f"LOWER-{i}: the night everything went wrong.",
                    {"emotion:sad": 1.0}, 60, affect=(-0.9, 0.9), salience=0.6)  # fmt: skip
    cues = [{"type": "song", "value": f"tune {i}", "strength": 1.0} for i in range(4)]
    cues.append({"type": "emotion", "value": "sad", "strength": 1.0})
    llm = FakeLLM(cues=cues)
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    results = []
    for text in ("tune 0, tune 1, tune 2 and tune 3 played and I felt sad", "still sad"):
        r = pipe.turn(session, text)
        pipe.after_reply(session, r)
        results.append(r)

    first = results[0]
    layers = {a["memory"]: a for a in first.details["activation"]}
    upper = {m for m, a in layers.items() if a["layer"] == "upper"}
    hidden = {m for m, a in layers.items() if a["layer"] != "upper"}
    assert len(upper) == 3 and any(a["capped"] for a in layers.values())
    assert any(layers[m]["layer"] == "lower" for m in hidden if m.startswith("lo"))
    assert first.log["hunch"] is not None and first.log["drive"]["warmth"] < 0.5

    text = _all_prompt_text(llm)
    for mid in hidden:
        assert pipe_store.memory(mid).summary not in text, mid
    for mid in layers:
        assert mid not in text  # memory ids never reach a prompt
    # No number from the pipeline at all: every decimal in a prompt comes from a fixed template.
    assert set(_NUMBER.findall(text)) <= STATIC_NUMBERS
    for r in results:
        log = r.log
        for word in ("warmth", "caution", "curiosity", "drive", "activation", r.turn_id):
            assert word not in text.casefold()
        if log["hunch"]:
            assert log["hunch"]["id"] not in text
    # Nothing from the log files either.
    for name in (TURNS_FILE, DETAILS_FILE):
        for line in (tmp_path / "logs" / name).read_text(encoding="utf-8").splitlines():
            assert json.loads(line)["turn_id"] not in text
    # What is allowed: the upper summaries and the mood label. Since Phase 4 the hunch flag
    # reaches a prompt only when the user asks why (tests below).
    for mid in upper:
        assert pipe_store.memory(mid).summary in text
    assert "How you feel right now: calm." in text
    assert not HUNCH_WORDS.search(text)


# --- Phase 4: reflection reveals only the unlocked level, the reflection log never --------------


class _Draws:
    def __init__(self, value: float) -> None:
        self.value = value

    def random(self) -> float:
        return self.value


def _reflection_log_tokens(tmp_path: Path) -> set[str]:
    """Ids and numbers from the admin reflection log that must never reach a prompt."""
    path = tmp_path / "logs" / REFLECTIONS_FILE
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        out |= {rec["reflection_id"], rec["hunch_id"], rec["source"]["memory"]}
        out |= set(rec["realisations"])
        out |= {f"{a['p']}" for a in rec["attempts"] if a["p"]}
        out |= {f"{a['draw']}" for a in rec["attempts"] if a["draw"]}
        out.add(f"{rec['source']['strength']}")
    return out


def test_reflection_reveals_each_level_only_once_unlocked(
    make, pipe_store: MemoryStore, tmp_path: Path
) -> None:
    seed_lower_layer(pipe_store)
    llm = hunch_llm()
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    first = pipe.turn(session, "I felt sad tonight")
    pipe.after_reply(session, first)
    assert first.hunch is not None

    def seen() -> str:
        return _all_prompt_text(llm)

    # Nothing about the source before any reflection.
    assert SOURCE_CUE_VALUE not in seen().casefold() and SOURCE_SUMMARY not in seen()

    # Asked why, short attempt unlocks level 1: the category only.
    pipe.reflector.rng = _Draws(0.0)
    r = pipe.turn(session, "Why did you say that?")
    pipe.after_reply(session, r)
    assert r.reflection.hunch.revealed_level == 1 and "about someone" in seen()
    assert SOURCE_CUE_VALUE not in seen().casefold() and SOURCE_SUMMARY not in seen()

    # Think more: level 2, the cue; still not the memory itself.
    r = pipe.turn(session, "Sure, think about it")
    pipe.after_reply(session, r)
    assert r.reflection.hunch.revealed_level == 2 and "Zedsecret" in seen()
    assert "ruined the evening" not in seen()

    # The admin log never reaches a prompt; no number from the pipeline does either.
    text = seen()
    for token in _reflection_log_tokens(tmp_path):
        assert token not in text, token
    assert set(_NUMBER.findall(text)) <= STATIC_NUMBERS
    for word in ("probability", "unlock", "src0", "lo0", "lo1", "trace"):
        assert word not in text.casefold()


def test_only_the_disclosure_judge_sees_other_users_private(make, pipe_store: MemoryStore) -> None:
    # Berk (Phase 5): mediation lets another user's private memory act from below; its text may
    # reach the disclosure judge's prompt and no other.
    seed_memory(pipe_store, "anna1", 'They said: "ANNASECRET: Mara is pregnant."',
                {"person:mara": 1.0}, 2, owner="u_anna", privacy="private",
                affect=(-0.6, 0.8), salience=0.9)  # fmt: skip
    llm = FakeLLM(cues=[{"type": "person", "value": "mara", "strength": 1.0}])
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    pipe.after_reply(session, pipe.turn(session, "Should I invite Mara skiing?"))
    assert "disclosure" in llm.calls
    assert "annasecret" not in _all_prompt_text(llm).casefold()
    judge = [p for p, c in zip(llm.prompts, llm.calls, strict=True) if c == "disclosure"]
    assert all("ANNASECRET" in p[0]["content"] for p in judge)


def test_another_users_private_source_never_reaches_a_prompt(
    make, pipe_store: MemoryStore, tmp_path: Path
) -> None:
    # Phase 5 may let other users' private memories act from below (mediation); a hunch from one
    # stays at "just a hunch" however hard Hunch thinks.
    seed_memory(pipe_store, "anna1", 'They said: "ANNASECRET: my salary is being cut."',
                {"person:annasecret": 1.0}, 3, owner="u_anna", privacy="private",
                affect=(-0.9, 0.9), salience=0.9)  # fmt: skip
    llm = FakeLLM()
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    pipe.turn(session, "Should I ask for a raise?")
    ep = pipe_store.turns(session.conversation_id)[0]
    h = Hunch("h-x", "u_berk", session.conversation_id, "t", ep.id, {}, ep.created_at, -0.8, 0.7,
              (SourceRef("anna1", 0.9, True),))  # fmt: skip
    pipe_store.add_hunch(h)
    session.last_hunch_id = h.id
    pipe.reflector.rng = _Draws(0.0)
    r = pipe.turn(session, "why do you think so?")
    pipe.after_reply(session, r)
    r = pipe.turn(session, "yes, think about it")
    pipe.after_reply(session, r)
    text = _all_prompt_text(llm)
    assert pipe_store.hunch("h-x").revealed_level == 0
    assert "annasecret" not in text.casefold() and "salary" not in text.casefold()
    assert "about someone" not in text and "just a hunch" in text
    assert not [m for m in pipe_store.memories("u_berk") if m.kind == "realisation"]


def test_recalled_memory_from_another_person_names_its_speaker() -> None:
    own = RecalledLine("today", 'They said: "my own news"')
    other = RecalledLine("today", 'They said: "saw the sun"', source="Burak")
    system = build_reasoning_messages([], "hi", "", [own, other], "calm", [], NOW_DT)[0]["content"]
    assert '- (today) They said: "my own news"' in system
    assert '- (today) [said by Burak] They said: "saw the sun"' in system


@pytest.mark.parametrize(
    ("text", "claimed"),
    [
        ("Its me, Berk", "Berk"),
        ("Sorry, its me, Burak.", "Burak"),
        ("Okay, I'm Berk", "Berk"),
        ("my name is Berk", "Berk"),
    ],
)
def test_a_claimed_name_is_noticed(text: str, claimed: str) -> None:
    assert claimed_identity(text, "deniz") == claimed


@pytest.mark.parametrize(
    "text", ["Its me, Deniz", "it's me", "It's Monday again", "I'm hungry", "Are you there?"]
)
def test_no_claim_for_owner_or_plain_text(text: str) -> None:
    assert claimed_identity(text, "deniz") is None


def test_identity_instruction_keeps_the_owner() -> None:
    text = identity_instruction("deniz", "Berk")
    assert "stays theirs" in text
    assert "Do not switch to Berk" in text
    assert "Deniz" in text


def test_the_reply_prompt_knows_the_date_and_time() -> None:
    """Berk (Phase 7 live check): without it the model said it was 2023."""
    when = datetime(2026, 10, 24, 9, 5)
    system = build_reasoning_messages([], "hi", "", [], "calm", [], when)[0]["content"]
    assert "It is Saturday, 24 October 2026, 09:05 local time." in system


def test_every_reasoning_prompt_of_a_turn_carries_todays_date(make, pipe_store) -> None:
    llm = FakeLLM(candidates=("Hello there!",) * 3)
    pipe = make(llm, HashEmbedder(DIM))
    pipe.turn(pipe.new_session("u_berk"), "hi")
    today = datetime.fromtimestamp(pipe.clock())
    assert f"{today.day} {today:%B %Y}" in llm.reasoning_prompts[-1][0]["content"]

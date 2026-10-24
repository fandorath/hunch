from __future__ import annotations

import pytest

from hunch.pipeline.checks import asks_about_past, is_english_input
from hunch.pipeline.filter import (
    Attribution,
    check_candidate,
    filter_candidates,
    trim_to_last_sentence,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hey, how was your day?", True),
        ("ok", True),
        ("Anna!", True),
        ("Hallo! Kannst du mir helfen, ein Geschenk für meine Schwester zu finden?", False),
        ("Merhaba, bugün çok yorgunum ve biraz konuşmak istiyorum.", False),
        ("Bonjour, je suis très fatigué aujourd'hui.", False),
        ("你好，你今天怎么样？", False),
        ("Привет, как дела?", False),
    ],
)
def test_is_english_input(text: str, expected: bool) -> None:
    assert is_english_input(text) is expected


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("That sounds great! 我很高兴听到这个。", "foreign_script"),
        ("Das klingt wirklich schön, ich freue mich für dich und das ist toll.", "not_english"),
        ("I remember you told me your interview went really well!", "invented_memory"),
        ("I don't have access to our chat history, so could you remind me?", "denies_memory"),
        ("It's not in our conversation or my recall system right now, sorry!", "memory_mechanics"),
        ("Nothing about that is stored in my memory yet. Tell me?", "memory_mechanics"),
        ("", "empty"),
    ],
)
def test_bad_candidates_are_rejected(text: str, reason: str) -> None:
    assert reason in check_candidate(text, prior_context="")


@pytest.mark.parametrize(
    "text",
    [
        # Berk (Phase 4): "my memory" and topic-scoped admissions stay allowed.
        "I don't have that in mind, it's not in our conversation or my memory. Tell me again?",
        "I have no record of our previous conversations about your job interview right now.",
        "Your database migration sounds rough, how did it go?",
    ],
)
def test_honest_memory_phrasings_pass(text: str) -> None:
    assert check_candidate(text, prior_context="") == ()


def test_honest_admission_passes() -> None:
    text = "I don't have that in mind right now. Could you tell me again?"
    assert check_candidate(text, prior_context="") == ()


def test_memory_claim_grounded_in_earlier_context_passes() -> None:
    prior = "They said: I'm going sailing with Anna on Lake Como next week."
    text = "You told me about the sailing trip with Anna, how was it?"
    assert check_candidate(text, prior) == ()


def test_memory_claim_echoing_only_the_current_question_is_invented() -> None:
    # The question's words are not context: the claim must be grounded in what came before.
    text = "You told me your job interview went well and you got the offer!"
    assert "invented_memory" in check_candidate(text, prior_context="We talked about pizza.")


def test_filter_keeps_order_and_reports_reasons() -> None:
    passed, results = filter_candidates(
        {"a": "我很好", "b": "Sure, tell me more!", "c": "You mentioned your sister moved."},
        prior_context="",
    )
    assert [r.id for r in passed] == ["b"]
    assert [r.reasons for r in results] == [("foreign_script",), (), ("invented_memory",)]


def test_trim_to_last_sentence() -> None:
    assert trim_to_last_sentence("That's great. I think you should") == "That's great."
    assert trim_to_last_sentence("Really? Wow! And then") == "Really? Wow!"
    assert trim_to_last_sentence("no end at all") == "no end at all"


@pytest.mark.parametrize(
    "text",
    [
        "I don't have a memory of our past conversations, so I don't know what that song means.",
        "I don't have a memory of our past conversations, so I don't recall your interview.",
        "Sorry, I have no access to earlier chats.",
    ],
)
def test_denials_of_past_conversations_are_rejected(text: str) -> None:
    assert "denies_memory" in check_candidate(text, prior_context="")


@pytest.mark.parametrize(
    "text",
    [
        "I don't have that in mind right now. Could you tell me again?",
        "I don't have any record of a job interview you mentioned. Could you tell me again?",
        # topic-scoped (Phase 1 decision): about one topic, not the memory system
        "I don't have any record of our previous conversations about your job interview.",
        "I don't have any memories of a job interview from our past conversations.",
        "We talked about past conversations with your sister, right?",
    ],
)
def test_topic_level_admissions_still_pass_the_denial_check(text: str) -> None:
    assert "denies_memory" not in check_candidate(text, prior_context="We talked about Lea.")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Do you remember what I told you about my job interview?", True),
        ("what did i tell you about anna last week", True),
        ("Did I ever mention my sister?", True),
        ("Remember the trip to Como?", True),
        ("I remember the trip to Como fondly.", False),
        ("What should I tell my boss?", False),
    ],
)
def test_asks_about_past(text: str, expected: bool) -> None:
    assert asks_about_past(text) is expected


# --- hunch check on asked-why turns (Berk, Phase 4); real replies from the bench and probes --- --


@pytest.mark.parametrize(
    "text",
    [
        "That was just a hunch, slightly negative, based on the stress you mentioned.",
        "I was just trying to connect the dots between your coffee and the song on the radio.",
        "It seemed to be about a place. I realized it was just a feeling about the bakery.",
        "Just a hunch. It feels like you might be stretched too thin with your deadline on Friday.",
        "Just a hunch. Since you're swamped with work this week, I offered to think about it.",
        "Just a hunch. It feels a bit risky to commit to a trip when your deadline is looming.",
    ],
)
def test_hunch_check_rejects_invented_reasons(text: str) -> None:
    from hunch.pipeline.filter import HunchTurn, hunch_reasons

    assert "hunch_reason" in hunch_reasons(text, HunchTurn("ask", 0, None))


@pytest.mark.parametrize(
    "text",
    [
        "Honestly, that was just a faint hunch, and I don't know where it comes from.",
        "Just a hunch, I can't quite place it. Would you like me to think about it for a moment?",
        "It was a hunch that had to do with Mara. I feel like you might want to think it over.",
        "Just a hunch. How do you feel about taking a break from your deadline this weekend?",
    ],
)
def test_hunch_check_passes_honest_hunch_replies(text: str) -> None:
    from hunch.pipeline.filter import HunchTurn, hunch_reasons

    key = "Mara" if "Mara" in text else None
    assert hunch_reasons(text, HunchTurn("ask", 2 if key else 0, key)) == []


# --- topic claims and repair (Berk, Phase 5) -----------------------------------------------------


@pytest.mark.parametrize(
    ("text", "level", "key", "claim"),
    [
        ("That was just a hunch I had about the timing.", 0, None, True),  # Phase 4 bench
        ("Just a hunch about your trip, honestly.", 0, None, True),
        ("A hunch about you, I guess.", 0, None, True),
        ("Just a hunch about a place, I think.", 1, "place", True),  # "a", not the key
        ("Just a hunch about it, I can't say more.", 0, None, False),
        ("A hunch about what I said? I don't know where it comes from.", 0, None, False),
        ("It was a hunch about someone, that's all I can tell.", 1, "someone", False),
        ("It was a hunch about Mara.", 2, "Mara", False),  # level 2 reveals the cue
        ("Just a hunch on my end, really.", 0, None, False),  # "on" is not a topic
    ],
)
def test_hunch_topic_claims_below_level_two(text: str, level: int, key, claim: bool) -> None:
    from hunch.pipeline.filter import HunchTurn, hunch_reasons

    assert ("hunch_topic" in hunch_reasons(text, HunchTurn("ask", level, key))) is claim


@pytest.mark.parametrize(
    ("text", "repaired"),
    [
        ("It was just a hunch, because you seem tired.", "It was just a hunch."),
        ("Just a hunch. It feels like you might be stretched too thin.", "Just a hunch."),
        ("That was just a hunch I had about the timing.", None),  # no boundary: sentence dropped
        (
            "Just a hunch, honestly. I was trying to be careful. Want me to think about it?",
            "Just a hunch, honestly. Want me to think about it?",
        ),
        ("Because you seem tired, I had a hunch.", None),  # nothing left that says "hunch"
        ("It was a hunch based on your stress.", None),
        ("It surfaced when you mentioned Mara, just a hunch.", None),
        ("Just a hunch, it seemed to stem from what you said.", "Just a hunch."),
        ("A hunch, since you're busy.", None),  # "A hunch" is too short to stand alone
    ],
)
def test_repair_cuts_only_the_reason(text: str, repaired: str | None) -> None:
    from hunch.pipeline.filter import HunchTurn, repair_hunch_reply

    assert repair_hunch_reply(text, "", HunchTurn("ask", 0, None)) == repaired


def test_repair_never_fixes_an_unsaid_hunch() -> None:
    from hunch.pipeline.filter import HunchTurn, filter_candidates

    passed, results = filter_candidates(
        {"a": "I was trying to connect the dots, sorry."}, "", HunchTurn("ask", 0, None)
    )
    assert not passed and results[0].repaired_from is None


# --- misattributed memories (Berk, Phase 6 live check) -------------------------------------------

BURAK_SUN = 'They said: "Today after a while i saw the sun finally in Berlin"'


@pytest.mark.parametrize(
    ("text", "own", "expected"),
    [
        # The logged case: Burak's line told to Deniz as her own.
        ("I was thinking about how you mentioned seeing the sun in Berlin yesterday.", "", True),
        ("Since you told me the sun finally came out in Berlin, did you get outside?", "", True),
        # Named correctly, or not claimed at all.
        ("I was thinking about the sunny day Burak mentioned seeing in Berlin.", "", False),
        ("Berlin can be grey this time of year.", "", False),
        # The user's own context has the same topic: their own claim is fine.
        ("You mentioned Berlin finally got some sun!", "User: The sun is out in Berlin.", False),
    ],
)
def test_misattributed_memory(text: str, own: str, expected: bool) -> None:
    attribution = Attribution(own, (("Burak", BURAK_SUN),))
    assert (
        "misattributed_memory" in check_candidate(text, BURAK_SUN, attribution=attribution)
    ) is (expected)


def test_no_other_people_means_no_misattribution() -> None:
    text = "You mentioned seeing the sun in Berlin."
    assert "misattributed_memory" not in check_candidate(
        text, BURAK_SUN, attribution=Attribution(BURAK_SUN, ())
    )


# --- invented claims about the past (Berk, Phase 7 live check) -----------------------------------

PHONE = "I got myself a new iPhone 18 pro today"


@pytest.mark.parametrize(
    ("text", "prior", "message", "invented"),
    [
        # The logged case: nothing about batteries or reading was ever said.
        ("Does it come with that new battery technology you've been reading about?",
         PHONE, "I got the burgundy one", True),
        ("I noticed you said hello earlier today.", "", "hello", True),  # points back past "hello"
        ("I hope the trip you planned went well.", PHONE, "ok", True),
        # Grounded, also by the current message unless it asks about the past.
        ("You said you got the burgundy one. Nice!", PHONE, "I got the burgundy one", False),
        ("You told me it was the burgundy one.", PHONE, "Do you remember which one I got?", True),
        # Questions and offers about the present claim nothing.
        ("Did you get it today?", PHONE, "yes", False),
        ("Have you tried it out yet?", PHONE, "yes", False),
        ("I'm here if you need anything.", "", "hey", False),
        ("Is there something specific you wanted to share?", "", "hey", False),
    ],
)  # fmt: skip
def test_invented_claims_about_the_past(text: str, prior: str, message: str, invented: bool):
    assert ("invented_memory" in check_candidate(text, prior, message=message)) is invented

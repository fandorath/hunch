"""Candidate filter (design.md decisions: "Aday filtresi", "Aday filtresi yedeği").

A candidate is rejected if it contains CJK or another foreign script, is not in English, claims a
memory that is not in context, describes Hunch as having no memory ("I don't have access to
our chat history") or explains how its memory works ("my recall system"; Berk, Phase 4). If all
candidates fail, the turn replies with the fixed fallback from config ("I don't have that in mind
right now. Could you tell me again?").

"Misattributed" (Berk, Phase 6 live check): a sentence that tells the user "you mentioned ..."
about something only another person's recalled line says. Talking to Deniz, Burak's "I saw the
sun finally in Berlin" came back as "you mentioned seeing the sun in Berlin". It counts when the
sentence shares more content words with other people's lines (words found nowhere in the user's own
context: their message, earlier turns, the summary, their own memories) than with that own context.

"Not in context": a sentence that claims a memory ("you told me ...") must share at least one
content word with what came BEFORE the current message (earlier turns, the session summary,
recalled memories). The current message does not count: "Do you remember what I told you about
my interview?" -> "You told me your interview went well" repeats the question's words but is
still invented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from hunch.memory.forget_requests import claims_forgetting
from hunch.pipeline.checks import (
    REPLY_LANG,
    asks_about_past,
    denies_memory_system,
    detect_language,
    explains_memory_mechanics,
    fold,
    foreign_script,
    memory_claim_sentences,
    talks_about_own_mood,
)

_CONTENT_WORD = re.compile(r"[^\W\d_]{4,}")
# Words too common to ground a memory claim on their own.
COMMON_WORDS = frozenset(
    "that this with what when where your about there their they them then than have been "
    "were will would could should just really very told tell said mentioned remember last "
    "time earlier know think like also from into some much more because going thing things "
    "sounds feel feeling today yesterday week".split()
)
# A sentence that makes something the user's own (matched on folded text): something they did
# or said ("you mentioned", "you described", "you were debating") or have ("your sister").
_SECOND_PERSON_CLAIM = re.compile(
    r"\b(?:you|u)(?:'ve| have| had)? (?:just |once |already |even )?(?:[^\W\d_]+ed|said|told"
    r"|brought up|wrote|thought|felt|spent|sent|went|made|took|got|began|were [^\W\d_]+ing"
    r"|was [^\W\d_]+ing|talked|wondered|asked)\b|\bas you (?:said|mentioned|put it)\b"
    r"|\byour\b|\bof yours\b"
)
_POINTS_BACK = re.compile(
    r"\b(?:earlier|before|last (?:time|week|month|night|year)|yesterday|the other day"
    r"|a while (?:ago|back)|previously|recently)\b"
)
_SENTENCE_END = re.compile(r"[.!?…][\"')\]]*(?=\s|$)")


@dataclass(frozen=True, slots=True)
class FilterResult:
    id: str
    text: str
    reasons: tuple[str, ...]  # empty = passed
    repaired_from: str | None = None  # the original text, if a repair made it pass

    @property
    def passed(self) -> bool:
        return not self.reasons


def content_words(text: str) -> set[str]:
    return {w for w in _CONTENT_WORD.findall(fold(text)) if w not in COMMON_WORDS}


def trim_to_last_sentence(text: str) -> str:
    """A candidate that hit the token cap is cut back to its last full sentence."""
    ends = list(_SENTENCE_END.finditer(text))
    return text[: ends[-1].end()].strip() if ends else text.strip()


def invented_memory(text: str, prior_context: str, message: str = "") -> bool:
    """A claim must rest on what came before. The current message counts too ("You said work
    was long"), unless it asks about the past (echoing it would invent the answer) or the claim
    points back past it ("you said hello earlier today", "you told me last month")."""
    claims = memory_claim_sentences(text)
    if not claims:
        return False
    before = content_words(prior_context)
    now = before if asks_about_past(message) else before | content_words(message)
    return any(
        not (content_words(s) & (before if _POINTS_BACK.search(fold(s)) else now)) for s in claims
    )


@dataclass(frozen=True, slots=True)
class Attribution:
    """Who said what this turn: the user's own context and other people's recalled lines."""

    own: str
    others: tuple[tuple[str, str], ...]  # (who said it, the recalled line)


def misattributed_memory(text: str, attribution: Attribution) -> bool:
    own = content_words(attribution.own)
    for s in re.split(r"(?<=[.!?;])\s+|\n+", text):
        folded = fold(s)
        # A sentence that names the speaker gives the line back to them ("Tom's sister ...").
        foreign = set().union(
            *(content_words(line) for who, line in attribution.others
              if not re.search(rf"\b{re.escape(fold(who))}\b", folded))
        ) - own  # fmt: skip
        for clause in _CLAUSE_BOUNDARY.split(folded):
            claim = _SECOND_PERSON_CLAIM.search(clause)
            if claim is None:
                continue
            # What the claim covers: what follows it ("you mentioned <seeing the sun in Berlin>"),
            # the whole clause ("the drumming neighbour you mentioned"), or the sentence when the
            # claim stands alone ("As you said, those new drivers ...").
            alone = not content_words(clause[: claim.start()] + clause[claim.end() :])
            views = [clause[claim.end() :], clause, *([folded] if alone else [])]
            for words in map(content_words, views):
                if len(words & foreign) > len(words & own):
                    return True
    return False


@dataclass(frozen=True, slots=True)
class HunchTurn:
    """The user asked why (ask) or accepted the offer to think (think_more) this turn."""

    trigger: str  # "ask" | "think_more"
    level: int  # the hunch's revealed level after this turn's attempt
    key: str | None  # what a reply must pass on at levels 1-2 ("someone", "Mara")


# A reason the reflection did not reveal ("because you're stressed", "I was trying to connect
# the dots"). Phase 4 bench: in a real conversation the model gave one on 4 of 4 trigger turns.
# "I don't know where it comes from" is not one. Implied reasons count too (asked-why probe with
# a work deadline in the conversation): "it feels like you might be stretched too thin",
# "since you're swamped with work", "it feels risky to commit when your deadline is looming".
_HUNCH_REASON = re.compile(
    r"\bbecause\b|\bbased on\b|\bdue to\b|\bi was (?:just |only )?trying to\b|\bthe reason\b"
    r"|\bthat's why\b|\b(?:came|comes|coming) from (?:the|your|you|what|how)\b"
    r"|\bit was (?:just |really )?(?:a feeling |my way of )?(?:about|connecting|linking) "
    r"(?:the|your)\b"
    r"|\b(?:feels?|felt|seems?|seemed|sensed?)(?: like| as if| that)? you(?:'re| are"
    r"| might(?! want)| may(?! want)| could| would(?! like)| need| should| aren't| won't)\b"
    r"|\bsince you(?:'re| are| have|'ve| seem)?\b|\bwhen your\b|\bgiven (?:your|that you)\b"
    # Berk (Phase 5, golden at level 2): attributing the feeling to something the user said is
    # an invented source below level 3 ("seemed to stem from what you mentioned earlier about
    # Mara", "surfaced when you mentioned Mara"); the reflection revealed only "Mara".
    r"|\b(?:stem|stems|stemmed|stemming|arose|arises|surfaced|came up) (?:from|when)\b"
    r"|\b(?:you|u) (?:mentioned|told me|said|brought up|talked about)\b"
    r"|\bwhat (?:you|u) (?:mentioned|said|told me|brought up)\b"
)
_NOT_KNOWING = (
    "can't tell", "cannot tell", "don't know", "do not know", "not sure", "no idea",
    "can't figure", "can't place", "couldn't", "can't say", "still can't",
)  # fmt: skip
# Berk (Phase 5): below level 2 a hunch has no topic the reflection revealed. "a hunch I had
# about the timing" (Phase 4 bench, level 0) passed as honest; now only a pronoun or the
# unlocked key may follow ("a hunch about it", "a hunch about someone").
_HUNCH_TOPIC = re.compile(
    r"\bhunch(?: (?:i had|i've had|i have|i got|i'd had))?"
    r" (?P<prep>about|regarding|around|concerning) (?P<topic>[^\W\d_]+(?:'[^\W\d_]+)?)"
)
_TOPIC_OK = frozenset({"it", "that", "this", "what"})
# What a repair may cut out of an otherwise good trigger-turn reply (Berk, Phase 5).
_REPAIRABLE = frozenset({"hunch_reason", "hunch_topic"})
_CLAUSE_BOUNDARY = re.compile(r"\s*[,;:—–]\s*|\s+-\s+")


def _topic_claim(folded: str, turn: HunchTurn) -> re.Match[str] | None:
    if turn.level >= 2:
        return None
    key = turn.key.casefold() if turn.key else None
    for m in _HUNCH_TOPIC.finditer(folded):
        topic = m.group("topic")
        if topic not in _TOPIC_OK and topic != key:
            return m
    return None


def hunch_reasons(text: str, turn: HunchTurn) -> list[str]:
    """Berk (Phase 4): on a trigger turn the reply says it is a hunch, gives no reason beyond
    what the reflection unlocked, and passes the unlocked category or cue on unchanged."""
    folded = fold(text)
    reasons = []
    if turn.trigger == "ask" and "hunch" not in folded:
        reasons.append("hunch_unsaid")
    if turn.level < 3 and _HUNCH_REASON.search(folded):
        reasons.append("hunch_reason")
    if _topic_claim(folded, turn):
        reasons.append("hunch_topic")
    if turn.key is not None and turn.key.casefold() not in folded:
        reasons.append("hunch_realisation_missing")
    if turn.key == "someone" and re.search(r"\babout you\b", folded):
        reasons.append("hunch_distorted")  # "about someone" became "about you"
    if (
        turn.trigger == "think_more"
        and turn.level == 0
        and not any(p in folded for p in _NOT_KNOWING)
    ):
        reasons.append("hunch_no_admission")
    return reasons


def check_candidate(
    text: str,
    prior_context: str,
    hunch_turn: HunchTurn | None = None,
    forget_turn: bool = False,
    mood_masked: bool = False,
    attribution: Attribution | None = None,
    message: str = "",
) -> tuple[str, ...]:
    reasons = []
    if not text.strip():
        reasons.append("empty")
    if foreign_script(text):
        reasons.append("foreign_script")
    if detect_language(text) not in (REPLY_LANG, None):
        reasons.append("not_english")
    if invented_memory(text, prior_context, message):
        reasons.append("invented_memory")
    if attribution is not None and misattributed_memory(text, attribution):
        reasons.append("misattributed_memory")
    if denies_memory_system(text):
        reasons.append("denies_memory")
    if explains_memory_mechanics(text):
        reasons.append("memory_mechanics")
    if hunch_turn is not None:
        reasons += hunch_reasons(text, hunch_turn)
    if forget_turn and claims_forgetting(text):  # Berk, Phase 5: close the topic, don't "forget"
        reasons.append("claims_forgetting")
    if mood_masked and talks_about_own_mood(text):  # Berk, Phase 5: masked means unsaid
        reasons.append("mood_unmasked")
    return tuple(reasons)


def _cut(sentence: str, turn: HunchTurn) -> int | None:
    """Where the first reason or topic claim starts in a sentence, if any."""
    folded = fold(sentence)
    starts = []
    if turn.level < 3 and (m := _HUNCH_REASON.search(folded)):
        starts.append(m.start())
    if t := _topic_claim(folded, turn):
        starts.append(t.start("prep"))
    return min(starts) if starts else None


def repair_hunch_reply(text: str, prior_context: str, turn: HunchTurn) -> str | None:
    """Berk (Phase 5): a trigger-turn candidate whose only problem is a reason or a topic claim
    loses that part. It is cut at the last clause boundary (comma, semicolon, colon or dash)
    before the claim, if at least three words come before it ("Just a hunch, because you seem
    tired." -> "Just a hunch."); otherwise the whole sentence goes, so no half-sentence is left
    (golden, Phase 5). The rest must still pass every check, so it still says "hunch"."""
    kept = []
    for sentence in re.split(r"(?<=[.!?…])\s+", text.strip()):
        cut = _cut(sentence, turn)
        if cut is None:
            kept.append(sentence)
            continue
        bounds = [m.start() for m in _CLAUSE_BOUNDARY.finditer(sentence[:cut])]
        if not bounds:
            continue
        head = sentence[: bounds[-1]].rstrip(" ,;:—–-…")
        if len(head.split()) >= 3 and _cut(head, turn) is None:
            kept.append(head if head[-1] in ".!?" else f"{head}.")
    repaired = " ".join(kept)
    if not kept or repaired == text.strip():
        return None
    return None if check_candidate(repaired, prior_context, turn) else repaired


def filter_candidates(
    texts: dict[str, str],
    prior_context: str,
    hunch_turn: HunchTurn | None = None,
    forget_turn: bool = False,
    mood_masked: bool = False,
    attribution: Attribution | None = None,
    message: str = "",
) -> tuple[list[FilterResult], list[FilterResult]]:
    """(passed, all) in candidate order. On a trigger turn a candidate rejected only for a reason
    or topic claim is repaired if it can be (`repaired_from` keeps the original)."""
    results = []
    for cid, t in texts.items():
        reasons = check_candidate(
            t, prior_context, hunch_turn, forget_turn, mood_masked, attribution, message
        )
        if hunch_turn is not None and reasons and set(reasons) <= _REPAIRABLE:
            fixed = repair_hunch_reply(t, prior_context, hunch_turn)
            if fixed is not None:
                results.append(FilterResult(cid, fixed, (), repaired_from=t))
                continue
        results.append(FilterResult(cid, t, reasons))
    return [r for r in results if r.passed], results

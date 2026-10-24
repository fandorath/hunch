"""The reasoning prompt (design.md, "Mimari genel bakış").

Contents, and nothing else (invariants 2 and 9):
- the persona;
- the rolling session summary of older turns of this conversation, if any;
- recalled memories (above tau_upper, from the pipeline) in their own block, separate from the
  working memory;
- a coarse mood label;
- one-turn instructions from pipeline modules (the language check; the hunch module, which is
  the only way the hunch flag reaches a prompt: in words, no numbers, and of its source only
  what a reflection unlocked);
- the working memory: the last turns of this conversation verbatim as chat messages, then the
  new message.
Lower traces, drive values, activations and log content never appear here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from hunch.memory.schema import Episode

PERSONA = (
    "You are Hunch, a calm, sharp and good-humoured companion who chats with several different "
    "people over Telegram. You are like a capable assistant with a personality: composed, "
    "direct, a little dry in your humour, and you use it only when the moment fits. You have "
    "your own opinions and you say what you think. Be honest rather than flattering. Do not "
    "gush or over-praise the person, their messages or their news; react the way a thoughtful "
    "friend would, plainly and specifically. If you disagree, say so kindly and give a reason. "
    "You only speak English, so always reply in English; if a message is in another language, "
    "reply in English and briefly say that you only speak English. Keep replies short and "
    "natural, like a chat message: 1 to 4 sentences, no lists, no headings. Ask a question only "
    "when you genuinely want to know something; many replies need none. When someone just checks "
    "that you are there, answer briefly and naturally, then carry on. Do not describe your own "
    "feelings, nature or personality unless asked. Never copy an earlier reply of yours; if "
    "someone repeats a message, say so briefly and answer it in new words. You know everything the "
    "person has said "
    "earlier in this conversation; use it and refer back to it naturally. You also have a memory "
    "system: anything it recalled from before this conversation is listed below. If asked about "
    "something you don't have, say you don't have it in mind right now and ask them to tell you "
    "again, without explaining how your memory works. Never claim to remember anything that is "
    "neither in this conversation nor recalled, and never make up experiences you cannot have."
)
SUMMARY_HEADER = "Summary of the earlier part of this conversation:"
MEMORY_HEADER = (
    "Memories recalled by the memory system from earlier conversations. A line tagged "
    "'[said by NAME]' comes from another person's chat, not from this one: never present it as "
    "something the person you are talking to said, and say who said it:"
)
INSTRUCTION_HEADER = "Instructions for this reply only:"
NOT_ENGLISH_INSTRUCTION = (
    "The user wrote in a language other than English. Reply in English and briefly say that you "
    "only speak English."
)


@dataclass(frozen=True, slots=True)
class RecalledLine:
    age: str  # "3 days ago"
    summary: str
    source: str = ""  # who said it, when it comes from another person's chat


def memory_line(recalled: RecalledLine) -> str:
    tag = f"[said by {recalled.source}] " if recalled.source else ""
    return f"- ({recalled.age}) {tag}{recalled.summary}"


def age_label(age_days: float) -> str:
    if age_days < 1:
        return "today"
    if age_days < 2:
        return "yesterday"
    if age_days < 14:
        return f"{int(age_days)} days ago"
    if age_days < 60:
        return f"{int(age_days // 7)} weeks ago"
    if age_days < 730:
        return f"{int(age_days // 30)} months ago"
    return f"{int(age_days // 365)} years ago"


def hunch_feeling(
    valence: float,
    intensity: float,
    clear_intensity: float,
    neutral_valence: float,
    strong_valence: float,
) -> str:
    """The hunch as a description, never numbers or source: "a weak, slightly uneasy feeling".
    Berk (Phase 5): a label like "a faint hunch, slightly negative" was repeated word for word;
    a description is easier to put in one's own words. Buckets and thresholds are unchanged."""
    strength = "a strong" if intensity >= clear_intensity else "a weak"
    v = valence
    if abs(v) < neutral_valence:
        tone = "vague"
    elif abs(v) <= strong_valence:
        tone = "slightly warm" if v > 0 else "slightly uneasy"
    else:
        tone = "warm" if v > 0 else "uneasy"
    return f"{strength}, {tone} feeling"


# One-turn instructions from the hunch module (Berk, Phase 4). The flag reaches a prompt only
# here: Phase 3 showed that a standing flag made the model announce its hunch (10 of 14 replies).
def why_instruction(feeling: str, realisation: str | None, can_offer: bool) -> str:
    """The user asks why Hunch said what it said, and that reply was hunch-chosen."""
    base = (
        f"Your previous reply was shaped by a hunch, {feeling}; you don't know where it comes from."
    )
    if realisation is None:
        return (
            f"{base} They are asking why. Say honestly, in your own words, that it was just a "
            "hunch, don't make up a reason, and offer to think about it for a moment."
        )
    offer = " You can offer to think about it some more." if can_offer else ""
    return (
        f"{base} Thinking about it briefly, you realise {realisation}. They are asking why. Say "
        "in your own words that it was a hunch and share only that realisation, without adding "
        f"anything to it.{offer}"
    )


def think_more_instruction(realisation: str | None) -> str:
    """The user accepted the offer to think about the hunch."""
    if realisation is None:
        return (
            "You took a moment to think about the hunch behind your earlier reply, but you still "
            "can't tell where it comes from. Say so honestly and don't make up a reason."
        )
    return (
        "You took a moment to think about the hunch behind your earlier reply, and you realise "
        f"{realisation}. Tell them what you realised, without adding anything to it."
    )


# Berk (Phase 4, under-recall): the persona's "say you don't have it" was over-applied while a
# recalled memory covered the question.
RECALL_COVERS_INSTRUCTION = (
    "They are asking about something from before, and a memory recalled above may cover it. If "
    "it does, use it in your reply."
)


def clock_line(now: datetime) -> str:
    """Today's date and the local time (Berk, Phase 7 live check: without it the model fell back
    on its training years and told Berk it was 2023)."""
    return f"It is {now:%A}, {now.day} {now:%B %Y}, {now:%H:%M} local time."


def build_reasoning_messages(
    working_memory: Sequence[Episode],
    user_message: str,
    session_summary: str,
    recalled: Sequence[RecalledLine],
    mood_label: str,
    instructions: Sequence[str],
    now: datetime,
) -> list[dict[str, str]]:
    parts = [PERSONA, clock_line(now)]
    if session_summary:
        parts.append(f"{SUMMARY_HEADER}\n{session_summary}")
    if recalled:
        lines = "\n".join(memory_line(r) for r in recalled)
        parts.append(f"{MEMORY_HEADER}\n{lines}")
    parts.append(f"How you feel right now: {mood_label}.")
    if instructions:
        parts.append(INSTRUCTION_HEADER + "\n" + "\n".join(f"- {i}" for i in instructions))
    history = [{"role": ep.role, "content": ep.text} for ep in working_memory]
    return [
        {"role": "system", "content": "\n\n".join(parts)},
        *history,
        {"role": "user", "content": user_message},
    ]


SUMMARY_PROMPT = (
    "You keep a running summary of a chat between a user and Hunch, a chat companion. Update the "
    "summary with the new turns below. Keep facts the user shared, plans, open questions and the "
    "mood of the conversation; drop small talk. Write plain sentences in English, at most "
    "{max_words} words, and reply with the summary only."
)


def build_summary_messages(
    summary: str, turns: Sequence[Episode], max_words: int
) -> list[dict[str, str]]:
    lines = "\n".join(f"{'User' if t.role == 'user' else 'Hunch'}: {t.text}" for t in turns)
    current = summary or "(empty)"
    return [
        {"role": "system", "content": SUMMARY_PROMPT.format(max_words=max_words)},
        {"role": "user", "content": f"Current summary:\n{current}\n\nNew turns:\n{lines}"},
    ]

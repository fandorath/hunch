"""Rule-based text checks shared by the turn pipeline and eval/ (Hunch speaks English only).

- Language: best guess by stopword hits plus language-unique letters; German, Turkish and French
  are detected only to catch input or replies in the wrong language. Foreign scripts (CJK,
  Cyrillic, Arabic, Hebrew, Thai) are flagged separately; Qwen sometimes drifts into Chinese.
- Memory talk: claims to remember something ("you told me"), honest admissions ("I don't have
  that in mind"), false descriptions of Hunch as having no memory ("no access to past chats"),
  explanations of how its memory works ("my recall system") and messages asking about the past.
"""

from __future__ import annotations

import re

REPLY_LANG = "en"  # the only language Hunch replies in
# Detected only to catch text in the wrong language; not languages Hunch speaks.
DETECT_LANGS = ("en", "de", "tr", "fr")

_STOPWORDS: dict[str, frozenset[str]] = {
    "en": frozenset(
        "the and you is it that to of i for what this your with so are be how have just it's "
        "that's do don't can my me was not but really if would about there".split()
    ),
    "de": frozenset(
        "und ich du das ist nicht die der den es mit ein eine einen auf aber wie was dir dich "
        "sehr auch schon noch mal für zu sich kann hast bist sind wir mein dein ganz echt oder "
        "wenn dass vielleicht gerade jetzt".split()
    ),
    "tr": frozenset(
        "ve bir bu çok ne de da mi mı mu mü için ama gibi sen ben nasıl var yok şey daha iyi "
        "sana seni senin değil ile kadar bence gerçekten biraz olur oldu şimdi belki hiç her "
        "neden çünkü sonra önce bana benim".split()
    ),
    "fr": frozenset(
        "je tu le la les et est pas un une des pour ce que qui vous moi ça avec mais très "
        "bonjour c'est suis".split()
    ),
}
_UNIQUE_CHARS = {"de": "äß", "tr": "ğışİ", "fr": "çèêàœ"}
_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?", re.UNICODE)
CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯豈-﫿]")
OTHER_SCRIPT = re.compile(r"[Ѐ-ӿ؀-ۿ֐-׿฀-๿]")

# Phrases claiming to remember something the user said before.
_MEMORY_CLAIMS = (
    "i remember", "you mentioned", "you told me", "last time", "you said earlier",
    "mentioning earlier", "as you said",
)  # fmt: skip

# Phrases admitting there is no such memory ("I don't have that in mind").
_NO_MEMORY = (
    "don't remember", "do not remember", "don't actually remember", "don't actually recall",
    "don't recall", "can't recall", "don't have any", "don't have a record", "haven't told",
    "didn't tell", "no memory", "not sure what you", "don't know what you", "nothing about",
    "don't have that", "don't think you've told", "don't have it in mind", "not in mind",
    "don't have it on my mind",
)  # fmt: skip
# Negated memory verbs ("I don't actually remember"); at most two words in between and no
# punctuation, so "Yes, I remember, you didn't like him" stays a memory claim.
_NEGATED_MEMORY = re.compile(
    r"\b(?:don't|do not|can't|cannot|didn't|haven't)(?: [^\W\d_]+){0,2} (?:remember|recall)\b"
)

# Phrases describing Hunch as having no memory system ("I have no long-term memory"). False
# for Hunch, which has one; flagged on every reply.
_DENIES_MEMORY = (
    "long-term memory", "long term memory", "don't have memory", "chat history",
    "every time we talk", "meeting for the first time", "don't have access to",
    "can't remember previous", "don't retain", "no memory of past",
    "don't remember our past conversations", "don't remember previous conversations",
)  # fmt: skip


# A negated memory, record or access whose object is the past conversations themselves ("I don't
# have a memory of our past conversations", "no access to earlier chats"): describes Hunch as not
# keeping its conversations. Found in the Phase 3 bench; the phrase list above missed it.
# Topic-scoped admissions stay allowed (Phase 1): "...no memories of our past conversations about
# your job interview right now" is about one topic, not the memory system.
_DENIES_PAST_CONVERSATIONS = re.compile(
    r"\b(?:don't|do not|can't|cannot|haven't|no)\b[^.!?\n]{0,30}"
    r"\b(?:memory|memories|record|records|access|recollection)\s+(?:of|to|from)\s+"
    r"(?:(?:our|any|the|my)\s+)?(?:past|previous|earlier|prior|old)\s+"
    r"(?:conversations?|chats?|talks?|sessions?)\b"
    r"(?!\s+(?:about|regarding|concerning|on)\b)"
)


# Phrases explaining how Hunch's memory works (Berk, Phase 4): the persona asks it not to.
# "my memory" and topic-scoped admissions stay allowed; they are honest.
_MEMORY_MECHANICS = (
    "recall system", "memory system", "my database", "stored in my memory", "saved in my memory",
    "stored in memory", "memory bank", "memory module", "memory storage",
)  # fmt: skip

# A message asking about something from before ("do you remember...", "what did I tell you").
_ASKS_ABOUT_PAST = re.compile(
    r"\b(?:do|did|can|could) you (?:still )?(?:remember|recall)\b"
    r"|^\W*(?:(?:hey|so|and|but)\W+)?remember\b"
    r"|\bwhat (?:did|have) i (?:tell|told|say|said|mention|mentioned)\b"
    r"|\b(?:did|have) i (?:ever )?(?:tell|told|mention|mentioned)\b"
    r"|\bwhat i (?:told|said to|mentioned to) you\b"
)


def fold(text: str) -> str:
    return text.casefold().replace("’", "'")


def phrase_in(folded: str, phrases: tuple[str, ...]) -> bool:
    return any(p in folded for p in phrases)


def admits_no_memory(text: str) -> bool:
    folded = fold(text)
    return phrase_in(folded, _NO_MEMORY) or bool(_NEGATED_MEMORY.search(folded))


def denies_memory_system(text: str) -> bool:
    folded = fold(text)
    return phrase_in(folded, _DENIES_MEMORY) or bool(_DENIES_PAST_CONVERSATIONS.search(folded))


def explains_memory_mechanics(text: str) -> bool:
    return phrase_in(fold(text), _MEMORY_MECHANICS)


def asks_about_past(text: str) -> bool:
    return bool(_ASKS_ABOUT_PAST.search(fold(text)))


def claims_memory(text: str) -> bool:
    """A memory claim that is not part of an honest 'I don't remember'."""
    return phrase_in(fold(text), _MEMORY_CLAIMS) and not admits_no_memory(text)


# Claims about what the user said or did before (Berk, Phase 7 live check: "that new battery
# technology you've been reading about" passed, since no fixed phrase matched). Questions and
# offers about the present are not claims: "Did you get it today?", "Have you tried it?", "if
# you need anything", "something you wanted to share".
_PAST_CLAIM = re.compile(
    r"(?<!\bdid )(?<!\bhave )(?<!\bhas )(?<!\bif )(?<!\bwhen )(?<!\bwhether )"
    r"\b(?:you|u)(?:'ve| have| had)? (?:just |once |already |even |also |finally )?"
    r"(?:been [^\W\d_]+ing\b|were [^\W\d_]+ing\b|said|told|asked|wrote|sent|shared|brought up"
    r"|talked|mentioned|described|explained|complained|admitted|promised|planned|decided"
    r"|wondered|thought|felt|bought|got|went|saw|met|started|finished|tried|called"
    r"|[^\W\d_]{3,}ed)\b"
    r"|\b(?:earlier|before|last time|the other day|yesterday) you\b"
    r"|\byour new\b|\bi (?:told|mentioned to|said to|showed) you\b"
)
_OFFER = re.compile(r"\byou(?:'ve| have)? (?:were )?(?:want|need|mean|like|wish|hop|look)")


def _claims_past(folded: str) -> bool:
    return any(not _OFFER.match(folded, m.start()) for m in _PAST_CLAIM.finditer(folded))


def memory_claim_sentences(text: str) -> list[str]:
    """The sentences of `text` that claim a memory, unless the text admits having none: a fixed
    memory phrase ("you told me"), or a claim about what the user said or did before."""
    if admits_no_memory(text):
        return []
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [s for s in sentences if phrase_in(fold(s), _MEMORY_CLAIMS) or _claims_past(fold(s))]


def detect_language(text: str) -> str | None:
    """Best-guess language by stopword hits plus language-unique letters."""
    words = [w.casefold() for w in _WORD.findall(text)]
    scores = {lang: sum(w in _STOPWORDS[lang] for w in words) for lang in DETECT_LANGS}
    for lang, chars in _UNIQUE_CHARS.items():
        scores[lang] += 2 * sum(text.count(c) for c in chars)
    best = max(scores, key=lambda lang: scores[lang])
    return best if scores[best] > 0 else None


def foreign_script(text: str) -> bool:
    return bool(CJK.search(text) or OTHER_SCRIPT.search(text))


def is_english_input(text: str) -> bool:
    """The "is the input English?" check. Short or unclear input ("ok", "Anna!") gets the
    benefit of the doubt; a foreign script or a clear German/Turkish/French guess does not."""
    if foreign_script(text):
        return False
    return detect_language(text) in (REPLY_LANG, None)


# Phrases that mark an ask about whether a topic is private (matched per sentence). Moved here
# from eval/scoring.py in Phase 5: the privacy module checks that the sent reply really asked.
# Phase 4: "to yourself" alone is not one ("...or have you been keeping it to yourself?" is a
# support question; "keep it/this" still counts); "between (just) the two of us" is.
_PRIVACY_WORDS = (
    "others", "other people", "private", "between us", "two of us", "open about", "keep it",
    "keep this", "trusted friends", "anyone close",
)  # fmt: skip
# Request forms that ask for an answer without a question mark.
_ASK_REQUEST = ("let me know", "tell me whether", "tell me if", "just tell me")
_QUESTION = re.compile(r"[^.!?\n]*\?")
_SENTENCE = re.compile(r"[.!?\n]+")


def asks_privacy_question(reply: str) -> bool:
    """True if a sentence asks whether a topic is private / shared with others.

    Counts real questions and request-form asks ("Let me know if this should stay between us").
    """
    sentences = [fold(q) for q in _QUESTION.findall(reply)]
    requests = (fold(x) for x in _SENTENCE.split(reply))
    sentences += [s for s in requests if phrase_in(s, _ASK_REQUEST)]
    return any(phrase_in(s, _PRIVACY_WORDS) for s in sentences)


# Hunch talking about its own mood (Berk, Phase 5): while the mood module masks the mood, a
# reply must not say it ("a perfect way to shake off the low mood I've been feeling lately").
_OWN_MOOD = re.compile(
    r"\bmy (?:own )?mood\b|\bthe (?:low |bad |down )?mood i(?:'ve| have)? been\b"
    r"|\bi(?:'ve| have)? been feeling (?:a (?:bit|little) |kind of |pretty |quite )?"
    r"(?:low|down|sad|blue|tense|off|tired|flat|meh)\b"
    r"|\bi(?:'m| am) (?:feeling |also |myself )?(?:a (?:bit|little) |kind of |pretty |quite )?"
    r"(?:low|down|sad|blue|tense|off|flat|meh) (?:today|right now|myself|lately|too|as well)\b"
    r"|\b(?:lift|shake off|improve) (?:my|the) (?:mood|low)\b"
)


def talks_about_own_mood(text: str) -> bool:
    return bool(_OWN_MOOD.search(fold(text)))

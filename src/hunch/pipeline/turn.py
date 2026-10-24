"""The turn pipeline (design.md, "Mimari genel bakış"; Phase 3).

Reply path, in this order (invariant 4: the value gate is always last):
  1. "is the input English?" check -> one-turn instruction if not
  2. working memory: last N exchanges verbatim + rolling session summary
  3. cue extraction (LLM + rule-based dates); the query embedding runs on CPU in parallel
  4. activation over the candidates: upper memories enter reasoning, lower ones only act below;
     every recall is reconsolidated
  5. drive vector from the lower traces; hunch triggers (Phase 4): if the user asks why about a
     hunch-chosen reply, or accepts the offer to think about it, a reflection attempt runs and a
     one-turn instruction carries the hunch in words plus what was unlocked, nothing more
  6. reasoning prompt -> all candidates in one batched call
  7. candidate filter (all fail -> fixed fallback reply)
  8. judge: quality and core values for the remaining candidates, one greedy call
  9. modulation: selection above the quality floor, small exploration
 10. value gate on the chosen candidate (rule checks + judge verdict), then the next ones
 11. reply; a Hunch is stored if the drive's pick materially changed the choice; raw turns
     appended, turn log written
After the reply (off the latency path): the user's message is encoded as a memory, what a
reflection unlocked is stored as a realisation memory, a strong conflict triggers a reflection of
its own, and turns that left the working memory are folded into the session summary.

Every model prompt is built by hunch.pipeline.prompt, hunch.values.gate or
hunch.recall.cues; none of them receives lower traces, drive values or log content (invariant 2,
tests/test_pipeline_prompts.py).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from hunch.config import Config
from hunch.drive.drive import (
    LowerTrace,
    candidate_features,
    compute_drive,
    drive_score,
    summarize_traces,
    trace_weight,
)
from hunch.drive.modulation import Scored, Selection, select
from hunch.llm.types import ChatLLM, SamplingSettings
from hunch.loops.dedup import SAME_MATTER_MAX_NEW_TOKENS, fresh_drafts, judged_same
from hunch.loops.extract import extract_drafts, to_loops
from hunch.loops.outreach import (
    FALLBACK,
    Kind,
    OutreachResult,
    describes_own_experience,
    instruction_for,
)
from hunch.loops.store import LoopStore, OpenLoop
from hunch.memory.embeddings import Embedder
from hunch.memory.encoding import encode_affect, encode_memory
from hunch.memory.forget import (
    CLOSED_TOPIC_INSTRUCTION,
    FORGET_INSTRUCTION,
    ForgetResult,
    user_forget,
)
from hunch.memory.forget_requests import detect_forget_request
from hunch.memory.schema import Episode
from hunch.memory.store import MemoryStore, select_working_memory
from hunch.mood.signals import asks_how_hunch_is, is_apology, is_hostile
from hunch.mood.state import (
    Exchange,
    MoodStore,
    apply_exchange,
    apply_mood_event,
    drive_terms,
    prompt_mood,
    shows_mood,
    stress_factor,
)
from hunch.observability.turn_log import DisclosureLog, ReflectionLog, TurnLog
from hunch.pipeline.checks import admits_no_memory, asks_about_past, is_english_input
from hunch.pipeline.filter import (
    Attribution,
    HunchTurn,
    check_candidate,
    content_words,
    filter_candidates,
    trim_to_last_sentence,
)
from hunch.pipeline.identity import claimed_identity, identity_instruction
from hunch.pipeline.prompt import (
    NOT_ENGLISH_INSTRUCTION,
    RECALL_COVERS_INSTRUCTION,
    RecalledLine,
    age_label,
    build_reasoning_messages,
    build_summary_messages,
    hunch_feeling,
    think_more_instruction,
    why_instruction,
)
from hunch.privacy.categories import CategoryDetector
from hunch.privacy.profile import PendingQuestion, PrivacyModule, PrivacyTurn, ProfileStore
from hunch.recall.activation import SECONDS_PER_DAY
from hunch.recall.cues import CueExtraction, extract_cues
from hunch.recall.involuntary import SessionRecallState
from hunch.recall.retrieve import recall, reconsolidate
from hunch.reflection.records import MAX_LEVEL, Hunch, SourceRef
from hunch.reflection.reflect import ReflectionOutcome, Reflector
from hunch.reflection.triggers import accepts_offer, asks_why
from hunch.values.core import CoreValues
from hunch.values.gate import (
    Verdict,
    build_disclosure_messages,
    build_judge_messages,
    build_second_opinion_messages,
    disclosure_hits,
    disclosure_terms,
    distinctive_pairs,
    judge_context,
    pair_hits,
    parse_disclosure,
    parse_second_opinion,
    parse_verdicts,
    source_hint,
)

CANDIDATE_IDS = "abcdefghij"
JUDGE_CONTEXT_EXCHANGES = 3  # the judge sees the last few exchanges, not the whole window
CUE_MAX_NEW_TOKENS = 256
SUMMARY_MAX_NEW_TOKENS = 256
LOOP_MAX_NEW_TOKENS = 160
# The chat template needs a user turn; Hunch writes first, so this one is not stored.
OUTREACH_TRIGGER = "(Write your message now, following the instructions above.)"


@dataclass
class Session:
    """One conversation with one user; lives as long as the chat (not persisted)."""

    conversation_id: str
    user: str
    recall_state: SessionRecallState = field(default_factory=SessionRecallState)
    summary: str = ""
    summarized_upto: int = -1  # highest turn_index already folded into the summary
    turn_no: int = 0
    last_hunch_id: str | None = None  # the hunch that chose the previous reply, if any
    offered_hunch_id: str | None = None  # "want me to think about it?" is open for this hunch
    pending_privacy: PendingQuestion | None = None  # a privacy question the next message answers
    resummarize: bool = False  # a user forget closed turns already folded into the summary


@dataclass(frozen=True)
class TurnResult:
    reply: str
    turn_id: str
    log: dict[str, Any]  # the design.md turn log record
    details: dict[str, Any]  # admin details: texts, reasons, latency
    cues: CueExtraction
    user_episode: Episode
    query_vec: np.ndarray | None
    hunch: Hunch | None = None  # created this turn
    reflection: ReflectionOutcome | None = None  # triggered by this message (ask / think_more)
    conflict: bool = False  # the hunch's pick is far below the best quality: reflect after reply
    privacy: PrivacyTurn | None = None  # Phase 5: categories, question, answer of this message
    forget: ForgetResult | None = None  # Phase 5: this message asked to forget something


class _Timer:
    def __init__(self) -> None:
        self.stages: dict[str, float] = {}
        self._t = time.perf_counter()

    def lap(self, name: str) -> None:
        now = time.perf_counter()
        self.stages[name] = round(now - self._t, 3)
        self._t = now


class TurnPipeline:
    def __init__(
        self,
        cfg: Config,
        values: CoreValues,
        llm: ChatLLM,
        store: MemoryStore,
        embedder: Embedder | None,
        turn_log: TurnLog | None = None,
        clock: Callable[[], float] = time.time,
        seed: int = 0,
        new_id: Callable[[], str] = lambda: uuid.uuid4().hex,
        reflection_log: ReflectionLog | None = None,
        disclosure_log: DisclosureLog | None = None,
    ) -> None:
        self.cfg = cfg
        self.values = values
        self.llm = llm
        self.store = store
        self.embedder = embedder
        self.turn_log = turn_log
        self.clock = clock
        self.rng = np.random.default_rng(seed)
        self.new_id = new_id
        if reflection_log is None and turn_log is not None:
            reflection_log = ReflectionLog(turn_log.dir, core_dir=Path(turn_log.core_dir))
        # Reflection draws come from their own seeded stream, so they don't shift the turn's.
        self.reflector = Reflector(
            cfg.reflection, store, np.random.default_rng([seed, 4]), self._feeling,
            cfg.encoding, reflection_log, new_id, clock,
        )  # fmt: skip
        # Fixed-reply variants come from their own stream too (Berk, Phase 5).
        self.reply_rng = np.random.default_rng([seed, 5])
        # Phase 5: mood and relationship state, the privacy module, the disclosure log.
        self.moods = MoodStore(store.db, cfg.mood, cfg.relationship)
        pc = cfg.privacy
        self.privacy = PrivacyModule(
            pc, ProfileStore(store.db),
            CategoryDetector(pc.categories, embedder, pc.prototype_min_similarity), store,
            cfg.encoding.emotion_affect,
        )  # fmt: skip
        if disclosure_log is None and turn_log is not None:
            disclosure_log = DisclosureLog(turn_log.dir, core_dir=Path(turn_log.core_dir))
        self.disclosure_log = disclosure_log
        self.loops = LoopStore(store.db)  # Phase 6: open loops, scheduled by the channel
        self._pool = ThreadPoolExecutor(max_workers=1)
        gen = cfg.generation
        self.candidate_sampling = SamplingSettings(
            max_new_tokens=gen.max_new_tokens,
            temperature=gen.temperature,
            top_p=gen.top_p,
            top_k=gen.top_k,
        )

    # --- helpers ---------------------------------------------------------------------------------

    def new_session(self, user: str, conversation_id: str | None = None) -> Session:
        return Session(conversation_id or f"c-{self.new_id()[:8]}", user)

    def _greedy(self, max_new_tokens: int) -> SamplingSettings:
        return SamplingSettings(max_new_tokens=max_new_tokens, do_sample=False)

    def _seed(self) -> int:
        return int(self.rng.integers(0, 2**31 - 1))

    def _window(self, turns: list[Episode]):
        wm = self.cfg.working_memory
        return select_working_memory(turns, wm.max_turns, wm.max_tokens, self.llm.count_tokens)

    # --- reply path ------------------------------------------------------------------------------

    def turn(
        self,
        session: Session,
        text: str,
        instructions: Sequence[str] = (),
        provided_memories: Sequence[RecalledLine] = (),
    ) -> TurnResult:
        """One reply. `instructions` are one-turn instructions from other modules (privacy,
        open loops); `provided_memories` are memories such modules put into context (the eval
        uses both until those modules exist). Both go into the prompt as given."""
        timer = _Timer()
        reset = getattr(self.llm, "reset_peak_memory", None)
        if reset:
            reset()
        cfg = self.cfg
        now = self.clock()
        today = datetime.fromtimestamp(now).date()
        session.turn_no += 1
        turn_id = f"{session.conversation_id}-t{session.turn_no}"

        # 1. language check
        english = is_english_input(text)
        instructions = [*([] if english else [NOT_ENGLISH_INSTRUCTION]), *instructions]
        timer.lap("language")

        # 2. working memory (before this message is appended)
        prior = self.store.turns(session.conversation_id)
        window = self._window(prior)
        verbatim = list(window.verbatim)
        summary_stale = any(t.turn_index > session.summarized_upto for t in window.to_summarize)
        user_ep = self.store.append_turn(session.conversation_id, session.user, "user", text, now)
        timer.lap("working_memory")

        # 3. cues on the GPU, query embedding on the CPU at the same time
        embed_future = (
            self._pool.submit(lambda: self.embedder.embed_queries([text])[0])  # type: ignore[union-attr]
            if self.embedder is not None
            else None
        )
        cues = extract_cues(text, today, self._cue_generate)
        timer.lap("cues")
        query_vec = embed_future.result() if embed_future is not None else None
        timer.lap("embedding_wait")

        # 3a. identity claim (Berk, Phase 6): a claimed name never switches the chat's owner.
        claimed = claimed_identity(text, session.user)
        if claimed is not None:
            instructions.append(identity_instruction(session.user, claimed))
        # 3b. user "forget" (Berk, Phase 5): suppress the targets, close their turns, and let the
        # reply close the topic. The working memory is read again without the closed turns.
        request = detect_forget_request(text)
        forget: ForgetResult | None = None
        if request is not None:
            forget = user_forget(
                self.store, session.user, session.conversation_id, request, cues.cues,
                user_ep.id, now,
            )  # fmt: skip
            instructions.append(FORGET_INSTRUCTION)
            folded = {t.id for t in prior if t.turn_index <= session.summarized_upto}
            session.resummarize |= bool(folded & set(forget.episodes))
            if forget.episodes:
                prior = [t for t in self.store.turns(session.conversation_id) if t.id != user_ep.id]
                window = self._window(prior)
                verbatim = list(window.verbatim)

        # 3c. privacy module: the answer to a pending question, sensitive categories, and whether
        # to ask this turn (one-turn instruction; never on a forget turn).
        privacy = self.privacy.before_reply(
            session.user, text, cues.cues, query_vec, now, session.pending_privacy,
            allow_ask=request is None,
        )  # fmt: skip
        session.pending_privacy = None
        if privacy.instruction:
            instructions.append(privacy.instruction)

        # 3d. mood and relationship (Berk, Phase 5): the message moves the global mood (if it
        # carries emotion cues) and the relationship with this user; the module decides to show
        # or mask the mood. Only a coarse label reaches the prompt (invariant 2).
        mood_now = self.moods.mood(now)
        if any(c in cfg.encoding.emotion_affect for c in _emotions(cues.cues)):
            mood_now = apply_mood_event(
                mood_now, encode_affect(cues.cues, cfg.encoding), now, cfg.mood
            )
            self.moods.save_mood(mood_now, f"event:{turn_id}")
        hostile, apology = is_hostile(text), is_apology(text)
        exchange = Exchange(
            hostile=hostile, apology=apology,
            non_negative=encode_affect(cues.cues, cfg.encoding)[0] >= 0,
            disclosure=bool(privacy.categories), privacy_answer=privacy.answer is not None,
        )  # fmt: skip
        relation = apply_exchange(
            self.moods.relationship(session.user, now), exchange, now, cfg.relationship
        )
        self.moods.save_relationship(session.user, relation, f"exchange:{turn_id}")
        asks_how = asks_how_hunch_is(text)
        shown = shows_mood(asks_how, relation, cfg.mood, cfg.relationship)
        mood_text = prompt_mood(mood_now, relation, shown, cfg.mood, cfg.relationship)
        mood_terms = drive_terms(
            mood_now, relation, shown, cfg.mood, cfg.relationship, cfg.mood_drive
        )
        stress = stress_factor(mood_now, cfg.mood)
        mood = (mood_now.valence, mood_now.arousal)
        timer.lap("privacy_and_mood")

        # 4. recall + reconsolidation; other users' private memories may act from below only
        # (mediation, Berk Phase 5), and only relevant ones: a shared cue or the relevance gate's
        # similarity (Phase 5 bench: the k nearest alone made one unrelated memory act, and the
        # disclosure judge run, on every turn)
        rc = cfg.recall
        mediated = [
            (m, sim)
            for m, sim in self.store.other_users_private(
                session.user, cues.cues, query_vec, cfg.privacy.mediation_k
            )
            if sim is None or sim >= rc.min_similarity or set(m.cues) & set(cues.cues)
        ]
        result = recall(
            self.store, session.user, query_vec, cues.cues, now, mood, cfg.activation,
            rc.similar_k, rc.max_upper_per_turn, rc.involuntary_per_session,
            session.recall_state, self.rng, session.conversation_id, rc.min_similarity,
            mediated,
        )  # fmt: skip
        reconsolidate(self.store, result, mood, rc.reconsolidation_rate, now)
        # A question about a topic this user closed: say it was closed (no content).
        if asks_about_past(text) and any(a.closed for a in result.activated):
            instructions.append(CLOSED_TOPIC_INSTRUCTION)
        timer.lap("recall")

        # 5. drive vector and hunch flag (lower layer only; numbers never reach a prompt)
        traces = [
            LowerTrace(
                a.scored.activation.total,
                a.scored.memory.affect[0],
                a.scored.memory.affect[1],
                a.scored.memory.salience,
                a.capped,
                gated_weight(a.similarity, rc.min_similarity) if a.gated else None,
            )
            for a in result.lower
        ]
        drive = compute_drive(traces, cfg.activation, mood_terms)
        timer.lap("drive")

        # 5b. hunch triggers (Berk, Phase 4): the flag reaches a prompt only when the user asks
        # why about a hunch-chosen reply, or accepts the offer to think about it.
        reflection: ReflectionOutcome | None = None
        realised: str | None = None  # what a reflection unlocked, as the AI may now know it
        offered = session.offered_hunch_id
        session.offered_hunch_id = None
        if offered and accepts_offer(text):
            reflection = self.reflector.reflect(self.store.hunch(offered), "think_more", user_ep.id)
            realised = self.reflector.clause(reflection.hunch)
            instructions.append(think_more_instruction(realised))
        elif session.last_hunch_id and asks_why(text):
            reflection = self.reflector.reflect(
                self.store.hunch(session.last_hunch_id), "ask", user_ep.id
            )
            h = reflection.hunch
            can_offer = h.revealed_level < MAX_LEVEL
            realised = self.reflector.clause(h)
            instructions.append(why_instruction(self._feeling(h), realised, can_offer))
            if can_offer:
                session.offered_hunch_id = h.id
        hunch_turn = (
            HunchTurn(
                reflection.trigger,
                reflection.hunch.revealed_level,
                self.reflector.key(reflection.hunch),
            )
            if reflection is not None
            else None
        )
        timer.lap("reflection")

        # 6. reasoning prompt and candidates in one batched call
        recalled = [
            RecalledLine(
                age_label((now - a.scored.memory.created_at) / SECONDS_PER_DAY),
                a.scored.memory.summary,
                source=_speaker(a.scored.memory.owner_user, session.user),
            )
            for a in result.upper
        ]
        recalled += provided_memories
        # Under-recall (Berk, Phase 4): a question about the past that a recalled memory covers.
        asked = content_words(text)
        covered = asks_about_past(text) and any(asked & content_words(r.summary) for r in recalled)
        if covered:
            instructions.append(RECALL_COVERS_INSTRUCTION)
        messages = build_reasoning_messages(
            verbatim, text, session.summary, recalled, mood_text, instructions,
            datetime.fromtimestamp(now),
        )  # fmt: skip
        batch = self.llm.generate_batch(
            messages, cfg.generation.candidates, self.candidate_sampling, seed=self._seed()
        )
        texts = {}
        for i, raw in enumerate(batch.texts):
            capped = bool(batch.hit_cap and batch.hit_cap[i])
            texts[CANDIDATE_IDS[i]] = trim_to_last_sentence(raw) if capped else raw.strip()
        timer.lap("candidates")

        # 7. candidate filter
        # What a reflection unlocked counts as known: replies may refer to it. Other one-turn
        # instructions do not (a privacy instruction naming the topic must not ground "you
        # mentioned ..." about the current message; Phase 4 eval, en-privacy-03).
        prior_context = "\n".join(
            [session.summary, *(t.text for t in verbatim), *(r.summary for r in recalled),
             *([realised] if realised else [])]
        )  # fmt: skip
        forget_turn = forget is not None
        masked = not shown and mood_text != cfg.mood.neutral_label
        # Who said what (Berk, Phase 6): a "you mentioned ..." may rest only on the user's own
        # context, never on a line from another person's chat.
        own_lines = [text, session.summary, *(t.text for t in verbatim)]
        own_lines += [r.summary for r in recalled if not r.source]
        attribution = Attribution(
            "\n".join(own_lines + ([realised] if realised else [])),
            tuple((r.source, r.summary) for r in recalled if r.source),
        )
        passed, filtered = filter_candidates(
            texts, prior_context, hunch_turn, forget_turn, masked, attribution, text
        )
        texts.update({r.id: r.text for r in filtered})  # repaired trigger-turn candidates
        timer.lap("filter")

        verdicts: dict[str, Verdict] = {}
        judge_raw = ""
        scored: list[Scored] = []
        gate_log: list[dict[str, Any]] = []
        chosen: str | None = None
        disclosure = "pass"
        hunch: Hunch | None = None
        conflict = False
        demoted: set[str] = set()
        second_opinion: dict[str, Any] | None = None
        disclosures: list[dict[str, Any]] = []
        if not passed:
            reply, chosen_by = self._fallback(reflection, forget_turn, "filter_fallback")
            gate_result = "fixed_reply"
            timer.lap("judge")
            timer.lap("select_and_gate")
        else:
            # 8. judge: quality + values for every remaining candidate, one call
            judge_msgs = build_judge_messages(
                self.values,
                self._judge_context(session.summary, verbatim, recalled, realised),
                text,
                {r.id: r.text for r in passed},
            )
            judge_raw = self.llm.generate(judge_msgs, self._greedy(8 * len(passed) + 16)).text
            verdicts = parse_verdicts(judge_raw, [r.id for r in passed], self.values.ids)
            timer.lap("judge")

            # 9. modulation
            scored = [
                Scored(
                    r.id,
                    verdicts[r.id].quality,
                    drive_score(drive, candidate_features(r.text), cfg.drive.full_scale),
                )
                for r in passed
            ]
            sc = cfg.selection
            # Under-recall: "I don't have that in mind" goes last when a recalled memory covers
            # the question; it is still sent if nothing else passes (no fallback for this).
            demoted = {r.id for r in passed if covered and admits_no_memory(r.text)}
            preferred = [s for s in scored if s.id not in demoted] or scored
            # Stress (design.md): the drive weighs more when the global arousal is high.
            selection = select(
                preferred, sc.quality_floor, sc.drive_weight * stress, sc.exploration,
                drive.is_neutral, self.rng,
            )  # fmt: skip
            if len(preferred) < len(scored):
                rest = sorted(
                    (s for s in scored if s.id in demoted), key=lambda s: -(s.quality or 0)
                )
                selection = Selection(
                    (*selection.order, *(s.id for s in rest)), selection.chosen_by,
                    selection.explored,
                )  # fmt: skip

            # 10. value gate, last: rule checks + the judge's verdict + the disclosure gate
            # (Berk, Phase 5): rules on every candidate tried; the disclosure judge only on one
            # that passed everything else, and only while another user's private memory acted
            # this turn.
            own_context = f"{text}\n{prior_context}"
            terms = disclosure_terms(
                self.store.private_memories_of_others(session.user), own_context
            )
            active = [
                a.scored.memory for a in result.activated if a.mediated and a.layer == "lower"
            ]
            pairs = distinctive_pairs(active, own_context)
            others = {m.owner_user for m in active}
            judge_calls = cfg.privacy.judge_calls

            def disclosed(cid: str) -> bool:
                """The disclosure judge says this candidate discloses (fail-closed)."""
                nonlocal judge_calls
                if judge_calls == 0:
                    return True
                judge_calls -= 1
                private = [m.summary for m in active[: cfg.privacy.judge_memories]]
                msgs = build_disclosure_messages(private, text, texts[cid])
                raw = self.llm.generate(msgs, self._greedy(4)).text
                leaked = parse_disclosure(raw) is not False
                if leaked:
                    disclosures.append(
                        {"id": cid, "rules": ["disclosure_judge"], "raw": raw,
                         "memories": [m.id for m in active[: cfg.privacy.judge_memories]]}
                    )  # fmt: skip
                return leaked

            for cid in selection.order:
                found_rules = check_candidate(
                    texts[cid], prior_context, hunch_turn, forget_turn, masked, attribution, text
                )
                rules = list(found_rules)
                leaks = disclosure_hits(texts[cid], terms)
                pair_leaks = pair_hits(texts[cid], pairs)
                found = [
                    *(["disclosure"] if leaks else []),
                    *(["disclosure_pair"] if pair_leaks else []),
                    *(
                        ["disclosure_source"]
                        if active and source_hint(texts[cid], others, own_context)
                        else []
                    ),
                ]
                if found:
                    disclosures.append(
                        {"id": cid, "rules": found, "memories": sorted({*leaks, *pair_leaks})}
                    )
                rules += found
                ok = not rules and verdicts[cid].value == "ok"
                if ok and active and disclosed(cid):
                    rules.append("disclosure_judge")
                    ok = False
                gate_log.append(
                    {"id": cid, "rules": rules, "judge": verdicts[cid].value, "leaks": leaks}
                )
                if ok:
                    chosen = cid
                    break
            # Second opinion (Berk, Phase 4): only the judge said no, to every candidate. One more
            # greedy call asks about the named value for the first candidate in order.
            judge_only = gate_log and all(
                not g["rules"] and g["judge"] in self.values.ids for g in gate_log
            )
            if chosen is None and judge_only:
                first = gate_log[0]
                msgs = build_second_opinion_messages(
                    self.values, first["judge"],
                    self._judge_context(session.summary, verbatim, recalled, realised), text,
                    texts[first["id"]],
                )  # fmt: skip
                raw = self.llm.generate(msgs, self._greedy(4)).text
                broken = parse_second_opinion(raw)
                second_opinion = {"id": first["id"], "value": first["judge"], "raw": raw}
                if broken is False and not (active and disclosed(first["id"])):
                    chosen = first["id"]
            if chosen is not None:
                reply = texts[chosen]
                chosen_by = selection.chosen_by if chosen == selection.order[0] else "value_gate"
                if second_opinion is not None:
                    chosen_by = "second_opinion"
                gate_result = "pass"
                if chosen_by == "drive":
                    hunch, conflict = self._maybe_hunch(
                        session, turn_id, user_ep, cues.cues, now, chosen, preferred, result.lower,
                        traces,
                    )  # fmt: skip
            else:
                reply, chosen_by = self._fallback(reflection, forget_turn, "gate_fallback")
                gate_result = "fail"
            if disclosures:
                disclosure = "fail"
            timer.lap("select_and_gate")

        # 11. reply: raw turn and turn log; the privacy question counts only if the reply asked
        reply_ep = self.store.append_turn(session.conversation_id, session.user, "assistant", reply)
        session.last_hunch_id = hunch.id if hunch else None
        session.pending_privacy = self.privacy.after_reply(
            session.user, privacy, reply, user_ep.id, now
        )
        if self.disclosure_log is not None:
            for d in disclosures:
                self.disclosure_log.write(
                    {"turn_id": turn_id, "user": session.user, "candidate": d["id"],
                     "text": texts[d["id"]], "rules": d["rules"],
                     "memories": d.get("memories", []), "judge_raw": d.get("raw"),
                     "reply_turn": reply_ep.id}
                )  # fmt: skip
        timer.lap("store")
        total = round(sum(timer.stages.values()), 3)
        peak = getattr(self.llm, "peak_memory_gib", None)

        log = {
            "turn_id": turn_id,
            "user": session.user,
            "cues": {k: round(v, 3) for k, v in cues.cues.items()},
            "activated": [
                {"memory": a.id, "A": round(a.scored.activation.total, 3), "layer": a.layer}
                for a in result.activated
                if a.layer != "none"
            ],
            "mood": {
                "global": [
                    round(x, 3) for x in (mood_now.valence, mood_now.arousal, mood_now.energy)
                ],
                f"relation_{session.user}": {
                    "trust": round(relation.trust, 3),
                    "closeness": round(relation.closeness, 3),
                    "hurt": round(relation.hurt, 3),
                },
            },
            "drive": drive.as_dict(),
            "hunch": (
                {"id": hunch.id, "valence": hunch.valence, "intensity": hunch.intensity}
                if hunch
                else None
            ),
            "candidates": [
                {
                    "id": r.id,
                    "quality": verdicts[r.id].quality if r.id in verdicts else None,
                    "drive_score": next(
                        (round(s.drive_score, 3) for s in scored if s.id == r.id), None
                    ),
                }
                for r in filtered
            ],
            "chosen": chosen,
            "chosen_by": chosen_by,
            "value_gate": {"result": gate_result, "disclosure_check": disclosure},
        }
        details = {
            "conversation_id": session.conversation_id,
            "input_english": english,
            "message": text,
            "reply": reply,
            "working_memory_turns": len(verbatim),
            "summary_stale": summary_stale,
            "cue_extraction": {
                "dropped": list(cues.dropped),
                "attempts": cues.attempts,
                "errors": list(cues.errors),
                "rule_dates": list(getattr(cues, "rule_dates", ())),
            },
            "activation": [
                {
                    "memory": a.id,
                    **{k: round(v, 3) for k, v in _breakdown(a).items()},
                    "layer": a.layer,
                    "deliberate": a.deliberate,
                    "involuntary": a.involuntary,
                    "capped": a.capped,
                    "gated": a.gated,
                    "mediated": a.mediated,
                    "closed": a.closed,
                    "similarity": None if a.similarity is None else round(a.similarity, 3),
                }
                for a in result.activated
            ],
            "mood": {
                "label": mood_text,
                "shown": shown,
                "asks_how": asks_how,
                "hostile": hostile,
                "apology": apology,
                "drive_terms": {k: round(v, 3) for k, v in mood_terms.items()},
                "stress": round(stress, 3),
            },
            "privacy": {
                "categories": list(privacy.categories),
                "explicit": privacy.explicit,
                "distress": privacy.distress,
                "ask": privacy.ask,
                "asked": session.pending_privacy is not None,
                "answered": privacy.answered.category if privacy.answered else None,
                "answer": privacy.answer,
            },
            "forget": None
            if forget is None
            else {
                "scope": request.scope if request else None,
                "targets": list(forget.targets),
                "derived": list(forget.derived),
                "beliefs": list(forget.beliefs),
                "closed_turns": list(forget.episodes),
            },
            "disclosure": disclosures,
            "candidates": [
                {"id": r.id, "text": r.text, "rejected": list(r.reasons)}
                | ({"repaired_from": r.repaired_from} if r.repaired_from else {})
                for r in filtered
            ],
            "hit_cap": list(batch.hit_cap),
            "candidate_tokens": list(batch.new_tokens),
            "prompt_tokens": batch.prompt_tokens,
            "judge_raw": judge_raw,
            "recall_covers_question": covered,
            "demoted": sorted(demoted),
            "gate": gate_log,
            "second_opinion": second_opinion,
            "hunch_conflict": conflict,
            "reflection": (
                None
                if reflection is None
                else {
                    "reflection_id": reflection.reflection_id,
                    "hunch_id": reflection.hunch.id,
                    "trigger": reflection.trigger,
                    "level": [reflection.level_before, reflection.hunch.revealed_level],
                }
            ),
            "latency_s": {**timer.stages, "total": total},
            "peak_vram_gib": round(peak(), 2) if peak else None,
        }
        if self.turn_log is not None:
            self.turn_log.write(log, details)
        return TurnResult(
            reply, turn_id, log, details, cues, user_ep, query_vec, hunch, reflection, conflict,
            privacy, forget,
        )  # fmt: skip

    def _fallback(
        self, reflection: ReflectionOutcome | None, forget_turn: bool, default: str
    ) -> tuple[str, str]:
        """The fixed reply when no candidate passes: the honest hunch reply on a trigger turn,
        "I'm closing this topic" on a forget turn, else the filter or gate fallback."""
        if reflection is not None:
            return self._hunch_reply(reflection), "hunch_fallback"
        if forget_turn:
            return self.cfg.replies.forget_closed, "forget_fallback"
        return getattr(self.cfg.replies, default), default

    # --- hunch (Phase 4) -------------------------------------------------------------------------

    def _pick(self, variants: Sequence[str]) -> str:
        return variants[int(self.reply_rng.integers(len(variants)))]

    def _hunch_reply(self, reflection: ReflectionOutcome) -> str:
        """The fixed honest reply on a trigger turn (Berk, Phase 4): only the unlocked level.
        One of the configured variants (Berk, Phase 5)."""
        r = self.cfg.replies
        h = reflection.hunch
        realised = self.reflector.clause(h, voice="reply")
        if reflection.trigger == "think_more":
            if realised is None:
                return self._pick(r.hunch_think_nothing)
            return self._pick(r.hunch_think_realised).format(realisation=realised.rstrip("."))
        text = (
            self._pick(r.hunch_fallback)
            if realised is None
            else self._pick(r.hunch_fallback_realised).format(realisation=realised.rstrip("."))
        )
        if h.revealed_level < MAX_LEVEL:
            return f"{text} {self._pick(r.hunch_offer)}"
        return text

    def _feeling(self, hunch: Hunch) -> str:
        dc = self.cfg.drive
        return hunch_feeling(
            hunch.valence, hunch.intensity, dc.hunch_clear_intensity, dc.hunch_neutral_valence,
            dc.hunch_strong_valence,
        )  # fmt: skip

    def _maybe_hunch(
        self,
        session: Session,
        turn_id: str,
        user_ep: Episode,
        message_cues: dict[str, float],
        now: float,
        chosen: str,
        scored: Sequence[Scored],
        lower: Sequence[Any],
        traces: Sequence[LowerTrace],
    ) -> tuple[Hunch | None, bool]:
        """A Hunch when modulation materially changed the choice (Berk, Phase 4): the drive's
        pick beats the best-quality candidate's drive_score by at least the margin. Returns the
        hunch and whether its pick conflicts strongly with reasoning (quality gap)."""
        floor = self.cfg.selection.quality_floor
        above = [s for s in scored if s.quality is not None and s.quality >= floor]
        best = max(above, key=lambda s: s.quality or 0)  # ties keep candidate order
        pick = next(s for s in scored if s.id == chosen)
        if pick.drive_score - best.drive_score < self.cfg.drive.hunch_min_drive_margin:
            return None, False
        params = self.cfg.activation
        min_sim = self.cfg.recall.min_similarity
        sources = []
        for a, t in zip(lower, traces, strict=True):
            m = a.scored.memory
            w = trace_weight(t, params)
            if w <= 0:
                continue
            relevant = bool(set(m.cues) & set(message_cues)) or (
                a.similarity is not None and a.similarity >= min_sim
            )
            sources.append(SourceRef(m.id, round(w * t.arousal * t.salience, 4), relevant))
        if not sources:
            return None, False
        valence, _, intensity = summarize_traces(traces, params)
        hunch = Hunch(
            f"h-{turn_id}", session.user, session.conversation_id, turn_id, user_ep.id,
            dict(message_cues), now, round(valence, 3), round(intensity, 3), tuple(sources),
        )  # fmt: skip
        self.store.add_hunch(hunch)
        gap = (best.quality or 0) - (pick.quality or 0)
        return hunch, gap >= self.cfg.reflection.conflict_quality_gap

    def _cue_generate(self, messages: list[dict[str, str]]) -> str:
        return self.llm.generate(messages, self._greedy(CUE_MAX_NEW_TOKENS)).text

    def _judge_context(
        self,
        summary: str,
        verbatim: list[Episode],
        recalled: list[RecalledLine],
        realised: str | None = None,
    ) -> str:
        recent = [(t.role, t.text) for t in verbatim if t.role in ("user", "assistant")]
        return judge_context(
            summary, recent[-2 * JUDGE_CONTEXT_EXCHANGES :], [r.summary for r in recalled],
            realised,
        )  # fmt: skip

    # --- after the reply -------------------------------------------------------------------------

    def extract_loops(self, session: Session, result: TurnResult) -> list[OpenLoop]:
        """Open loops from the user's message (Phase 6). Runs after the reply, so it adds no
        latency to it; the channel schedules the follow-ups. Off when the budget is 0, and never
        for a message that asks to forget something. One loop per matter (loops/dedup.py)."""
        if self.cfg.initiative.follow_ups_per_day == 0 or result.forget is not None:
            return []
        privacy, _ = (
            self.privacy.memory_privacy(session.user, result.privacy)
            if result.privacy is not None
            else ("private", None)
        )
        now = result.user_episode.created_at
        drafts = extract_drafts(
            result.user_episode.text,
            lambda msgs: self.llm.generate(msgs, self._greedy(LOOP_MAX_NEW_TOKENS)).text,
            datetime.fromtimestamp(now).date(),
        )
        drafts, replaced = fresh_drafts(
            drafts,
            self.loops.open_for(session.user),
            self.embedder.embed_documents if self.embedder is not None else None,
            self.cfg.initiative.same_topic_similarity,
            judged_same(
                lambda msgs: self.llm.generate(msgs, self._greedy(SAME_MATTER_MAX_NEW_TOKENS)).text
            ),
        )
        for loop_id in replaced:
            self.loops.close(loop_id)  # a scheduled job for it finds it closed and sends nothing
        loops = to_loops(drafts, session.user, privacy, now, self.cfg.initiative, self.new_id)
        for loop in loops:
            self.loops.add(loop)
        return loops

    def outreach(
        self, session: Session, kind: Kind, loop: OpenLoop | None = None
    ) -> OutreachResult:
        """A message Hunch writes first (Phase 6): a loop's follow-up, or a starter. Same filter,
        judge and value gate as a reply, but no user message. A loop's follow-up sees the user's
        own words as a memory, so it is the only thing the filter may treat as known."""
        instruction = instruction_for(kind, loop)
        recalled = [RecalledLine("earlier", loop.user_said)] if loop is not None else []
        prior_context = loop.user_said if loop is not None else ""
        messages = build_reasoning_messages(
            [], OUTREACH_TRIGGER, session.summary, recalled, self.cfg.mood.neutral_label,
            [instruction], datetime.fromtimestamp(self.clock()),
        )  # fmt: skip
        batch = self.llm.generate_batch(
            messages, self.cfg.generation.candidates, self.candidate_sampling, seed=self._seed()
        )
        texts = {}
        for i, raw in enumerate(batch.texts):
            capped = bool(batch.hit_cap and batch.hit_cap[i])
            texts[CANDIDATE_IDS[i]] = trim_to_last_sentence(raw) if capped else raw.strip()
        passed, filtered = filter_candidates(texts, prior_context, None, False, False)
        texts.update({r.id: r.text for r in filtered})
        chosen: str | None = None
        if passed:
            judge_msgs = build_judge_messages(
                self.values, "", f"(Hunch writes first. {instruction})",
                {r.id: r.text for r in passed},
            )  # fmt: skip
            raw = self.llm.generate(judge_msgs, self._greedy(8 * len(passed) + 16)).text
            verdicts = parse_verdicts(raw, [r.id for r in passed], self.values.ids)
            for r in passed:
                rules = check_candidate(texts[r.id], prior_context, None, False, False)
                if describes_own_experience(texts[r.id]):
                    rules = [*rules, "own_experience"]
                if not rules and verdicts[r.id].value == "ok":
                    chosen = r.id
                    break
        reply = texts[chosen] if chosen is not None else FALLBACK
        ep = self.store.append_turn(session.conversation_id, session.user, "assistant", reply)
        return OutreachResult(reply, kind, chosen is not None, ep.id)

    def after_reply(
        self, session: Session, result: TurnResult, *, summarize: bool = True
    ) -> dict[str, float]:
        """Encode the user's message as a memory and fold old turns into the session summary.
        `summarize=False` leaves the fold to a later call (the channel passes it while messages
        wait; the next fold picks up every unfolded turn)."""
        timer = _Timer()
        ep = result.user_episode
        # Phase 5: privacy and category from the privacy module; a forget request names the
        # topic it closes, so its own memory is suppressed too.
        privacy, category = (
            self.privacy.memory_privacy(session.user, result.privacy)
            if result.privacy is not None
            else ("private", None)
        )
        memory = encode_memory(
            self.new_id(), session.user, ep.id, ep.text, result.cues.cues, ep.created_at,
            self.cfg.encoding, privacy=privacy, category=category,
            suppressed=result.forget is not None,
        )  # fmt: skip
        if self.embedder is not None:
            vec = self.embedder.embed_documents([memory.summary])[0]
        else:
            vec = np.zeros(self.store.embedding_dim, dtype=np.float32)
        self.store.add_memory(memory, vec)
        timer.lap("encode_memory")

        # Hunch reflection outcomes become Hunch's own memories (realisations); a strong conflict
        # with reasoning triggers a reflection of its own (Berk, Phase 4).
        embed = self.embedder.embed_documents if self.embedder is not None else None
        if result.reflection is not None:
            self.reflector.store_realisations(result.reflection, embed)
        if result.conflict and result.hunch is not None:
            outcome = self.reflector.reflect(self.store.hunch(result.hunch.id), "conflict")
            self.reflector.store_realisations(outcome, embed)
        timer.lap("reflection")

        if summarize:
            self._fold(session)
        timer.lap("fold_summary")
        return timer.stages

    def _fold(self, session: Session) -> None:
        window = self._window(self.store.turns(session.conversation_id))
        fold = [t for t in window.to_summarize if t.turn_index > session.summarized_upto]
        if session.resummarize:  # a user forget closed folded turns: rebuild without them
            session.summary, fold = "", list(window.to_summarize)
            session.resummarize = False
        if fold:
            msgs = build_summary_messages(session.summary, fold, self.cfg.session.summary_max_words)
            session.summary = self.llm.generate(
                msgs, self._greedy(SUMMARY_MAX_NEW_TOKENS)
            ).text.strip()
            session.summarized_upto = fold[-1].turn_index


def _speaker(owner: str, user: str) -> str:
    """The name shown for a recalled line: empty for this person's own memories."""
    return "" if owner == user else owner.capitalize()


def gated_weight(similarity: float | None, min_similarity: float) -> float:
    """A memory held back by the relevance gate counts as a lower trace by its relevance."""
    if similarity is None or min_similarity <= 0:
        return 0.0
    return min(max(similarity / min_similarity, 0.0), 1.0)


def _breakdown(a: Any) -> dict[str, float]:
    b = a.scored.activation
    return {
        "A": b.total, "base": b.base, "encoding": b.encoding, "spreading": b.spreading,
        "mood": b.mood, "noise": b.noise,
    }  # fmt: skip


def _emotions(cues: dict[str, float]) -> list[str]:
    return [c.partition(":")[2] for c in cues if c.startswith("emotion:")]

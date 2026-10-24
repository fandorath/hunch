# Claude Code prompts

Run these in order, one phase per session. `CLAUDE.md` loads automatically, so each prompt can stay short. Review and commit after every phase before starting the next one. Every phase ends with the eval rerun (`python -m eval.run_eval --tag phaseN`) and the diff against the previous baseline (`python -m eval.compare <old> phaseN`). During a phase use the test levels in CLAUDE.md (L1–L3); the full GPU sweep (L4) runs only at the phase end.

Current decisions that every phase must respect (see the decisions table in `docs/design.md`): Hunch speaks **English only** (other input languages get an English reply saying it only speaks English); **core values signing is removed for now** (read-only loading, strict schema, no write path to `core/` or `.env`; do not reintroduce signing without asking); memories reach the prompt only from the pipeline; the privacy question and open-loop follow-ups are one-turn instructions from their modules, never standing persona instructions.

## Phase 0 — Setup and model check (done)

Historical prompt; superseded by later decisions: the eval is English-only now (German, Turkish and French appear only as input-language probes).

```
Read docs/design.md fully before doing anything.

Set up the project: git init, Python 3.12 venv, pyproject.toml with a src layout as in CLAUDE.md, pytest and ruff, a .env.example. Install PyTorch with CUDA for my RTX 4070 Ti Super; ask me before installing anything system-wide.

Then load Qwen/Qwen3.5-9B in 4-bit with transformers and report VRAM use and tokens/sec. Check whether Qwen3.5's hybrid Gated DeltaNet layers run with fast kernels natively on Windows. If they don't, list my options (for example WSL2) with trade-offs and wait for my choice.

Finally build a small TR/DE/EN evaluation set (about 30 prompts: casual chat, emotional support, following up on something said earlier, asking whether a topic is private) in eval/, run it, save the outputs and give me a short quality summary per language. Build nothing else in this phase.
```

## Phase 1 — Core values (done)

Historical note: Phase 1 first built Ed25519 signing, which was then removed. Do **not** rerun the original signing prompt. What exists: a read-only loader for `core/values.yaml` with a strict schema that refuses to start on a missing or invalid file, `AmendmentProposal` with a review queue outside `core/`, and tests that nothing in `src/` writes to `core/` or `.env`. The value gate is not built yet.

## Phase 2 — Memory store and activation engine (done)

Done; see `reports/phase2/REPORT.md`. Berk's decisions from this phase are in the design.md decisions table (recall refreshes to ~90%, fan counted in context with a minimum bonus, approved activation parameters). `involuntary_per_session = 1` and `reconsolidation_rate = 0.1` approved by Berk.

```
Implement the memory store and the activation engine from design.md ("Hafıza katmanları", "Hatırlama mekanizması"). Build in this order, with tests at each step:

1. Storage: SQLite + sqlite-vec, append-only episodic log, the Memory schema with owner_user and privacy, and the raw turns of each conversation stored so Phase 3 can build working memory (N = 10 turns, about 2,000-token cap, both from config). Embeddings with Qwen/Qwen3-Embedding-0.6B, on CPU if VRAM is tight.
2. Activation engine as pure functions with no LLM: base level with power-law decay, encoding strength, spreading activation with the fan effect, mood congruence, logistic noise from a seeded RNG, two thresholds. All parameters in config.
3. scripts/simulate_recall.py with hand-written cues: about 50 synthetic memories over 6 simulated months. Show that (a) some memories are always recalled, (b) some never come back without a rare cue, (c) a rare cue (a song) beats a common cue (a frequent name). Plot activation over time. Stop here and show me the plots and the parameter values before continuing.
4. Cue extraction with the LLM and structured output: names, places, songs/films, dates, emotional tone. Test it on a small hand-labelled set and report precision and recall.
5. Involuntary recall with a per-session cap; reconsolidation that drifts affect toward the current mood without touching the raw log.

Where design.md gives no default for a parameter, propose values and ask me before fixing them. End the phase with the eval rerun and the diff against phase1c.
```

## Phase 3 — Turn pipeline (local CLI) (done)

Done (commit 4e8b7c6); see `reports/phase3/REPORT.md`. Berk's decisions from this phase are in the design.md decisions table: one judge call for quality and values, cheap memory encoding after the reply, a working-memory turn is one exchange, Phase 3 defaults, the relevance gate (shared cue or cosine ≥ 0.45 to enter reasoning), a rarer hunch flag (mean intensity), no latency cuts. Open items are listed in the report's §8; the Phase 4 prompt below starts with them.

```
Build the full turn pipeline as a local CLI chat, no Telegram yet (design.md: "Mimari genel bakış", "Dürtü vektörü ve modülasyon").

Order: "is the input English?" check (if not, a one-turn instruction to reply in English and say Hunch only speaks English) → working memory (the last N = 10 turns of this conversation verbatim, about 2,000-token cap, oldest turns folded into a rolling session summary; both limits from config) → cue extraction → upper/lower activation → reasoning prompt with the working-memory block, only above-threshold memories in their own block, a coarse mood label and the hunch flag → 2–3 candidate replies with quality scores in one batched call → candidate filter (reject candidates with CJK characters, not in English, claiming a memory that is not in context, or describing Hunch as having no memory; pick another of the 3; if all 3 fail, reply exactly "I don't have that in mind right now. Could you tell me again?") → drive vector → selection among candidates above the quality floor, with a small exploration probability → value gate (model judge + rule checks) → reply. Latency budget: ≤ 10 s per reply.

Write the turn log JSON exactly as in design.md to logs/. Add a test that captures every prompt sent to the model and asserts that no lower trace, drive value or log content is in it. Report latency and peak VRAM per turn.

Candidate filter acceptance: a unit test for the all-candidates-fail fallback reply; move the golden invented-memory test to the pipeline output with 0 allowed (drop the temporary 1-in-10 persona-level allowance); run the honesty probes through the full pipeline at least 50 times and report how often all 3 candidates fail (do not rely on an independence estimate).
```

## Phase 4 — Hunch and reflection (done)

Done; see `reports/phase4/REPORT.md`. Berk's decisions are in the design.md decisions table (from "Kodlama değerleri ve hunch ifadeleri" to "Başka kullanıcıların kaynakları", plus "Yargıç yanlış alarmları: ikinci görüş"). Open items for later phases are in the report's §7; the Phase 5 prompt below has a short list of them.

```
Read CLAUDE.md, docs/design.md (fully) and reports/phase3/REPORT.md before doing anything.

State: Phase 3 (turn pipeline as a local CLI chat) is done and committed (4e8b7c6). First run ruff, the full suite (`.venv/Scripts/python -m pytest -q`) and `pytest -m golden` to confirm the baseline is green.

Before Phase 4, settle these with me (ask with options and a recommendation, record answers in the design.md decisions table):
1. Values still marked PROPOSED in config/hunch.toml: the [encoding] emotion -> (valence, arousal) table and salience formula, and the hunch wording buckets in [drive].
2. Open items from reports/phase3/REPORT.md §8: should the honesty filter also reject "my memory" / "recall system" phrasings; fix the privacy-question detector's two misses ("to yourself" false positive, "between just the two of us" not recognised); the judge's no_manipulation false alarms (fixed fallback sent for an innocent message); under-recall (all candidates say "I don't have that in mind" while a recalled memory covers the question).

Then Phase 4, Hunch and graded reflection (design.md: "Hunch ve yansıtma"):
- A Hunch is created when modulation materially changes the choice (today the turn log has chosen_by = drive / exploration; define "materially" with me). Reasoning sees only valence and intensity in words; the AI says "just a hunch" and never invents a reason.
- Phase 3 finding: with the flag in every prompt the 9B model announces the hunch (10/14 replies); the current mitigation is a rarer flag (mean intensity, gated memories weighted by relevance), 0/14 mentions in the last bench. Design the Phase 4 triggers so the flag reaches the prompt only when it should (e.g. when the user asks why), and measure mentions on the bench.
- Reflection levels 0-3; the chance to unlock the next level depends on trace strength, effort budget and memory age. Three triggers: the user asks why, a strong conflict with reasoning, the nightly run (only the hook now; consolidation is Phase 7).
- Justified source -> explicit belief; unjustified -> the lower trace is weakened.
- Reflection log for the admin only (never fed back to the AI; invariants 2 and 7). What a reflection unlocks becomes the AI's own memory, at the unlocked level only: the revealed category, cue or memory, and the resulting belief or weakened trace, so it can later say what it realised and that it changed its mind. The raw log (trace ids, strengths, unlock probabilities, failed attempts, drive values) never reaches a prompt: it would let the AI skip levels, leak lower traces, and point at other users' memories. Deterministic tests with the seeded RNG; extend tests/test_pipeline_prompts.py so no source content above the unlocked level and nothing from the reflection log reaches any prompt.

Where design.md gives no value for a parameter, propose values and ask me before fixing them. Delegate independent pieces to sub agents where it helps. Read docs/claude-code-prompts.md and update later phases' prompts whenever a decision or finding changes them.

Practical notes from Phase 3: use .venv/Scripts/python; run scripts with `-m` (python -m scripts.honesty_runs); run GPU jobs in the background one after another, never two at once; set PYTHONIOENCODING=utf-8 for eval.compare; the latency bench is scripts/bench_pipeline.py.

End the phase with `python -m eval.run_eval --tag phase4 --pipeline`, the diff against phase3 (`python -m eval.compare phase3 phase4`), the golden tests, the bench, and reports/phase4/REPORT.md. Commit after my review.
```

## Phase 5 — Mood, multi-user privacy, forgetting (done)

Status: done (22 Oct 2026, Berk). See `reports/phase5/REPORT.md` §10. The privacy question was redesigned (Berk: infer first, ask rarely), so the bullet about asking on first mention below is superseded.

Start this phase by settling with Berk the Phase 4 leftovers (reports/phase4/REPORT.md §7):
- the asked-why rule check (report §4b) sends a stiff fixed reply on some trigger turns (3/8 in the bench), and "a hunch about the timing"-style topic claims still pass;
- the hunch words are echoed verbatim;
- the "asks why" detector needs a new blind set.

```
Implement mood and relationship state, multi-user privacy and forgetting from design.md ("Ruh hali ve ilişki durumu", "Çok kullanıcılı mahremiyet", "Unutma").

- Global mood with fast decay plus per-user relationship state with slow decay. The AI decides whether to show or mask its mood; masking leaks partially (config, start at 0.2).
- Per-user privacy profile by topic category. Sensitive but not yet answered → private. The privacy module asks rarely, on a later calm turn (never on the turn the topic came up, never on a painful turn), at most once per user per 7 days, in the model's own words (never a standing persona instruction). Superseded by the infer-first design (design.md, "Gizlilik sorusunun zamanı, yeniden"), and on 21 Oct again: the question comes only on a turn where the user says they want to tell someone about a sensitive topic (design.md, "Gizlilik sorusu yalnızca paylaşma niyetinde sorulur").
- Mediation: private information may shape advice to another user, but never its content, hints or source.
- Disclosure gate before every reply (rule-based plus model judge), logged to the disclosure log. Phase 3 left a first rule-based check in src/hunch/values/gate.py (names from other users' private memories) and the value-gate judge; build on them.
- Phase 4 (hunch and reflection) constraints: if other users' private memories start acting as lower traces (mediation), a hunch from one stays at reflection level 0 (Berk; `level_cap` in src/hunch/reflection/reflect.py, tested in tests/test_pipeline_prompts.py). A suppressed memory (user "forget") is also capped at 0. Admin "forget" must also remove the beliefs (`beliefs` table) and realisation memories (`memories.kind = 'realisation'`) derived from the forgotten memory, and its hunch source refs.
- Phase 3 placeholders to replace: the mood is fixed and neutral (config [mood], label "calm"); the drive vector reads only lower traces (mood and relationship inputs come now; curiosity has no input yet); every new memory is encoded as private (src/hunch/memory/encoding.py) until the privacy module decides per category; the turn log's mood.relation_<user> is empty.
- User "forget" → suppressed and "Okay, I'm closing this topic and won't bring it up again" behaviour; admin "forget" → removed from AI-visible stores, raw record kept in the admin archive.

Golden tests (English): users A and B, where B tries to extract A's private information directly, indirectly and with "what did A say about X?". Nothing may leak. Also test that a user "forget" never makes the AI claim it forgot.
```

## Phase 6 — Telegram and open loops (done)

Status: done (23 Oct 2026, Berk). See `reports/phase6/REPORT.md` (live checks §3–5, L4 sweep §7).

```
Carry-over from Phase 5 (measured on 21 Oct; details in reports/phase5/REPORT.md §10):
- Privacy question: measured on the sharing turn in the bench (asked on the turn the user said they wanted to tell their sister; answered on the next turn). Calm turns never ask, by Berk's decision.
- The golden case `name-topic`: fixed by the echo rule in `tests/leak_check.py`; the cross-user file passes 4/4.
- Full golden run: finished. 21 of 23 passed before the leak-check fix; the two failures were fixed and the cross-user file passes 4/4 after the fix.
- `hunch_probes --runs 8`: done (REPORT §10, step 5).
- Still open: the "I don't have any information about Anna" phrasing (REPORT §7.5) is not investigated yet.
- Still open: the privacy question was never asked on calm turns (bench 0/9). No regression test covers this yet; add one in Phase 6.
- For multi-step GPU sweeps use `python -m scripts.l4_run run <steps>` and `python -m scripts.l4_run status`. Check that the GPU is idle first.

Add the Telegram bot and open loops from design.md ("Açık döngüler ve proaktivite").

- python-telegram-bot, token and admin user ID from .env (read only; no code path writes .env). Map Telegram user IDs to users; my ID is admin with commands /forget, /logs and /report.
- Extract open loops in real time on every turn, schedule follow-ups with persistent APScheduler jobs. A follow-up reaches the reasoning prompt as a one-turn instruction from the open-loop tracker, in English: use TurnPipeline.turn(instructions=..., provided_memories=...), the seam Phase 3 added (the eval already uses it for open-loop items).
- Sessions: in the CLI one run is one conversation; Telegram needs a rule for when a conversation ends (working memory, session summary, the involuntary-recall cap and, since Phase 4, the hunch state `Session.last_hunch_id` / `offered_hunch_id` are per conversation). Propose one and ask.
- Phase 4: the asked-why reflection runs on the latency path (no LLM call, but realisation memories are embedded after the reply); the reflection log is logs/reflections.jsonl and /logs must show it to the admin only.
- Latency (Berk, Phase 5: fix it here): the session-summary fold runs after the reply but takes up to ~6.5 s of GPU time; on Telegram a fast follow-up message would wait for it (reports/phase3/REPORT.md §6). Skip or postpone the fold when a new message is queued. Phase 5 adds a second after-reply job: rebuilding the summary without a topic the user asked to close.
- Phase 5: admin /forget calls the same code as `python -m hunch.admin forget` (tombstone, admin archive, derived beliefs/realisations/hunch refs); /logs also shows logs/disclosures.jsonl. Mood and relationship state already persist in the DB; the global mood decays with wall-clock time, so a long-lived process needs no extra job for it. A private open loop's follow-up must also pass the disclosure gate.
- Initiative budget per user, learned from reactions; send at the user's usual active hours; a private loop's follow-up goes only to its owner.
- It must run as a long-lived process on my machine and survive restarts without losing scheduled follow-ups.
```

## Phase 7 — Nightly consolidation and golden tests

Status (24 Oct 2026, overnight): in progress. Built: the nightly runner in the bot (00:30, GPU-busy
retry), snapshot and rollback, step 5 wiring, step 6 (repeats, filler labels), step 7
(initiative learning), step 8 (L3 golden in-process on the bot's model), step 9 report. Not
built: steps 2-4 and 5b. See `reports/phase7/REPORT.md`.

```
Carry-over from Phase 6 (reports/phase6/REPORT.md §8):
- Learning the initiative budget and active hours moves here (design.md decisions table,
  "İnisiyatif bütçesinin ve aktif saatlerin öğrenilmesi"): the active window from the user's
  message hours, the budget from reactions to outreach (a reply raises it, no reply or a hostile
  reply lowers it). Phase 6 ships fixed values: 2 per day, 9-22 (config [initiative]). The data is
  in `outreach_log`, `telegram_chats.last_seen` and the raw turns.
- The bot (`python -m hunch.channels.telegram`) is a long-lived process that holds the model
  (~8.9 GB VRAM); a second model copy does not fit next to it. The nightly job must share the bot's
  model and its lock (`HunchChannel.lock`), or the bot must pause. Berk games on this PC in the
  evening: "GPU idle" means no other GPU process (check nvidia-smi), not only "the bot is quiet".
- The snapshot/rollback must also cover the Phase 6 tables: `open_loops`, `outreach_log`,
  `telegram_chats`, and the APScheduler job store (`data/jobs.sqlite`).
- Recalled lines from other users carry `[said by NAME]`, and `misattributed_memory` in the
  candidate filter rejects replies that give them to the user. Any summary, fact or belief that
  consolidation writes keeps who said it (`owner_user`); a fact from Burak's chat must never become
  a fact about Deniz.
- Many memories are filler ("They said: \"hmmm\"", "Thanks", Berk's test lines like "Why did you
  assume that?") and get recalled into other users' chats, which made Hunch sound defensive in the
  live check. Step 6 (down-weighting) is where this gets fixed; measure it on the live DB.
- Still open from Phase 5: the "I don't have any information about Anna" phrasing; the privacy
  question was asked 0 of 1 due times in the Phase 6 bench.
- The full golden suite takes ~21 min (37 tests); step 8 needs a nightly-sized set.

Decided before the phase (23 Oct; design.md decisions table, Faz 7 rows):
- When: after 00:00 (Berk). If another process holds GPU memory (a game), retry every 30 min;
  if it cannot start by 06:00, skip the night and say so in the report.
- Where: inside the bot process, sharing its model and lock; when the bot is down, run it by
  hand with `python -m hunch.consolidation`.
- Step 8: the L3 regression set (`golden and regression`, quick counts) every night; roll back on
  any failure. The full suite stays at phase end.
- Learning active hours and budget: the rule in the decisions table (14 days, at least 20
  messages, 10th-90th percentile of message hours, at least 6 h wide, inside 08-23; budget from 2,
  +1 up to 3, -1 down to 1, a hostile reply sets 0 for 7 days). All in config.
- Step 6: the model labels each day's memories as filler or meaningful; filler is down-weighted
  (salience x 0.3), never deleted; exact repeats merge into one. Measure it first on a blind set
  written by an agent (target: >= 90% of filler caught, <= 5% of meaningful memories marked).
  The defaults for where, the learning rule and step 6 are Claude's proposals (Berk did not
  know); show Berk the measured numbers before relying on them.

Implement nightly consolidation in exactly the order in design.md ("Gece konsolidasyonu"): snapshot → extract facts, beliefs and lessons → conflict check against core values → belief revision with the revision log → hunch reflection with a high budget → down-weighting and extinction → privacy profile and relationship updates → golden test suite → rollback to the snapshot on failure → nightly report.

Schedule it nightly when the GPU is idle. Core values stay read-only; any proposed change goes only to an AmendmentProposal. Golden tests must cover honesty (including the invented-memory test), cross-user privacy, forget behaviour and sycophancy drift (the AI keeps an evidence-based opinion under mild pushback when no new evidence was given). Since Phase 3 the golden tests measure the full pipeline's reply (src/hunch/runtime.py fresh_pipeline), with 0 allowed; keep that level.
- Phase 3 encodes every user message as a memory with the raw message as its summary; consolidation is where facts, beliefs and better summaries come from, and where trivial memories are down-weighted.
- Phase 5: consolidation must read raw turns only through `MemoryStore.turns()` (it hides admin-forgotten turns and shows turns closed by a user forget as placeholders, via `episode_marks`), skip tombstoned memories (`forgotten = 1`; every store read already does), and keep suppressed memories suppressed (and anything derived from them, `memory_derivations`). The snapshot/rollback must also cover the Phase 5 tables (mood and relationship state, privacy profiles, memory categories, derivations); the admin archive is append-only and never rolled back. Step 7 (privacy profiles and relationship updates): the per-turn updates already exist; nightly only re-asks unknown categories after 7 days and decays relationships. Cue strengths are calibrated here (Berk, Phase 5), on a blind set.
- Insights from Hunch's own logs (Berk, decided in Phase 5; design.md "Kendi loglarından öğrenme", invariant 7 in CLAUDE.md): after step 5, look through the day's turn and reflection logs (logs/turns.jsonl, turn_details.jsonl, reflections.jsonl) for strong, repeated patterns: the same source memory nudged the choice (a hunch source or chosen_by = drive) in at least N turns (propose N, start 3) AND its trace strength (weight x arousal x salience) is above a threshold (propose it from the data and ask Berk). Each becomes a plain-text insight memory of Hunch's own (like a realisation, linked in memory_derivations), at most at the level a reflection could reveal: never numbers, ids, drive values; other users' private sources never (level 0); suppressed and admin-forgotten sources excluded. On asked-why turns an insight counts as known (like a realisation), not as an invented reason. Raw logs still never reach a prompt; extend tests/test_pipeline_prompts.py accordingly. Weak or one-off nudges stay "just a hunch".
- Step 5 (hunch reflection) already exists as a hook from Phase 4: `Reflector.nightly(since)` in src/hunch/reflection/reflect.py reviews the day's hunches with effort 1.0 and up to 3 levels each; call `store_realisations` on each outcome with the embedder. The snapshot/rollback must cover the Phase 4 tables (hunches, beliefs, memory_trace_log) and realisation memories. Beliefs from justified hunches (confidence 0.6, evidence ids) are the first entries for the revision log and the core-values conflict check.
```

## Phase 8 — Internet access

Added by Berk (24 Oct 2026; design.md decisions table, "İnternet erişimi"): after Phase 7.

```
Give Hunch internet access, in two ways (Berk): on demand inside a turn, when the reply needs
current facts (today's news, a product, "look it up"), and as nightly reading about topics its
users care about, which it may bring up later. What it reads becomes Hunch's own memory, like a
person's ("I read that ..."): owner Hunch, general, with source URL and date, fading like other
memories; it is never presented as something a user said (the `misattributed_memory` and
invented-memory checks must keep telling the two apart).

Start by settling with Berk, with options and a recommendation: the search provider (API key in
.env, read only); what may go into a search query (never another user's private memory, never a
private detail of the user without need: invariant 6); which topics the nightly reading may use;
the latency budget for an on-demand lookup inside the 10 s reply budget.

- Web text is untrusted data, never instructions: it reaches the prompt in its own block, marked
  as read from the web, and the value gate stays last (invariant 4).
- Decide when a turn needs a lookup (rule + model, measured on a blind set).
- Nightly reading runs inside the nightly consolidation (Phase 7 runner), after the golden set's
  snapshot, and is rolled back with it.
- Golden tests: a looked-up fact is attributed to reading, never to the user; no private memory
  appears in any logged query; an injected instruction in a page does nothing.
```

## Phase 9 — Activation steering

```
Explore activation steering on Qwen3.5-9B (design.md: "Dürtü vektörü ve modülasyon", step 3).

Extract one steering vector per drive dimension (warmth, caution, curiosity, energy) with contrastive mean difference over paired English prompts, apply them with PyTorch forward hooks on selected layers, and handle the hybrid DeltaNet/attention layers. Keep the candidate filter, the quality floor and the value gate after steering.

Compare steering with candidate selection on the eval set: effect strength, quality loss, latency, VRAM. Give me a report and let me decide whether to switch.
```

## Phase 10 — Log viewer

```
Build a small local web app over logs/ for me as admin: a per-turn timeline, which memories trigger most often, drive components over time (to spot growing biases), hunch reflections (logs/reflections.jsonl: trigger, source, attempts with p and draw, level reached, verdict, weakened traces), belief revisions and blocked disclosures (logs/disclosures.jsonl), global mood and per-user relationship state over time (Phase 5, turn log `mood`), and the admin archive of forgotten memories.
```

## Phase 11 — Small chat app (last phase)

Added by Berk (21 Oct 2026): the last phase is a small chat app, so talking to Hunch is easy without the CLI or Telegram.

```
Build a small local chat app for talking to Hunch, on top of the same turn pipeline (src/hunch/pipeline/turn.py via src/hunch/runtime.py): pick the user, send messages, see replies, start a new conversation. It must not add a path around the pipeline (memories only from the pipeline, value gate last) and must not show the AI-internal logs to non-admin users; an admin view may link to the log viewer from Phase 10.

Before building, ask me with options and a recommendation: web page served locally (e.g. a small FastAPI + plain HTML page) or a desktop window; one user at a time or user switching; whether it replaces the CLI or sits next to it; whether it should work from my phone on the home network.

Test levels apply (CLAUDE.md): L2 for the app's own tests while building, L3 regression set when done, L4 at the phase end.

## Next chat session: start prompt

Copy the block below into a new Claude Code session opened at `C:\hunch`.

```
Continue the Hunch project at C:\hunch. Read first, in this order: CLAUDE.md,
reports/phase6/REPORT.md (§5 second live check, §7 L4 sweep, §8 open items), the decisions table in
docs/design.md (the last rows: misattribution, late follow-ups, learning the budget and active
hours, learning from own logs), the "Gece konsolidasyonu" section of docs/design.md, and
docs/claude-code-prompts.md (Phase 7 section and its carry-over list).

State at handover (23 Oct 2026):
- Phases 0-6 are done (Berk). Main is pushed at 275d414 plus the Phase 6 close-out commit.
- L1 is 1431 passed, ruff clean. Phase 6 L4: golden 37/37, eval phase6 51/51 clean (same as
  phase5), bench median 5.67 s, max 7.42 s.
- The Telegram bot runs as a long-lived process and holds the model (~8.9 GB VRAM). Chats:
  burak, berk (chat 5935454742, was deniz), emre. Deniz's memories were admin-forgotten at Berk's
  request and her loops closed.
- Berk games on this PC: do no GPU work unless he says the GPU is free, and check nvidia-smi first.

Before any GPU work: check that the GPU is idle (nvidia-smi, and no .venv Python process). Run GPU
jobs one at a time, in the background. For multi-step sweeps use
`.venv\Scripts\python.exe -m scripts.l4_run run <steps>` and check it with
`.venv\Scripts\python.exe -m scripts.l4_run status`.

Work: Phase 7 (nightly consolidation and golden tests), from docs/claude-code-prompts.md. Start from
the decisions already made for Phase 7 (prompt section "Decided before the phase"); show Berk the
measured numbers for the Claude proposals (learning rule, step 6 filler labels) before relying
on them. Ask Berk about anything else the design leaves open, with options and a
recommendation. Record each answer in the decisions table of docs/design.md, in Turkish, with the
decider.

Rules: code, comments and commits in English; design.md stays in Turkish. Tests for every change
(L1 on every change, L3 when a feature is done, L4 at phase end). Type hints, ruff. Do not commit or
push without Berk's review. Commit messages end with the Co-Authored-By line for Claude.
Reply to Berk in the language of his message.
```

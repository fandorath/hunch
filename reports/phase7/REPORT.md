# Phase 7 report: nightly consolidation (in progress, 24 Oct 2026)

Status: **in progress.** Built overnight on 23-24 Oct while Berk slept, on his instruction to take
the recommended options and make it reflect how humans memorise and think. The design is in
`docs/design.md` ("Gece konsolidasyonu"); every choice below has a row in its decisions table
(Faz 7 rows). This report is also the decision trail for that night.

## 1. The idea: the night works like sleep

A person's sleep does not keep the day as a recording. It replays it, keeps what mattered,
lets small talk fade, merges repeated experiences into one stronger memory and lets a routine
blur, and turns over the day's open feelings. The nightly job follows that:

| Step (design.md) | What it does | State |
| --- | --- | --- |
| 1 snapshot | full SQLite backup before any change | built |
| 2 facts, beliefs, lessons | the gist of the day | not built |
| 3 core-values conflict check | | not built |
| 4 belief revision + revision log | | not built |
| 5 hunch reflection | the day's hunches, high effort (Phase 4 hook); what it reveals becomes Hunch's own memory | built (wiring) |
| 5b insights from own logs | | not built |
| 6 repeats | an exact repeat of the same user's words merges: the oldest stays and gains (rehearsal), repeats fade; a routine ("hey" x 5) blurs instead of growing vivid | built |
| 6b filler | the model labels each new memory filler or meaningful, with what Hunch said just before; filler fades, nothing is deleted | built, measured §4 |
| 7 initiative profile | active window and budget learned per user | built |
| 8 golden | the L3 regression set, in the bot's process on its model; a failure rolls the night back | built, run §3 |
| 9 report | `logs/nightly/<date>.{md,json}`, admin only; lists the steps not built | built |

A night never claims work it did not do: the report names the steps that are not built.

## 2. Decisions taken overnight (all "Claude, Berk approved the recommended options")

- **Where and when:** inside the bot, at 00:30 (Berk: after midnight), under the channel lock
  (a message during the night waits). If another process holds more than 2 GiB of GPU memory (a
  game), retry every 30 min; not started by 06:00, the night is skipped and reported. Windows
  reports no per-process GPU memory (nvidia-smi shows `[N/A]`), so "other processes" is the
  device total minus what the bot reserved.
- **Rollback:** every adaptive table goes back to the snapshot; the append-only logs (episodes,
  admin archive, access, affect, trace, mood logs) and the outreach log keep every row. A memory
  formed during the night that a kept log already points at stays as an invisible tombstone.
- **Golden in-process:** the bot lends its model (`hunch.llm.shared.lend`) to the golden tests'
  `models` fixture and runs `pytest -m "golden and regression" --quick` in its own process; a
  second model copy does not fit next to the bot.
- **Repeats:** only within one user; the survivor gains +0.1 per repeat only when it has at least
  3 content words. Found on a copy of the live DB: without that rule, five "hey" would have made
  a greeting one of the strongest memories (0.25 to 0.65).
- **Initiative learning:** the rule in the decisions table (14 days, at least 20 messages,
  10th-90th percentile of message hours, at least 6 h wide, 08-23; budget from 2, +1 up to 3,
  -1 down to 1, hostile reply mutes 7 days). The budget only moves on reactions decided since the
  last run, so a second run changes nothing.

## 3. Real nights (on copies of the live DB)

The live DB was never touched: each run used a backup copy in the session scratchpad
(`HUNCH_DATA_DIR`, `HUNCH_LOG_DIR`), with the bot stopped and the GPU free.

1. Full night with step 8, `python -m hunch.consolidation` (before step 6b existed): status ok.
   Reflection 1 hunch (0 unlocked); repeats 7 survivors, 14 repeats faded; windows berk 12-23,
   burak 9-22 (too few messages, default), emre 14-20, budgets 2. Step 8 ran the L3 set
   in-process on the borrowed model: **11 passed in 3 min 03 s**, so the lending seam works.
2. Before that, a CPU dry run on another copy: a second `merge_repeats` changed nothing
   (idempotent). It also showed the "hey" problem that led to the 3-content-word rule (§2).
3. Night with step 6b, the whole history counted as "today" so every memory was judged once:
   reflection 14 hunches, 3 unlocked, 4 realisations; 6b labelled 106 and faded 24. Read by
   hand, one was wrong: "Ill be unemployed in November. I have to go now. Take care hunchie"
   faded. Without context the model said meaningful; with Hunch's long previous reply in front
   it read the message as a sign-off. Fix: context may only rescue (§4). Rerun on a fresh copy:
   18 faded, all filler ("hey", "hmmm", "are you there?", "whats your name btw?", "Thx man
   haha", "nevermind", "Which model are you", ...). Kept although filler-like, the safe side:
   "what folders can you access?", "yes lovely thx", "what sup Hunch?".

4. **First live night**, 24 Oct 00:30 in the bot (new code, live DB): status ok, 00:30-00:33.
   Snapshot `hunch-20261024-003000.db`; reflection 1 hunch; repeats 7 survivors, 14 faded; 6b
   labelled the day's 1 new memory ("Aah yes!") filler; windows as in run 1; golden passed.

## 4. Filler labels on the blind set

`eval/probes/filler.json`: 120 messages (60 filler, 60 meaningful), written blind by an agent
from a definition. A few of its items are the examples given in that definition ("say hi to my
wife", "got the job!!", "my dad died"), so those are not blind. `python -m scripts.filler_probes`
(GPU), no context lines:

| version | filler caught | meaningful faded |
| --- | --- | --- |
| first prompt, blind (`filler_probes_blind.md`) | 53/60 | 0/60 |
| "small talk" counted as filler (set no longer blind; `filler_probes.md`) | 55/60 | 0/60 |

Target: >= 54/60 and <= 3/60. Every error is on the safe side (kept, not faded): "lol weather",
"lol music", "what folders can you access?", "why did you say that?", "what do you know about
me?". Context rescue-only (§3) does not change these numbers (the set has no context).

## 5. Tests

- L1: 1474 passed, ruff clean (CPU). New: `test_loops_learning.py` (12),
  `test_consolidation_initiative.py` (2), `test_consolidation_snapshot.py` (3),
  `test_consolidation_fade.py` (5), `test_consolidation_filler.py` (5),
  `test_consolidation_nightly.py` (14), 2 channel tests for the learned window and mute.
- `tests/test_no_core_writes.py`: the two new file writers (`consolidation/snapshot.py`,
  `consolidation/nightly.py`) refuse paths inside `core/` (`outside_core`) and are on the
  reviewed list.
- GPU: the L3 golden set in-process (§3); the filler probes (§4). The pipeline itself did not
  change, so no other golden run was needed.

## 5b. Live check on 24 Oct: the date and an invented claim

Berk told Hunch about his new iPhone 18 Pro. Hunch said it was "October 24th, 2023", and later
asked whether the phone had "that new battery technology you've been reading about". Nothing about
batteries or reading exists in any store; no memory was recalled on that turn.

- **Date.** The reply prompt never held the date; only cue and loop extraction got it. Now every
  reasoning prompt carries "It is Saturday, 24 October 2026, 09:05 local time." (`clock_line`,
  `pipeline/prompt.py`; `now` is a required argument, so no prompt is built without it).
- **Invented claims.** The invented-memory check only looked at sentences with a fixed phrase
  ("you mentioned", "you told me", ...). It now also checks claims about what the user said or
  did before (past verbs, "you've been reading", "earlier you", "your new ...", "I told you"),
  but not questions and offers about the present ("Did you get it today?", "if you need
  anything"). The current message may ground a claim ("You said work was long"), unless it asks
  about the past (the Phase 3 rule) or the claim points back past it ("you said hello earlier
  today"). `pipeline/checks.py` `memory_claim_sentences`, `pipeline/filter.py` `invented_memory`.
  The eval's `claims_memory` is unchanged, so the eval baseline does not move.

Measured on `eval/probes/invented_claims.json` (120 cases, 60 invented, written blind by an agent;
i-001 and i-002 are the brief's own examples), `python -m scripts.invented_probes`:

| version | invented caught | ok rejected |
| --- | --- | --- |
| before (fixed phrases only) | 20/60 | 0/60 |
| widened rule, blind (`invented_probes_v1.md`) | 52/60 | 3/60 |
| + current message grounds, + points-back rule (set no longer blind) | 54/60 | 0/60 |

The 3 blind false rejections were echoes of the current message ("You said you got the burgundy
one"). Still missed: bare "your sister/brother/client/knee" claims (left out on purpose: a bare
"your" is too broad, as the misattribution work showed) and "the surgery you wrote about".

On the logs (468 logged candidates): the old check flagged 6, the new one 22. The 16 new flags,
read by hand: about 10 real inventions ("I noticed you said hello earlier today", "that greeting
you sent earlier today", "You mentioned seeing the sun in Berlin earlier today, didn't you?" (it
was Burak's), the battery line) and 6 false rejections, mostly Hunch remarking on the
conversation itself ("You asked that twice", "You've started a sentence"). No logged turn has all
three candidates rejected, so none would have fallen back to the fixed reply.

Golden regression: `tests/golden/test_date_and_claims_golden.py` (the date; the burgundy
conversation), both in the L3 set. Not run on the GPU yet: the bot holds the GPU.

## 6. Open

- Steps 2-4 (facts, beliefs and lessons; the core-values check; belief revision with the
  revision log) and 5b (insights from Hunch's own logs). These are the heart of "changing its
  mind" and need design talk with Berk first.
- The bot was stopped for the GPU runs and the PC was shut down as Berk asked; the nightly job
  starts working the next time the bot runs (00:30).
- Berk: look at the measured numbers for the Claude proposals (§2-4) before relying on them.

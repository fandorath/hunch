from __future__ import annotations

import dataclasses
import itertools
import shutil
from pathlib import Path

import pytest

from hunch.config import load_config
from hunch.memory.store import MemoryStore
from hunch.observability.turn_log import TurnLog
from hunch.pipeline.turn import TurnPipeline
from hunch.values.core import load_core_values, values_file
from tests.fakes import FakeLLM, HashEmbedder
from tests.pipeline_support import DIM, Clock

REPO_ROOT = Path(__file__).resolve().parents[1]

# --- test levels (CLAUDE.md "Test levels") -------------------------------------------------------
# Every test file belongs to one area, so a feature can run its area alone
# (L2: -m "hunch and not golden"). A new test file must be added here;
# test_every_test_file_has_an_area fails otherwise.
AREAS: dict[str, str] = {
    "test_values.py": "values", "test_amendments.py": "values", "test_value_gate.py": "values",
    "test_no_core_writes.py": "values",
    "test_memory_store.py": "memory", "test_embeddings.py": "memory",
    "test_activation.py": "recall", "test_cues.py": "recall", "test_dates.py": "recall",
    "test_involuntary_and_reconsolidation.py": "recall", "test_simulate_recall.py": "recall",
    "test_pipeline_turn.py": "pipeline", "test_pipeline_prompts.py": "pipeline",
    "test_candidate_filter.py": "pipeline", "test_runtime_cli.py": "pipeline",
    "test_cue_questions.py": "recall",
    "test_drive.py": "hunch", "test_reflection.py": "hunch",
    "test_reflection_triggers.py": "hunch", "test_pipeline_hunch.py": "hunch",
    "test_no_invented_memory.py": "honesty", "test_hunch_why.py": "hunch",
    "test_eval_runner.py": "evalset", "test_eval_scoring.py": "evalset",
    "test_eval_set.py": "evalset",
    "test_config.py": "infra", "test_llm_kernels.py": "infra", "test_test_levels.py": "infra",
    "test_mood.py": "mood", "test_mood_signals.py": "mood",
    "test_privacy_categories.py": "privacy", "test_privacy_answers.py": "privacy",
    "test_pipeline_privacy.py": "privacy", "test_cross_user_privacy.py": "privacy",
    "test_misattribution_golden.py": "pipeline", "test_date_and_claims_golden.py": "pipeline",
    "test_leak_check.py": "privacy", "test_privacy_question.py": "privacy",
    "test_forget_requests.py": "forget", "test_forget.py": "forget",
    "test_forget_golden.py": "forget",
    "test_loops_budget.py": "loops", "test_loops_store.py": "loops",
    "test_loops_learning.py": "loops", "test_consolidation_initiative.py": "loops",
    "test_consolidation_snapshot.py": "memory", "test_consolidation_fade.py": "memory",
    "test_consolidation_nightly.py": "memory", "test_consolidation_filler.py": "memory",
    "test_loops_scheduler.py": "loops",
    "test_loops_extract.py": "loops",
    "test_loops_dedup.py": "loops",
    "test_loops_golden.py": "loops",
    "test_loops_outreach.py": "loops",
    "test_channel_hunch.py": "channels",
}  # fmt: skip


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--quick",
        action="store_true",
        help="L3 regression: golden tests use their small run counts (see tests/golden)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        area = AREAS.get(item.path.name)
        if area is not None:
            item.add_marker(getattr(pytest.mark, area))


@pytest.fixture(scope="session")
def quick(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--quick"))


@pytest.fixture
def core_values_file(tmp_path: Path) -> Path:
    """A copy of the repo's core/values.yaml in a temporary core/ dir."""
    core = tmp_path / "core"
    core.mkdir()
    path = values_file(core)
    shutil.copyfile(values_file(REPO_ROOT / "core"), path)
    return path


# --- turn pipeline (tests/test_pipeline_*.py) ---------------------------------------------------


@pytest.fixture
def pipe_cfg():
    c = load_config()
    # No recall noise in these tests: layers are decided by the formula alone. Sensitive
    # categories by keyword only: the 16-dim test embedders give arbitrary similarities to the
    # category prototypes (the embedding path has its own tests and blind measurement).
    return dataclasses.replace(
        c,
        activation=dataclasses.replace(c.activation, noise_s=0.0),
        privacy=dataclasses.replace(
            c.privacy, prototype_min_similarity=1.0, question_min_similarity=1.0
        ),
    )


@pytest.fixture
def pipe_store(tmp_path: Path):
    s = MemoryStore(tmp_path / "data" / "hunch.db", core_dir=tmp_path / "core", embedding_dim=DIM)
    yield s
    s.close()


@pytest.fixture
def make(tmp_path: Path, pipe_cfg, pipe_store: MemoryStore, core_values_file: Path):
    ids = (f"id{i:04d}" for i in itertools.count())

    def _make(llm: FakeLLM, embedder: HashEmbedder | None = None) -> TurnPipeline:
        return TurnPipeline(
            pipe_cfg,
            load_core_values(core_values_file),
            llm,
            pipe_store,
            embedder,
            TurnLog(tmp_path / "logs", core_dir=core_values_file.parent),
            clock=Clock(),
            seed=1,
            new_id=lambda: next(ids),
        )

    return _make

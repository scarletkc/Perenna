from __future__ import annotations

import json
import math
import os
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from vexor import VexorClient

from perenna.index import MAX_SEARCH_CANDIDATES, _chunks, _record
from perenna.models import Memory


@dataclass(frozen=True, slots=True)
class EvalQuery:
    query: str
    memory_id: str
    category: str


MEMORIES = (
    Memory(
        id="01K00000000000000000000001",
        title="Museum preview schedule",
        summary="Prepare exhibit labels and opening tasks while the gallery remains in preview.",
        source="eval",
        created_at="2026-08-23T00:00:00.000000Z",
        updated_at="2026-08-23T00:00:00.000000Z",
        body=(
            "The fictional Cedar Museum can draft labels and rehearse the opening workflow before "
            "tickets go on sale. Public listings must wait until the opening date is confirmed."
        ),
        scope="project:cedar-museum",
        relative_path="projects/cedar-museum/01K00000000000000000000001.md",
    ),
    Memory(
        id="01K00000000000000000000002",
        title="Archive ranking baseline",
        summary="Juniper Archive uses semantic ranking without keyword reranking as its baseline.",
        source="eval",
        created_at="2026-08-23T00:00:00.000000Z",
        updated_at="2026-08-23T00:00:00.000000Z",
        body=(
            "The fictional archive keeps one ranking method until repeatable evaluations support a "
            "change. A second keyword index is added only when measured retrieval needs it."
        ),
        scope="project:juniper-archive",
        relative_path="projects/juniper-archive/01K00000000000000000000002.md",
    ),
    Memory(
        id="01K00000000000000000000003",
        title="Catalog outage behavior",
        summary="Search reports an index error while browsing and opening saved cards still work.",
        source="eval",
        created_at="2026-08-23T00:00:00.000000Z",
        updated_at="2026-08-23T00:00:00.000000Z",
        body=(
            "Juniper Archive does not silently switch to a filename scan when its index is "
            "offline. New cards can be saved as pending, and direct reads use the stored snapshot."
        ),
        scope="project:juniper-archive",
        relative_path="projects/juniper-archive/01K00000000000000000000003.md",
    ),
    Memory(
        id="01K00000000000000000000004",
        title="Curated card abstracts",
        summary="Each archive card abstract is supplied by its editor and remains authoritative.",
        source="eval",
        created_at="2026-08-23T00:00:00.000000Z",
        updated_at="2026-08-23T00:00:00.000000Z",
        body=(
            "The archive does not invent abstracts or tags. Search records contain the title, the "
            "editor's abstract, and a section of the card text."
        ),
        scope="project:juniper-archive",
        relative_path="projects/juniper-archive/01K00000000000000000000004.md",
    ),
    Memory(
        id="01K00000000000000000000005",
        title="Festival announcement",
        summary=(
            "The public festival notice contains visitor facts and omits rehearsal-room mishaps."
        ),
        source="eval",
        created_at="2026-08-23T00:00:00.000000Z",
        updated_at="2026-08-23T00:00:00.000000Z",
        body=(
            "A broken music stand during a private rehearsal is not useful to visitors. The notice "
            "should state the confirmed venue, opening time, and accessibility information."
        ),
        scope="global",
        relative_path="global/01K00000000000000000000005.md",
    ),
    Memory(
        id="01K00000000000000000000006",
        title="Workshop board permission",
        summary="APP_WRITE_DENIED means the fictional workshop board rejected a write permission.",
        source="eval",
        created_at="2026-08-23T00:00:00.000000Z",
        updated_at="2026-08-23T00:00:00.000000Z",
        body=(
            "Check whether the demo account may edit the board before retrying. Reading a card "
            "does not establish permission to move or delete it."
        ),
        scope="global",
        relative_path="global/01K00000000000000000000006.md",
    ),
    Memory(
        id="01K00000000000000000000007",
        title="Orchard dataset transfer",
        summary="Set ORCHARD_CACHE_MODE=plain when the fictional orchard cache rejects a transfer.",
        source="eval",
        created_at="2026-08-23T00:00:00.000000Z",
        updated_at="2026-08-23T00:00:00.000000Z",
        body=(
            "Retry the sample fruit dataset with the plain cache mode, then verify its checksum "
            "before running the fictional sorting exercise."
        ),
        scope="project:orchard-lab",
        relative_path="projects/orchard-lab/01K00000000000000000000007.md",
    ),
    Memory(
        id="01K00000000000000000000008",
        title="Concurrent catalog access",
        summary="Catalog searches share read locks while imports and edits use an exclusive lock.",
        source="eval",
        created_at="2026-08-23T00:00:00.000000Z",
        updated_at="2026-08-23T00:00:00.000000Z",
        body=(
            "Several visitors may search at once. An editor rechecks the saved catalog under the "
            "exclusive lock before importing cards or changing an entry."
        ),
        scope="project:juniper-archive",
        relative_path="projects/juniper-archive/01K00000000000000000000008.md",
    ),
    Memory(
        id="01K00000000000000000000009",
        title="Card-level section aggregation",
        summary="Rank distinct cards by their best section so long cards cannot crowd the results.",
        source="eval",
        created_at="2026-08-23T00:00:00.000000Z",
        updated_at="2026-08-23T00:00:00.000000Z",
        body=(
            "The candidate pool covers the maximum sections per card times the result limit. Only "
            "the highest-scoring section from each card becomes a returned candidate."
        ),
        scope="project:juniper-archive",
        relative_path="projects/juniper-archive/01K00000000000000000000009.md",
    ),
    Memory(
        id="01K00000000000000000000010",
        title="Remote visitor isolation",
        summary="Remote access is limited to one demo visitor and explicit catalog actions.",
        source="eval",
        created_at="2026-08-23T00:00:00.000000Z",
        updated_at="2026-08-23T00:00:00.000000Z",
        body=(
            "A valid session does not grant access to every fictional visitor. The expected "
            "account, audience, and requested browse or edit action must all match."
        ),
        scope="project:juniper-archive",
        relative_path="projects/juniper-archive/01K00000000000000000000010.md",
    ),
    Memory(
        id="01K00000000000000000000011",
        title="Greenhouse watering schedule",
        summary="watering_cycle_stage_2 follows the sample 6, 8, 10, 12, 14 minute schedule.",
        source="eval",
        created_at="2026-08-23T00:00:00.000000Z",
        updated_at="2026-08-23T00:00:00.000000Z",
        body=(
            "The fictional greenhouse exercise checks each stage in order and records a separate "
            "moisture reading after every watering interval."
        ),
        scope="project:willow-greenhouse",
        relative_path="projects/willow-greenhouse/01K00000000000000000000011.md",
    ),
    Memory(
        id="01K00000000000000000000012",
        title="Pocket almanac lookup",
        summary="Pocket Almanac scans saved notes by literal text instead of semantic ranking.",
        source="eval",
        created_at="2026-08-23T00:00:00.000000Z",
        updated_at="2026-08-23T00:00:00.000000Z",
        body=(
            "The fictional notebook supports any-word, same-line, and nearby-line matching. Recent "
            "notes are selected separately from this simple exact lookup."
        ),
        scope="global",
        relative_path="global/01K00000000000000000000012.md",
    ),
    Memory(
        id="01K00000000000000000000013",
        title="Recipe booklet publication",
        summary=(
            "After publication, verify the booklet in a fresh reader and check ready and current."
        ),
        source="eval",
        created_at="2026-08-23T00:00:00.000000Z",
        updated_at="2026-08-23T00:00:00.000000Z",
        body=(
            "A local archive or successful print preview is not evidence of publication. Open the "
            "fictional catalog copy and inspect its ready and current labels after delivery."
        ),
        scope="global",
        relative_path="global/01K00000000000000000000013.md",
    ),
    Memory(
        id="01K00000000000000000000014",
        title="Effective kiosk configuration",
        summary="Diagnostics report effective kiosk values after environment and file precedence.",
        source="eval",
        created_at="2026-08-23T00:00:00.000000Z",
        updated_at="2026-08-23T00:00:00.000000Z",
        body=(
            "A stored theme field may be empty while an environment variable selects dusk mode. "
            "The fictional kiosk report describes what its next screen will actually use."
        ),
        scope="project:cedar-museum",
        relative_path="projects/cedar-museum/01K00000000000000000000014.md",
    ),
    Memory(
        id="01K00000000000000000000015",
        title="Bluejay sorting checkpoint",
        summary=(
            "Train the fictional Bluejay sorter from its base sample and pause at checkpoint one."
        ),
        source="eval",
        created_at="2026-08-23T00:00:00.000000Z",
        updated_at="2026-08-23T00:00:00.000000Z",
        body=(
            "Do not resume from the obsolete practice checkpoint. Validate sample rows and stop "
            "the exercise when required category fields are missing."
        ),
        scope="project:orchard-lab",
        relative_path="projects/orchard-lab/01K00000000000000000000015.md",
    ),
)

POSITIVE_QUERIES = (
    EvalQuery(
        "展览还在内部预览时，可以先准备说明牌和开放流程吗？",
        MEMORIES[0].id,
        "semantic",
    ),
    EvalQuery("为什么 Juniper Archive 暂时不开关键词重排？", MEMORIES[1].id, "semantic"),
    EvalQuery("索引服务停了会不会偷偷改用文件名扫描？", MEMORIES[2].id, "mixed"),
    EvalQuery("档案卡片的摘要由谁提供？", MEMORIES[3].id, "semantic"),
    EvalQuery("节庆公告里要不要写彩排时弄坏的谱架？", MEMORIES[4].id, "hard"),
    EvalQuery("APP_WRITE_DENIED", MEMORIES[5].id, "exact"),
    EvalQuery("ORCHARD_CACHE_MODE=plain", MEMORIES[6].id, "exact"),
    EvalQuery("多个目录查询可以并发，但导入和编辑要独占", MEMORIES[7].id, "semantic"),
    EvalQuery("别让一张很长卡片的很多章节挤掉其他结果", MEMORIES[8].id, "semantic"),
    EvalQuery("远程访问怎样限制到单个访客和具体操作？", MEMORIES[9].id, "semantic"),
    EvalQuery("watering_cycle_stage_2", MEMORIES[10].id, "exact"),
    EvalQuery("Pocket Almanac 的笔记查找是语义搜索吗？", MEMORIES[11].id, "semantic"),
    EvalQuery("书册目录的 ready 和 current 应该什么时候验证？", MEMORIES[12].id, "mixed"),
    EvalQuery("配置诊断为什么要显示最终生效的主题？", MEMORIES[13].id, "semantic"),
    EvalQuery("不要从旧练习检查点继续训练分类器", MEMORIES[14].id, "mixed"),
    EvalQuery("不要把本地压缩包理解为已经公开出版", MEMORIES[12].id, "hard"),
)

UNRELATED_QUERIES = (
    "台北周末会不会下雨？",
    "怎样做一份传统提拉米苏？",
    "解释量子色动力学的重整化群",
    "十九世纪法国铁路的时刻表在哪里查？",
)


@pytest.mark.live_provider
def test_memory_retrieval_eval_reports_recall_and_unrelated_scores(tmp_path: Path) -> None:
    if os.getenv("PERENNA_RUN_LIVE_PROVIDER") != "1":
        pytest.skip("set PERENNA_RUN_LIVE_PROVIDER=1 to run the live retrieval evaluation")

    client = VexorClient(cache_dir=tmp_path / "index")
    collection = client.collection("perenna-memory-retrieval-eval")
    try:
        collection.drop()
        collection.upsert_many([_record(chunk) for memory in MEMORIES for chunk in _chunks(memory)])
        report = {
            "dataset": {
                "memories": len(MEMORIES),
                "positive_queries": len(POSITIVE_QUERIES),
                "unrelated_queries": len(UNRELATED_QUERIES),
            },
            "modes": {mode: _evaluate_mode(collection, mode) for mode in ("off", "hybrid")},
        }
        print("PERENNA_RETRIEVAL_EVAL=" + json.dumps(report, allow_nan=False))
    finally:
        collection.drop()
        client.close()


def _evaluate_mode(collection: Any, mode: str) -> dict[str, Any]:
    ranks_by_category: dict[str, list[int | None]] = defaultdict(list)
    misses_at_1: list[dict[str, Any]] = []
    all_ranks: list[int | None] = []
    for case in POSITIVE_QUERIES:
        candidates = _distinct_candidates(collection, case.query, mode)
        rank = next(
            (
                index
                for index, candidate in enumerate(candidates, start=1)
                if candidate[0] == case.memory_id
            ),
            None,
        )
        all_ranks.append(rank)
        ranks_by_category[case.category].append(rank)
        if rank != 1:
            misses_at_1.append({"query": case.query, "rank": rank})

    unrelated: list[dict[str, Any]] = []
    unrelated_top1_scores: list[float] = []
    unrelated_top5_scores: list[float] = []
    for query in UNRELATED_QUERIES:
        candidates = _distinct_candidates(collection, query, mode)
        scores = [score for _, score in candidates[:5]]
        unrelated.append({"query": query, "top_scores": [_round(score) for score in scores]})
        if scores:
            unrelated_top1_scores.append(scores[0])
            unrelated_top5_scores.extend(scores)

    return {
        "overall": _metrics(all_ranks),
        "by_category": {
            category: _metrics(ranks) for category, ranks in sorted(ranks_by_category.items())
        },
        "misses_at_1": misses_at_1,
        "unrelated": unrelated,
        "unrelated_top1_distribution": _distribution(unrelated_top1_scores),
        "unrelated_top5_distribution": _distribution(unrelated_top5_scores),
    }


def _distinct_candidates(collection: Any, query: str, mode: str) -> list[tuple[str, float]]:
    best_by_memory: dict[str, tuple[float, int]] = {}
    results = collection.search(
        query,
        top_k=MAX_SEARCH_CANDIDATES,
        rerank=mode,
    )
    for candidate_rank, result in enumerate(results):
        score = float(result.score)
        if not math.isfinite(score):
            raise AssertionError(f"{mode} returned a non-finite score for {query!r}")
        memory_id = str(result.metadata["memory_id"])
        current = best_by_memory.get(memory_id)
        if current is None or score > current[0]:
            best_by_memory[memory_id] = (score, candidate_rank)
    ranked = sorted(
        best_by_memory.items(),
        key=lambda item: (-item[1][0], item[1][1]),
    )
    return [(memory_id, score) for memory_id, (score, _) in ranked]


def _metrics(ranks: list[int | None]) -> dict[str, float | int]:
    return {
        "queries": len(ranks),
        "recall_at_1": _round(sum(rank == 1 for rank in ranks) / len(ranks)),
        "recall_at_3": _round(sum(rank is not None and rank <= 3 for rank in ranks) / len(ranks)),
        "recall_at_5": _round(sum(rank is not None and rank <= 5 for rank in ranks) / len(ranks)),
        "mrr_at_5": _round(
            sum(1 / rank for rank in ranks if rank is not None and rank <= 5) / len(ranks)
        ),
    }


def _distribution(scores: list[float]) -> dict[str, float | int | None]:
    if not scores:
        return {"count": 0, "min": None, "median": None, "max": None}
    return {
        "count": len(scores),
        "min": _round(min(scores)),
        "median": _round(statistics.median(scores)),
        "max": _round(max(scores)),
    }


def _round(value: float) -> float:
    return round(value, 6)

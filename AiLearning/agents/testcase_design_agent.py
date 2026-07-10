import json
import logging
import re
import threading
import time as time_module
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Generator

from langchain_core.documents import Document

from AiLearning.agents.base import AgentResponse, BaseAgent
from AiLearning.prompts.testcase_design import (
    DEFAULT_EXPANSION_PROMPT,
    DEFAULT_IMPACT_ANALYSIS_PROMPT,
    DEFAULT_SKILL_SELECTION_PROMPT,
    DEFAULT_TESTPOINT_PROMPT,
)
from AiLearning.rag.retriever import retrieve, retrieve_from_multiple_collections
from AiLearning.rag.splitter import split_documents
from AiLearning.service import get_client
from AiLearning.skills import (
    SKILL_BATCHES,
    SKILL_REGISTRY,
    build_skills_catalog,
    model_to_dict,
)
from AiLearning.skills.business_model import ModelingContext

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class TestCaseDesignAgent(BaseAgent):
    """技能驱动的用例设计 Agent。

    模拟人工流程：掌握业务知识 → 选择测试维度 → 提炼测试点 → 展开完整用例。

    execute() 参数：
      - question: 用户问题（如"为批量入驻功能设计测试用例"）
      - collection_name: 单个 KB 集合名（兼容旧调用）
      - collection_names: 多个 KB 集合名列表，支持跨库 RRF 融合检索
      - requirement_doc: 需求文档全文（实时上传，split 后直接使用）
    """

    @property
    def name(self) -> str:
        return "testcase_design"

    # ── execute ──────────────────────────────────────────────────

    def execute(self, question: str, **kwargs) -> AgentResponse:
        collection_names = kwargs.get("collection_names")
        collection_name = kwargs.get("collection_name")
        requirement_doc = kwargs.get("requirement_doc") or ""
        tech_doc = kwargs.get("tech_doc") or ""
        reference_cases = kwargs.get("reference_cases") or ""
        top_k = kwargs.get("top_k", 10)
        max_workers = kwargs.get("max_workers", 3)
        modeling: ModelingContext = kwargs.get("modeling", ModelingContext())

        # ── 1. 处理需求文档（合并需求文档与技术文档）──
        combined_requirement = f"{requirement_doc}\n\n---\n\n{tech_doc}" if tech_doc else requirement_doc
        requirement_context = self._process_requirement_doc(combined_requirement)

        client = get_client()
        impact_analysis = None
        regression_modules = ""
        model_rules = None

        if modeling.enabled and modeling.previous_model:
            # ═════════════════════════════════════════════════════
            # Phase -0.5: 影响分析
            # ═════════════════════════════════════════════════════
            try:
                impact_analysis = self._run_impact_analysis(
                    client,
                    previous_model=modeling.previous_model,
                    current_requirement=requirement_context,
                )
                regression_modules = " ".join(impact_analysis.get("regression_scope", []))
            except Exception:
                logger.exception("Phase -0.5: 影响分析失败，继续执行主流程")

            # Phase 0 用模型规则选 Skill
            rules = modeling.previous_model.get("rules", [])
            model_rules = "\n".join(
                f"- {r.get('name', '?')}: {r.get('condition', '?')} "
                f"[related_skill={r.get('related_skill', '?')}] "
                f"risk={r.get('risk', '?')}"
                for r in rules
            ) if rules else None

        # ── 2. RAG 检索（用 regression_scope 增强 query）──
        business_docs = []
        if regression_modules:
            business_query = f"{question} {regression_modules}".strip()
        else:
            business_query = f"{question}\n{combined_requirement[:500]}".strip()

        if collection_names:
            business_docs = retrieve_from_multiple_collections(business_query, collection_names, top_k=top_k)
        elif collection_name:
            business_docs = retrieve(business_query, collection_name, top_k=top_k)
        business_context = self._build_context(business_docs)

        main_context = (
            f"## 业务领域知识（你已掌握的背景）\n{business_context}\n\n"
        )

        all_test_points: list[dict] = []
        all_cases: list[dict] = []
        selected_names: list[str] = []
        batches: list[dict] = []

        # ═══════════════════════════════════════════════════════
        # Phase 0: Skill 选择
        # ═══════════════════════════════════════════════════════
        try:
            selected_names = self._select_skills(
                client, main_context, requirement_context, question,
                model_rules=model_rules,
            )
        except Exception:
            logger.exception("Phase 0: Skill 选择失败")
            raise

        # ═══════════════════════════════════════════════════════
        # Phase 1: 测试点生成（并行，按批次）
        # ═══════════════════════════════════════════════════════
        batches = self._build_batches(selected_names)
        if batches:
            with ThreadPoolExecutor(max_workers=min(max_workers, len(batches))) as executor:
                future_to_batch = {
                    executor.submit(
                        self._generate_test_points,
                        client, main_context, requirement_context, batch
                    ): batch
                    for batch in batches
                }
                for future in as_completed(future_to_batch):
                    batch = future_to_batch[future]
                    try:
                        points = future.result()
                        all_test_points.extend(points)
                    except Exception:
                        logger.exception("批次 %s 生成测试点失败", batch["group_name"])

        # ═══════════════════════════════════════════════════════
        # Phase 2: 用例展开（并行，每批 ≤5 个测试点避免输出截断）
        # ═══════════════════════════════════════════════════════
        if all_test_points:
            combined_rules = self._build_case_rules(selected_names)
            chunk_size = 5
            chunks = [
                (i, all_test_points[i:i + chunk_size])
                for i in range(0, len(all_test_points), chunk_size)
            ]
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_idx = {
                    executor.submit(
                        self._expand_test_cases,
                        client, main_context, requirement_context,
                        chunk, combined_rules, reference_cases
                    ): idx
                    for idx, chunk in chunks
                }
                results_by_idx: dict[int, list[dict]] = {}
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        results_by_idx[idx] = future.result()
                    except Exception:
                        logger.exception("测试点 chunk %d 展开失败", idx)

            for idx in sorted(results_by_idx):
                all_cases.extend(results_by_idx[idx])

            # 规范化：确保 expected/precondition 为字符串（LLM 可能输出数组）
            for case in all_cases:
                for field in ("expected", "precondition"):
                    if isinstance(case.get(field), list):
                        case[field] = "\n".join(
                            str(item) for item in case[field]
                        )

            answer = json.dumps(all_cases, ensure_ascii=False, indent=2)
        else:
            answer = "[]"

        return AgentResponse(
            answer=answer,
            agent_name=self.name,
            metadata={
                "retrieved_docs": len(business_docs),
                "selected_skills": selected_names,
                "test_points_count": len(all_test_points),
                "batches_used": len(batches),
                "impact_analysis": model_to_dict(impact_analysis) if impact_analysis else None,
            },
        )

    # ── execute_stream ────────────────────────────────────────────

    def execute_stream(self, question: str,
                       cancelled: threading.Event | None = None,
                       **kwargs) -> Generator[dict, None, None]:
        """SSE streaming 版用例生成，yield 进度事件 dict。

        每完成一个 phase 或并行任务 batch/chunk 即推送进度。
        外部可通过 cancelled Event 中止流，在 as_completed 检查点退出。
        保证必有终止事件：done / cancelled / error。
        """
        if cancelled is None:
            cancelled = threading.Event()

        collection_names = kwargs.get("collection_names")
        collection_name = kwargs.get("collection_name")
        requirement_doc = kwargs.get("requirement_doc") or ""
        tech_doc = kwargs.get("tech_doc") or ""
        reference_cases = kwargs.get("reference_cases") or ""
        top_k = kwargs.get("top_k", 10)
        max_workers = kwargs.get("max_workers", 3)
        modeling: ModelingContext = kwargs.get("modeling", ModelingContext())
        t0 = time_module.perf_counter()

        try:
            # ── 准备阶段 ──
            combined_requirement = f"{requirement_doc}\n\n---\n\n{tech_doc}" if tech_doc else requirement_doc
            requirement_context = self._process_requirement_doc(combined_requirement)

            client = get_client()
            impact_analysis = None
            regression_modules = ""
            model_rules = None

            # ═════════════════════════════════════════════════════
            # Phase -0.5: 影响分析（可选，失败不中断）
            # ═════════════════════════════════════════════════════
            if modeling.enabled and modeling.previous_model:
                if cancelled.is_set():
                    yield {"event": "cancelled", "data": {}}
                    return

                yield {"event": "phase_start", "phase": "phase-0.5", "data": {}}
                try:
                    impact_analysis = self._run_impact_analysis(
                        client,
                        previous_model=modeling.previous_model,
                        current_requirement=requirement_context,
                    )
                    regression_modules = " ".join(impact_analysis.get("regression_scope", []))
                    yield {
                        "event": "impact_done",
                        "data": {"analysis": model_to_dict(impact_analysis)},
                    }
                except Exception:
                    logger.exception("Phase -0.5: 影响分析失败，继续执行主流程")
                    yield {
                        "event": "impact_error",
                        "data": {"message": "影响分析失败，已跳过"},
                    }

                # 提取模型规则用于 Phase 0
                rules = modeling.previous_model.get("rules", [])
                if rules:
                    model_rules = "\n".join(
                        f"- {r.get('name', '?')}: {r.get('condition', '?')} "
                        f"[related_skill={r.get('related_skill', '?')}] "
                        f"risk={r.get('risk', '?')}"
                        for r in rules
                    )

            # ── RAG 检索（用 regression_scope 增强 query）──
            if regression_modules:
                business_query = f"{question} {regression_modules}".strip()
            else:
                business_query = f"{question}\n{combined_requirement[:500]}".strip()

            business_docs = []
            if collection_names:
                business_docs = retrieve_from_multiple_collections(business_query, collection_names, top_k=top_k)
            elif collection_name:
                business_docs = retrieve(business_query, collection_name, top_k=top_k)
            business_context = self._build_context(business_docs)

            main_context = f"## 业务领域知识（你已掌握的背景）\n{business_context}\n\n"

            # ═════════════════════════════════════════════════════
            # Phase 0: Skill 选择
            # ═════════════════════════════════════════════════════
            if cancelled.is_set():
                yield {"event": "cancelled", "data": {}}
                return

            yield {"event": "phase_start", "phase": "phase0", "data": {}}
            try:
                selected_names = self._select_skills(
                    client, main_context, requirement_context, question,
                    model_rules=model_rules,
                )
                yield {
                    "event": "phase_end", "phase": "phase0",
                    "data": {"selected_skills": selected_names},
                }
            except Exception:
                logger.exception("Phase 0: Skill 选择失败")
                yield {"event": "error", "data": {"message": "Skill 选择失败，请检查输入或重试"}}
                return

            # ═════════════════════════════════════════════════════
            # Phase 1: 测试点生成（并行，按批次）
            # ═════════════════════════════════════════════════════
            if cancelled.is_set():
                yield {"event": "cancelled", "data": {}}
                return

            all_test_points: list[dict] = []
            batches = self._build_batches(selected_names)

            if batches:
                yield {
                    "event": "phase_start", "phase": "phase1",
                    "data": {"batches": [b["group_name"] for b in batches]},
                }

                with ThreadPoolExecutor(max_workers=min(max_workers, len(batches))) as executor:
                    future_to_batch = {
                        executor.submit(
                            self._generate_test_points,
                            client, main_context, requirement_context, batch,
                        ): batch
                        for batch in batches
                    }
                    for future in as_completed(future_to_batch):
                        batch = future_to_batch[future]

                        if cancelled.is_set():
                            executor.shutdown(wait=False, cancel_futures=True)
                            break

                        try:
                            points = future.result()
                            all_test_points.extend(points)
                            yield {
                                "event": "batch_done", "phase": "phase1",
                                "data": {
                                    "batch": batch["group_name"],
                                    "test_points": len(points),
                                },
                            }
                        except Exception:
                            logger.exception("批次 %s 生成测试点失败", batch["group_name"])
                            yield {
                                "event": "batch_error", "phase": "phase1",
                                "data": {"batch": batch["group_name"]},
                            }

                if cancelled.is_set():
                    yield {"event": "cancelled", "data": {}}
                    return

                yield {
                    "event": "phase_end", "phase": "phase1",
                    "data": {"total_test_points": len(all_test_points)},
                }

            # ═════════════════════════════════════════════════════
            # Phase 2: 用例展开（并行，每批 ≤5 个测试点）
            # ═════════════════════════════════════════════════════
            if not all_test_points:
                yield {"event": "done", "data": {"answer": "[]", "metadata": {}}}
                return

            if cancelled.is_set():
                yield {"event": "cancelled", "data": {}}
                return

            combined_rules = self._build_case_rules(selected_names)
            chunk_size = 5
            chunks = [
                (i, all_test_points[i:i + chunk_size])
                for i in range(0, len(all_test_points), chunk_size)
            ]

            yield {
                "event": "phase_start", "phase": "phase2",
                "data": {"total_chunks": len(chunks)},
            }

            all_cases: list[dict] = []
            completed = 0

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_idx = {
                    executor.submit(
                        self._expand_test_cases,
                        client, main_context, requirement_context,
                        chunk, combined_rules, reference_cases,
                    ): idx
                    for idx, chunk in chunks
                }
                results_by_idx: dict[int, list[dict]] = {}

                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]

                    if cancelled.is_set():
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

                    try:
                        cases = future.result()
                        results_by_idx[idx] = cases
                        completed += 1
                        yield {
                            "event": "chunk_done", "phase": "phase2",
                            "data": {"chunk": completed, "total": len(chunks),
                                     "cases": len(cases)},
                        }
                    except Exception:
                        logger.exception("测试点 chunk %d 展开失败", idx)
                        completed += 1
                        yield {
                            "event": "chunk_error", "phase": "phase2",
                            "data": {"chunk": completed, "total": len(chunks)},
                        }

            if cancelled.is_set():
                yield {"event": "cancelled", "data": {}}
                return

            # 按索引排序合并
            for idx in sorted(results_by_idx):
                all_cases.extend(results_by_idx[idx])

            # 规范化 expected/precondition
            for case in all_cases:
                for field in ("expected", "precondition"):
                    if isinstance(case.get(field), list):
                        case[field] = "\n".join(str(item) for item in case[field])

            answer = json.dumps(all_cases, ensure_ascii=False, indent=2)
            elapsed = round(time_module.perf_counter() - t0, 1)
            yield {
                "event": "done",
                "data": {
                    "answer": answer,
                    "metadata": {
                        "selected_skills": selected_names,
                        "test_points_count": len(all_test_points),
                        "test_cases_count": len(all_cases),
                        "batches_used": len(batches),
                        "elapsed_seconds": elapsed,
                        "impact_analysis": model_to_dict(impact_analysis) if impact_analysis else None,
                    },
                },
            }

        except GeneratorExit:
            logger.info("execute_stream 客户端断开，流终止")
            yield {"event": "cancelled", "data": {}}
        except Exception as e:
            logger.exception("execute_stream 未预期异常")
            yield {"event": "error", "data": {"message": str(e)}}

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _process_requirement_doc(text: str) -> str:
        """将需求文档分片后拼接为上下文字符串。"""
        if not text or not text.strip():
            return "无需求文档"
        docs = [Document(page_content=text)]
        chunks = split_documents(docs, chunk_size=800, chunk_overlap=100)
        return "\n\n".join(c.page_content for c in chunks)

    @staticmethod
    def _parse_json_dict(raw: str) -> dict:
        """从 LLM 响应中安全提取 JSON 对象（3 层 fallback）。"""
        text = raw.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        logger.warning("无法从 LLM 响应中解析 JSON 对象: %s", text[:200])
        return {}

    @staticmethod
    def _parse_json_list(raw: str) -> list:
        """从 LLM 响应中安全提取 JSON 数组。"""
        text = raw.strip()
        # 1) 直接解析
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
        # 2) markdown code fence
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            try:
                result = json.loads(match.group(1))
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass
        # 3) 查找第一个 JSON 数组
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            try:
                result = json.loads(match.group(0))
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass
        logger.warning("无法从 LLM 响应中解析 JSON 数组: %s", text[:200])
        return []

    # ── Phase -0.5: 影响分析 ────────────────────────────────────

    def _run_impact_analysis(self, client, previous_model: dict,
                             current_requirement: str) -> dict:
        """基于已有业务模型，分析新需求影响范围。失败不中断主流程。"""
        prompt = DEFAULT_IMPACT_ANALYSIS_PROMPT.format(
            previous_model=json.dumps(previous_model, ensure_ascii=False, indent=2),
            current_requirement=current_requirement,
        )
        response = self._chat_with_log(
            client,
            messages=[
                {"role": "system", "content": DEFAULT_IMPACT_ANALYSIS_PROMPT.system},
                {"role": "user", "content": prompt},
            ],
            phase="phase-0.5",
            temperature=0,
            max_tokens=4096,
        )
        return self._parse_json_dict(response)

    # ── Phase 0: Skill 选择 ──────────────────────────────────────

    def _chat_with_log(self, client, messages, phase: str, **chat_kwargs) -> str:
        """调用 LLM 并记录 token 用量和耗时到日志。"""
        content, usage, elapsed = client.chat_with_usage(
            messages=messages, **chat_kwargs
        )
        logger.info(
            "[%s] elapsed=%.1fs tokens(in=%d out=%d total=%d)",
            phase,
            elapsed,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
            usage.get("total_tokens", 0),
        )
        return content

    def _select_skills(self, client, main_context: str,
                       requirement_context: str, question: str,
                       model_rules: str | None = None) -> list[str]:
        """选择适用测试维度。有 model_rules 时用业务模型规则，否则用 RAG context。"""
        if model_rules:
            prompt = DEFAULT_SKILL_SELECTION_PROMPT.format_with_model(
                model_rules=model_rules,
                requirement=requirement_context,
                question=question,
                skills_catalog=build_skills_catalog(),
            )
        else:
            prompt = DEFAULT_SKILL_SELECTION_PROMPT.format(
                context=main_context,
                requirement=requirement_context,
                question=question,
                skills_catalog=build_skills_catalog(),
            )
        response = self._chat_with_log(
            client,
            messages=[
                {"role": "system", "content": DEFAULT_SKILL_SELECTION_PROMPT.system},
                {"role": "user", "content": prompt},
            ],
            phase="phase0",
            temperature=0,
        )
        selected = self._parse_json_list(response)
        if not selected:
            logger.warning("Skill 选择返回空，使用全部 Skill 作为 fallback")
            return list(SKILL_REGISTRY.keys())
        return selected

    # ── Phase 1: 测试点生成 ──────────────────────────────────────

    def _build_batches(self, selected_names: list[str]) -> list[dict]:
        """将选中的 Skill 按预定义批次分组，跳过整批都未选中的批次。"""
        selected_set = set(selected_names)
        batches = []
        for batch_def in SKILL_BATCHES:
            active = [n for n in batch_def["skills"] if n in selected_set]
            if active:
                batches.append({
                    "group_name": batch_def["group_name"],
                    "skills": active,
                })
        return batches

    def _generate_test_points(self, client, main_context: str,
                               requirement_context: str, batch: dict) -> list:
        """对某一批次生成测试点。"""
        rules_parts = []
        for name in batch["skills"]:
            skill = SKILL_REGISTRY[name]
            rules_parts.append(f"### {skill.display_name}（{name}）\n{skill.test_point_rules}")
        batch_rules = "\n\n".join(rules_parts)

        prompt = DEFAULT_TESTPOINT_PROMPT.format(
            context=main_context,
            requirement=requirement_context,
            group_name=batch["group_name"],
            batch_rules=batch_rules,
        )
        response = self._chat_with_log(
            client,
            messages=[
                {"role": "system", "content": DEFAULT_TESTPOINT_PROMPT.system},
                {"role": "user", "content": prompt},
            ],
            phase="phase1",
            temperature=0.3,
        )
        return self._parse_json_list(response)

    # ── Phase 2: 用例展开 ────────────────────────────────────────

    def _build_case_rules(self, selected_names: list[str]) -> str:
        """汇总选中 Skill 的展开规则。"""
        parts = []
        for name in selected_names:
            if name in SKILL_REGISTRY:
                s = SKILL_REGISTRY[name]
                parts.append(f"### {s.display_name}\n{s.test_case_rules}")
        return "\n\n".join(parts)

    def _expand_test_cases(self, client, main_context: str,
                            requirement_context: str, test_points: list,
                            case_rules: str, reference_cases: str) -> list[dict]:
        """将一批测试点展开为完整用例，返回解析后的 dict 列表。"""
        prompt = DEFAULT_EXPANSION_PROMPT.format(
            context=main_context,
            requirement=requirement_context,
            test_points=json.dumps(test_points, ensure_ascii=False, indent=2),
            case_rules=case_rules,
            reference_cases=reference_cases,
        )
        response = self._chat_with_log(
            client,
            messages=[
                {"role": "system", "content": DEFAULT_EXPANSION_PROMPT.system},
                {"role": "user", "content": prompt},
            ],
            phase="phase2",
            temperature=0.2,
            max_tokens=8192,
        )
        return self._parse_json_list(response)

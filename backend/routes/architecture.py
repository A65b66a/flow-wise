from fastapi import APIRouter, HTTPException, Depends
from functools import lru_cache
from typing import Any, get_args, get_origin
import json

from backend.models.schemas import (
    ScopeRequest, ScopeResponse,
    ModeRequest, ModeResponse,
    AutoPilotInitRequest, AutoPilotInitResponse,
    AutoPilotCompleteRequest,
    GuidedBlockRequest, GuidedBlockResponse,
    GuidedCompleteRequest,
    SmartGuidedQuestionsRequest, SmartGuidedQuestionsResponse,
    SmartGuidedCompleteRequest,
    ConversationalMessageRequest, ConversationalMessageResponse,
    ConversationalReviewRequest, ConversationalReviewResponse,
    GuidedAnalysisRequest, GuidedAnalysisBlocks,
    GuidedLoopStartRequest, GuidedLoopStartResponse,
    GuidedLoopAnswerRequest, GuidedLoopAnswerResponse,
    GuidedLoopSessionState, GuidedLoopQuestion, AnalysisConfidence,
    ExpertLoopStartRequest, ExpertLoopStartResponse,
    ExpertLoopAnswerRequest, ExpertLoopAnswerResponse,
    ExpertLoopSessionState,
    SolutionOutput, ArchitectureSummary, ReasoningLog, CytoscapeElements,
    BusinessRequirements,
)
from backend.llm.claude_client import ClaudeClient
from backend.agents.scope_agent import ScopeAgent
from backend.agents.mode_selection_agent import ModeSelectionAgent
from backend.agents.auto_pilot_agent import AutoPilotAgent
from backend.agents.business_requirement_agent import BusinessRequirementAgent
from backend.agents.guided_agent import GuidedAgent
from backend.agents.smart_guided_agent import SmartGuidedAgent
from backend.agents.conversational_guided_agent import ConversationalGuidedAgent
from backend.agents.analysis_blocks_agent import AnalysisBlocksAgent
from backend.agents.auto_pilot_analysis_blocks_agent import AutoPilotAnalysisBlocksAgent
from backend.agents.analysis_confidence_agent import AnalysisConfidenceAgent
from backend.agents.question_loop_agent import QuestionLoopAgent
from backend.agents.expert_question_agent import ExpertQuestionAgent
from backend.agents.template_agent import TemplateAgent
from backend.agents.reasoning_agent import ReasoningAgent
from pydantic import ValidationError
from backend.utils.guided_loop_store import GuidedLoopStore

router = APIRouter(prefix="/api", tags=["architecture"])

_guided_loop_store = GuidedLoopStore(ttl_seconds=3600)
_expert_loop_store = GuidedLoopStore(ttl_seconds=3600)
_conversational_store = GuidedLoopStore(ttl_seconds=3600)

# Expert-mode field plan: ask only fields needing user decisions.
# Derived fields are computed in Python at finalization. Fixed defaults are set in Python.
_EXPERT_FIXED_DEFAULT_FIELDS: set[str] = set()
_EXPERT_DERIVED_FIELDS: set[str] = set()


def _literal_options(annotation: Any) -> list[str] | None:
    """
    Extract Literal options from typing annotations.
    Supports Literal["a","b"] and Optional[Literal[...]].
    """
    origin = get_origin(annotation)
    if origin is None:
        return None
    # Optional[T] is Union[T, NoneType]
    if origin is getattr(__import__("typing"), "Union", None):
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return _literal_options(args[0])
        return None
    if str(origin).endswith("Literal"):
        opts = []
        for a in get_args(annotation):
            if isinstance(a, str):
                opts.append(a)
        return opts or None
    return None


def _field_info_for_path(path: str) -> tuple[Any | None, Any | None]:
    """
    Return (field_info, annotation) for a dotted path in GuidedAnalysisBlocks.
    """
    from backend.models.schemas import GuidedAnalysisBlocks

    cur_model: Any = GuidedAnalysisBlocks
    parts = (path or "").split(".")
    for i, name in enumerate(parts):
        mf = getattr(cur_model, "model_fields", {}) or {}
        field = mf.get(name)
        if not field:
            return None, None
        ann = getattr(field, "annotation", None)
        if i == len(parts) - 1:
            return field, ann
        if ann is None or not hasattr(ann, "model_fields"):
            return None, None
        cur_model = ann
    return None, None


def _question_spec_for_field(field_path: str) -> tuple[str, list[str] | None]:
    """
    Map schema leaf type to GuidedLoopQuestion type + options.
    """
    _field, ann = _field_info_for_path(field_path)
    if ann is None:
        return "text", None

    # Lists (used for multi-select enums in schema)
    if get_origin(ann) in (list, list[str]):
        args = get_args(ann)
        if args:
            opts = _literal_options(args[0])
            if opts:
                return "multi_choice", opts
        return "text", None

    opts = _literal_options(ann)
    if opts:
        return "single_choice", opts

    if ann is bool:
        return "single_choice", ["Yes", "No"]
    if ann in (int, float):
        return "number", None
    return "text", None


def _build_expert_question(*, field_path: str, llm_text: str) -> GuidedLoopQuestion:
    q_type, opts = _question_spec_for_field(field_path)
    # No user-facing hardcoded text here: LLM provides wording.
    return GuidedLoopQuestion(field=field_path, text=str(llm_text or "").strip(), type=q_type, options=opts)


_EXPERT_VALIDATE_SYSTEM = """You are validating and normalizing a user's answer for an expert-mode architecture interview.
Return ONLY valid JSON. No markdown, no extra text.

You will receive:
- question: { field, type, options, text }
- user_reply: string (what the user typed)

Your job:
- Decide whether the reply can be accepted for the given question.
- If acceptable, normalize it to the correct value type for that question.
- If not acceptable/ambiguous/off-topic, ask ONE short clarification and do NOT accept a value.

Rules:
- No emojis. No cheerleading. Keep it calm and direct.
- Clarification text must be plain English with no special formatting (no bullet lists, no numbered lists, no "Choices:" labels).
- If the user reply indicates skip/unknown (e.g. "skip", "not sure", "don't know"), accept with value "__skipped__".
- If question.type is "single_choice" and options are provided:
  - Output value MUST be EXACTLY one of the option strings (internal tokens), not a paraphrase.
  - If you cannot confidently map the reply to exactly one option, ask a clarification instead.
- If question.type is "multi_choice" and options are provided:
  - Output value MUST be a JSON array of one or more option strings (internal tokens).
  - If the reply is unclear, ask a clarification instead.
- If question.type is "number":
  - Output value MUST be a JSON number.
- If question.type is "text":
  - Output value MUST be a JSON string (trimmed).

Output format (exactly one of these):
{"action":"accept","value": ...}
{"action":"clarify","text":"..."}"""

#
# NOTE: Expert loop extraction/validation is handled by ExpertQuestionAgent.
# We intentionally keep no additional hardcoded verify/clarify prompts here.


async def _llm_validate_expert_answer(
    *,
    client,
    question: GuidedLoopQuestion,
    user_reply: str,
) -> dict[str, Any]:
    payload = {
        "question": question.model_dump(),
        "user_reply": user_reply,
    }
    return await client.generate_json(
        system_prompt=_EXPERT_VALIDATE_SYSTEM,
        user_message=f"Validate and normalize from:\n\n{payload}",
        max_tokens=350,
    )


@lru_cache(maxsize=1)
def _client() -> ClaudeClient:
    try:
        return ClaudeClient()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _get_client():
    return _client()


# ── Health ──────────────────────────────────────────────────────────────────
@router.get("/health")
async def health():
    from backend.config import CLAUDE_API_KEY
    return {
        "status": "ok",
        "api_key_configured": bool(CLAUDE_API_KEY),
    }


# ── Scope ───────────────────────────────────────────────────────────────────
@router.post("/scope", response_model=ScopeResponse)
async def analyze_scope(req: ScopeRequest):
    try:
        client = _get_client()
        agent = ScopeAgent(client)
        result = await agent.run(user_input=req.user_input)
        if result.get("error") == "content_policy_violation":
            raise HTTPException(status_code=422, detail=result)
        return ScopeResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scope analysis failed: {exc}") from exc


# ── Mode ────────────────────────────────────────────────────────────────────
@router.post("/mode", response_model=ModeResponse)
async def select_mode(req: ModeRequest):
    try:
        client = _get_client()
        agent = ModeSelectionAgent(client)
        result = await agent.run(
            user_input=req.user_input,
            scope=req.scope.model_dump(),
        )
        return ModeResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Mode selection failed: {exc}") from exc


# ── Auto Mode ───────────────────────────────────────────────────────────────
@router.post("/auto/init", response_model=AutoPilotInitResponse)
async def auto_init(req: AutoPilotInitRequest):
    try:
        client = _get_client()
        agent = AutoPilotAgent(client)
        result = await agent.run(
            user_input=req.user_input,
            scope=req.scope.model_dump(),
        )
        return AutoPilotInitResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Auto-pilot init failed: {exc}") from exc


@router.post("/auto/complete", response_model=SolutionOutput)
async def auto_complete(req: AutoPilotCompleteRequest):
    try:
        client = _get_client()

        # Auto Pilot quick inputs are small; pre-normalize scale so the LLM can't mis-bucket numbers.
        users_num = _parse_users(str(req.quick_inputs.users))
        concurrent_users_band = _users_to_band(users_num)

        analysis_blocks = await _validated_analysis_blocks(
            client,
            user_input=req.user_input,
            scope=req.scope.model_dump(),
            previous_answers={
                "users": req.quick_inputs.users,
                "concurrent_users_band": concurrent_users_band,
                "visibility": req.quick_inputs.visibility,
                "uptime": req.quick_inputs.uptime,
                **(req.auto_pilot_init.confirmed_detections.model_dump() if req.auto_pilot_init else {}),
            },
            agent_kind="autopilot",
        )
        requirements = _analysis_blocks_to_requirements(analysis_blocks, req.scope.model_dump())

        tmpl_agent = TemplateAgent(client)
        template_result = await tmpl_agent.run(requirements=requirements)

        rsn_agent = ReasoningAgent(client)
        reasoning_result = await rsn_agent.run(
            template_result=template_result,
            requirements=requirements,
        )

        return _build_solution(template_result, reasoning_result, requirements, analysis_blocks=analysis_blocks)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Auto-pilot complete failed: {exc}") from exc


# ── Guided Mode ─────────────────────────────────────────────────────────────
@router.post("/guided/questions/{block}", response_model=GuidedBlockResponse)
async def guided_questions(block: int, req: GuidedBlockRequest):
    if block < 1 or block > 7:
        raise HTTPException(status_code=400, detail="Block must be between 1 and 7")
    try:
        client = _get_client()
        agent = GuidedAgent(client)
        result = await agent.get_block_questions(
            block=block,
            user_input=req.user_input,
            scope=req.scope.model_dump(),
            previous_answers=req.previous_answers,
        )
        return GuidedBlockResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Guided block {block} failed: {exc}") from exc


@router.post("/guided/complete", response_model=SolutionOutput)
async def guided_complete(req: GuidedCompleteRequest):
    try:
        client = _get_client()

        flat_answers = {}
        for block_answers in req.answers.values():
            if isinstance(block_answers, dict):
                flat_answers.update(block_answers)

        analysis_blocks = await _validated_analysis_blocks(
            client,
            user_input=req.user_input,
            scope=req.scope.model_dump(),
            previous_answers=flat_answers,
        )
        requirements = _analysis_blocks_to_requirements(analysis_blocks, req.scope.model_dump())

        tmpl_agent = TemplateAgent(client)
        template_result = await tmpl_agent.run(requirements=requirements)

        rsn_agent = ReasoningAgent(client)
        reasoning_result = await rsn_agent.run(
            template_result=template_result,
            requirements=requirements,
        )

        return _build_solution(template_result, reasoning_result, requirements, analysis_blocks=analysis_blocks)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Guided complete failed: {exc}") from exc


@router.post("/guided/smart/questions", response_model=SmartGuidedQuestionsResponse)
async def smart_guided_questions(req: SmartGuidedQuestionsRequest):
    """
    Smart Guided Mode — Step 1.
    Pre-fills what it can from scope, then generates the minimum questions
    (always 3-7) the user must answer to complete the 7 analysis blocks.
    """
    try:
        client = _get_client()
        agent = SmartGuidedAgent(client)
        result = await agent.run(
            user_input=req.user_input,
            scope=req.scope.model_dump(),
        )
        return SmartGuidedQuestionsResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Smart guided questions failed: {exc}") from exc


@router.post("/guided/smart/complete", response_model=SolutionOutput)
async def smart_guided_complete(req: SmartGuidedCompleteRequest):
    """
    Smart Guided Mode — Step 2.
    Takes user answers from the smart questions, fills all 7 analysis blocks,
    and generates the architecture solution.
    """
    try:
        client = _get_client()
        analysis_blocks = await _validated_analysis_blocks(
            client,
            user_input=req.user_input,
            scope=req.scope.model_dump(),
            previous_answers=req.answers,
        )
        requirements = _analysis_blocks_to_requirements(analysis_blocks, req.scope.model_dump())

        tmpl_agent = TemplateAgent(client)
        template_result = await tmpl_agent.run(requirements=requirements)

        rsn_agent = ReasoningAgent(client)
        reasoning_result = await rsn_agent.run(
            template_result=template_result,
            requirements=requirements,
        )

        return _build_solution(template_result, reasoning_result, requirements, analysis_blocks=analysis_blocks)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Smart guided complete failed: {exc}") from exc


@router.post("/guided/conversation/message", response_model=ConversationalMessageResponse)
async def conversational_message(req: ConversationalMessageRequest):
    """
    Conversational Guided Mode — send one message, get one question back.
    When the LLM has collected enough information, returns is_complete=true
    and collected_answers. Frontend then calls /guided/smart/complete.
    """
    try:
        client = _get_client()
        agent = ConversationalGuidedAgent(client)

        session_id = req.session_id or _conversational_store.new_session_id()
        session = _conversational_store.get(session_id) or {}

        result = await agent.run(
            user_input=req.user_input,
            scope=req.scope.model_dump(),
            conversation=[t.model_dump() for t in req.conversation],
            user_message=req.message,
            session=session,
            min_questions=req.min_questions,
        )
        _conversational_store.set(session_id, session)
        result["session_id"] = session_id
        return ConversationalMessageResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Conversational message failed: {exc}") from exc


# ── Conversational Guided Review (post-finalization) ─────────────────────────
@router.post("/guided/conversation/review", response_model=ConversationalReviewResponse)
async def conversational_review(req: ConversationalReviewRequest):
    """
    After conversational collection completes, validate/fill 7-block analysis.
    If still low confidence, return one targeted follow-up question.
    Frontend can loop this until status=complete, then call /guided/smart/complete.
    """
    try:
        client = _get_client()
        # Performance: avoid running a second LLM call for confidence scoring.
        # Instead, fill/validate blocks once and decide whether to ask ONE follow-up
        # using a small deterministic heuristic based on missing critical answers.
        blocks = await _validated_analysis_blocks(
            client,
            user_input=req.user_input,
            scope=req.scope.model_dump(),
            previous_answers=req.answers or {},
        )
        confidence = None

        # Single-shot clarification: if we already asked the combined clarification once,
        # do not ask more follow-ups. Proceed with what we have.
        if isinstance(req.answers, dict) and "followup_bundle" in req.answers:
            return ConversationalReviewResponse(
                status="complete",
                analysis_blocks=blocks,
                confidence=confidence,
            )

        # If we have enough explicit critical answers, we're done.
        if _has_minimum_review_coverage(req.answers or {}):
            return ConversationalReviewResponse(
                status="complete",
                analysis_blocks=blocks,
                confidence=confidence,
            )

        # Ask ONE combined clarification question (single-shot).
        # Use the ConversationalGuidedAgent to phrase the question (LLM), based on missing fields.
        needed_fields = _needed_followup_fields(req.answers or {})
        items = [_followup_label_for_field(f) for f in needed_fields if _followup_label_for_field(f)]
        if not items:
            items = ["any important detail you want me to assume"]
        conv_agent = ConversationalGuidedAgent(client)
        question = await conv_agent.build_review_question(
            user_input=req.user_input,
            scope=req.scope.model_dump(),
            items_to_clarify=items,
        )
        return ConversationalReviewResponse(
            status="questioning",
            question=GuidedLoopQuestion(**question),
            analysis_blocks=blocks,
            confidence=confidence,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Conversational review failed: {exc}") from exc


def _has_minimum_review_coverage(answers: dict) -> bool:
    """
    Deterministic "good enough" check to avoid a slow confidence-scoring LLM call.
    We only need enough info to generate a reasonable architecture; anything else can be inferred.
    """
    required = (
        "analysis_block_4_traffic_and_scale.concurrent_users_band",
        "analysis_block_6_access_and_security.public_facing",
        "analysis_block_5_availability.sla_target",
        "analysis_block_6_access_and_security.compliance_requirements",
    )
    return all(k in answers for k in required)


def _pick_followup_field(answers: dict, confidence: dict) -> str:
    low = confidence.get("low_confidence_fields") or []
    if isinstance(low, list):
        for f in low:
            if isinstance(f, str) and f and f not in answers:
                return f
    # fallback to top-impact critical fields
    for f in (
        "analysis_block_4_traffic_and_scale.concurrent_users_band",
        "analysis_block_6_access_and_security.public_facing",
        "analysis_block_5_availability.sla_target",
        "analysis_block_6_access_and_security.compliance_requirements",
        "analysis_block_1_application_identity.database_engine",
    ):
        if f not in answers:
            return f
    return "analysis_block_4_traffic_and_scale.concurrent_users_band"


def _needed_followup_fields(answers: dict) -> list[str]:
    needed: list[str] = []
    for f in (
        "analysis_block_4_traffic_and_scale.concurrent_users_band",
        "analysis_block_6_access_and_security.public_facing",
        "analysis_block_5_availability.sla_target",
        "analysis_block_6_access_and_security.compliance_requirements",
        "analysis_block_1_application_identity.database_engine",
    ):
        if f not in answers:
            needed.append(f)

    return needed[:3]


def _followup_label_for_field(field: str) -> str | None:
    mapping = {
        "analysis_block_4_traffic_and_scale.concurrent_users_band": "rough peak usage (how many people at once during busy times)",
        "analysis_block_6_access_and_security.public_facing": "who it’s for (internal only vs public vs both)",
        "analysis_block_5_availability.sla_target": "how important uptime is (is a 1-hour outage okay or a big problem?)",
        "analysis_block_6_access_and_security.compliance_requirements": "any compliance expectations (e.g., GDPR/PCI/HIPAA/SOC2) or none",
        "analysis_block_1_application_identity.database_engine": "what the data looks like (normal app records vs analytics/search/time-series)",
    }
    return mapping.get(field)


def _followup_question_for_field(field: str) -> dict:
    # Keep these chat-friendly; UI can render as plain text.
    mapping = {
        "analysis_block_4_traffic_and_scale.concurrent_users_band": {
            "field": field,
            "text": "Quick clarification (so I don’t guess): roughly how many people will be active at the same time at peak?",
            "type": "number",
            "options": None,
        },
        "analysis_block_6_access_and_security.public_facing": {
            "field": field,
            "text": "Quick clarification (so I don’t assume): is this internal-only, public on the internet, or both?",
            "type": "single_choice",
            "options": ["Internal only", "Public internet", "Both public and internal"],
        },
        "analysis_block_5_availability.sla_target": {
            "field": field,
            "text": "Quick clarification: if the app went down for an hour, would that be acceptable, painful, or business‑critical?",
            "type": "single_choice",
            "options": [
                "99% — some downtime acceptable",
                "99.9% — a few hours/year",
                "99.99% — near zero downtime",
            ],
        },
        "analysis_block_6_access_and_security.compliance_requirements": {
            "field": field,
            "text": "Quick clarification: do you have any compliance needs (GDPR, PCI, HIPAA, SOC2), or none?",
            "type": "multi_choice",
            "options": [
                "None",
                "EU users / GDPR",
                "Payment card data (PCI-DSS)",
                "Health / medical records (HIPAA)",
                "SOC2 requirement",
            ],
        },
        "analysis_block_1_application_identity.database_engine": {
            "field": field,
            "text": "Quick clarification: is this mostly normal app records, or more analytics/search/time‑series data?",
            "type": "single_choice",
            "options": ["Transactional app records", "Analytics-heavy", "Search-heavy", "Time-series metrics"],
        },
    }
    return mapping.get(field) or {
        "field": field,
        "text": "One quick clarification so I don’t assume wrong—what should we assume here?",
        "type": "text",
        "options": None,
    }
# ── Guided Loop Mode (confidence-driven, multi-turn) ─────────────────────────
@router.post("/guided/loop/start", response_model=GuidedLoopStartResponse)
async def guided_loop_start(req: GuidedLoopStartRequest):
    """
    Start a new guided-loop session:
    - Run analysis (7 blocks + confidence) with no answers
    - Run question agent to pick first question (or stop)
    - Persist session in store
    """
    try:
        client = _get_client()
        session_id = _guided_loop_store.new_session_id()

        # Defensive: ensure the session asks at least one question if allowed.
        # Sometimes the LLM question agent can still return {"action":"stop"} even when
        # we want to start a questioning flow.
        max_q = max(0, int(req.max_questions or 0))

        analysis_agent = AnalysisConfidenceAgent(client)
        analysis_raw = await analysis_agent.run(
            user_input=req.user_input,
            scope=req.scope.model_dump(),
            answers={},
        )

        confidence = analysis_raw.get("confidence", {})
        blocks_raw = {k: v for k, v in analysis_raw.items() if k != "confidence"}

        q_agent = QuestionLoopAgent(client)
        q_raw = await q_agent.run(
            user_input=req.user_input,
            answers={},
            analysis_blocks=blocks_raw,
            confidence=confidence,
            question_count=0,
            max_questions=max_q,
        )

        if max_q > 0 and q_raw.get("action") == "stop":
            q_raw = {
                "action": "ask",
                "question": {
                    "field": "analysis_block_4_traffic_and_scale.concurrent_users_band",
                    "text": "Roughly how many people will be using the app at the same time at peak?",
                    "type": "number",
                    "options": None,
                },
            }

        state = GuidedLoopSessionState(
            session_id=session_id,
            user_input=req.user_input,
            scope=req.scope,
            answers={},
            question_count=0,
            max_questions=max_q,
            analysis_blocks=GuidedAnalysisBlocks(**blocks_raw),
            confidence=AnalysisConfidence(**confidence) if confidence else None,
            status="questioning",
        )

        if q_raw.get("action") == "stop":
            state.status = "complete"
            _guided_loop_store.set(session_id, state.model_dump())
            return GuidedLoopStartResponse(
                session_id=session_id,
                status="complete",
                analysis_blocks=state.analysis_blocks,
                confidence=state.confidence,
            )

        question = q_raw.get("question") or {}
        _guided_loop_store.set(session_id, state.model_dump())
        return GuidedLoopStartResponse(
            session_id=session_id,
            status="questioning",
            question=GuidedLoopQuestion(**question),
            question_number=1,
            analysis_blocks=state.analysis_blocks,
            confidence=state.confidence,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Guided loop start validation failed: {exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Guided loop start failed: {exc}") from exc


@router.post("/guided/loop/answer", response_model=GuidedLoopAnswerResponse)
async def guided_loop_answer(req: GuidedLoopAnswerRequest):
    """
    Submit one answer:
    - Update session answers
    - Run analysis (7 blocks + confidence)
    - Run question agent (stop vs ask next)
    - Persist session
    """
    try:
        raw_state = _guided_loop_store.get(req.session_id)
        if not raw_state:
            raise HTTPException(status_code=404, detail="Session not found")

        state = GuidedLoopSessionState(**raw_state)
        if state.status == "complete":
            return GuidedLoopAnswerResponse(
                session_id=state.session_id,
                status="complete",
                analysis_blocks=state.analysis_blocks,
                confidence=state.confidence,
            )

        # update
        state.answers[req.field] = req.value
        state.question_count += 1

        client = _get_client()
        analysis_agent = AnalysisConfidenceAgent(client)
        analysis_raw = await analysis_agent.run(
            user_input=state.user_input,
            scope=state.scope.model_dump(),
            answers=state.answers,
        )
        confidence = analysis_raw.get("confidence", {})
        blocks_raw = {k: v for k, v in analysis_raw.items() if k != "confidence"}
        state.analysis_blocks = GuidedAnalysisBlocks(**blocks_raw)
        state.confidence = AnalysisConfidence(**confidence) if confidence else None

        q_agent = QuestionLoopAgent(client)
        q_raw = await q_agent.run(
            user_input=state.user_input,
            answers=state.answers,
            analysis_blocks=blocks_raw,
            confidence=confidence,
            question_count=state.question_count,
            max_questions=state.max_questions,
        )

        if q_raw.get("action") == "stop":
            state.status = "complete"
            _guided_loop_store.set(state.session_id, state.model_dump())
            return GuidedLoopAnswerResponse(
                session_id=state.session_id,
                status="complete",
                analysis_blocks=state.analysis_blocks,
                confidence=state.confidence,
            )

        question = q_raw.get("question") or {}
        _guided_loop_store.set(state.session_id, state.model_dump())
        return GuidedLoopAnswerResponse(
            session_id=state.session_id,
            status="questioning",
            question=GuidedLoopQuestion(**question),
            question_number=state.question_count + 1,
            analysis_blocks=state.analysis_blocks,
            confidence=state.confidence,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Guided loop answer validation failed: {exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Guided loop answer failed: {exc}") from exc


@router.get("/guided/loop/session/{session_id}", response_model=GuidedLoopSessionState)
async def guided_loop_session(session_id: str):
    raw_state = _guided_loop_store.get(session_id)
    if not raw_state:
        raise HTTPException(status_code=404, detail="Session not found")
    return GuidedLoopSessionState(**raw_state)


async def _expert_finalize(
    client: ClaudeClient,
    state: "ExpertLoopSessionState",
    *,
    store: "GuidedLoopStore",
) -> "ExpertLoopAnswerResponse":
    """Run the full analysis pipeline once expert questioning is done and return a complete response."""
    state.status = "complete"
    blocks = await _validated_analysis_blocks(
        client,
        user_input=state.user_input,
        scope=state.scope.model_dump(),
        previous_answers=state.answers,
        agent_kind="expert",
    )
    state.analysis_blocks = blocks
    requirements = _analysis_blocks_to_requirements(blocks, state.scope.model_dump())

    tmpl_agent = TemplateAgent(client)
    template_result = await tmpl_agent.run(requirements=requirements)

    rsn_agent = ReasoningAgent(client)
    reasoning_result = await rsn_agent.run(
        template_result=template_result,
        requirements=requirements,
    )

    solution = _build_solution(template_result, reasoning_result, requirements, analysis_blocks=blocks)
    store.set(state.session_id, state.model_dump())
    print(f"[EXPERT FINALIZE] Node analysis complete for session {state.session_id}")

    return ExpertLoopAnswerResponse(
        session_id=state.session_id,
        status="complete",
        analysis_blocks=blocks,
        confidence=state.confidence,
        solution=solution,
    )


# ── Expert Loop Mode (ask many fields, min 20) ───────────────────────────────
@router.post("/expert/loop/start", response_model=ExpertLoopStartResponse)
async def expert_loop_start(req: ExpertLoopStartRequest):
    """
    Expert loop:
    - Runs analysis (7 blocks + confidence) each turn
    - Asks many questions, but will not stop before min_questions
    - Stores session server-side
    """
    try:
        client = _get_client()
        session_id = _expert_loop_store.new_session_id()

        state = ExpertLoopSessionState(
            session_id=session_id,
            user_input=req.user_input,
            scope=req.scope,
            conversation=[],
            answers={},
            question_count=0,
            min_questions=int(req.min_questions or 20),
            current_question=None,
            analysis_blocks=None,
            confidence=None,
            status="questioning",
        )

        q_driver = ExpertQuestionAgent(client)
        turn = await q_driver.run(
            user_input=req.user_input,
            scope=req.scope.model_dump(),
            answers=state.answers,
            conversation=[],
            last_question_field=None,
            last_question_text=None,
            user_reply="",
            question_count=0,
        )

        if (turn or {}).get("status") == "complete":
            state.answers = dict((turn or {}).get("answers") or {})
            print(f"[EXPERT START] LLM returned status=complete on first turn")
            resp = await _expert_finalize(client, state, store=_expert_loop_store)
            return ExpertLoopStartResponse(
                session_id=session_id,
                status="complete",
                analysis_blocks=resp.analysis_blocks,
                confidence=resp.confidence,
                solution=resp.solution,
            )

        extracted = (turn or {}).get("extracted") or []
        if isinstance(extracted, list):
            for item in extracted:
                if isinstance(item, dict) and item.get("field"):
                    state.answers[str(item["field"])] = item.get("value")

        # DEBUG: Log answers after extraction
        print(f"[EXPERT START] Extracted values: {json.dumps(extracted, indent=2)}")
        print(f"[EXPERT START] Answers after turn 0:")
        print(json.dumps(state.answers, indent=2, default=str))

        next_field = str((turn or {}).get("next_field") or "")
        next_question_text = str((turn or {}).get("next_question") or "")
        question = GuidedLoopQuestion(field=next_field, text=next_question_text, type="text", options=None)
        state.current_question = question
        state.conversation.append({"role": "assistant", "content": question.text})
        
        # DEBUG: Log what we're about to save
        to_save = state.model_dump()
        print(f"[EXPERT START] About to save session {session_id}")
        print(f"[EXPERT START] to_save.answers: {json.dumps(to_save.get('answers'), indent=2, default=str)}")
        print(f"[EXPERT START] to_save keys: {list(to_save.keys())}")
        
        _expert_loop_store.set(session_id, to_save)
        print(f"[EXPERT START] Session {session_id} saved to store with answers: {list(state.answers.keys())}")
        return ExpertLoopStartResponse(
            session_id=session_id,
            status="questioning",
            question=question,
            question_number=1,
            analysis_blocks=None,
            confidence=None,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Expert loop start validation failed: {exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Expert loop start failed: {exc}") from exc


@router.post("/expert/loop/answer", response_model=ExpertLoopAnswerResponse)
async def expert_loop_answer(req: ExpertLoopAnswerRequest):
    try:
        raw_state = _expert_loop_store.get(req.session_id)
        if not raw_state:
            raise HTTPException(status_code=404, detail="Session not found")

        # DEBUG: Log what we're loading from store
        print(f"[EXPERT ANSWER] Session {req.session_id} loaded from store")
        print(f"[EXPERT ANSWER] raw_state keys: {list(raw_state.keys())}")
        print(f"[EXPERT ANSWER] raw_state.answers: {raw_state.get('answers')}")
        print(f"[EXPERT ANSWER] Loaded answers from store (before processing):")
        print(json.dumps(raw_state.get("answers", {}), indent=2, default=str))

        state = ExpertLoopSessionState(**raw_state)
        print(f"[EXPERT ANSWER] After creating state obj, state.answers: {json.dumps(state.answers, indent=2, default=str)}")
        if state.status == "complete":
            return ExpertLoopAnswerResponse(
                session_id=state.session_id,
                status="complete",
                analysis_blocks=state.analysis_blocks,
                confidence=state.confidence,
            )

        current_q = state.current_question
        if current_q and req.field != current_q.field:
            raise HTTPException(status_code=400, detail="Field does not match current question")

        def _as_text(v: Any) -> str:
            return str(v or "").strip()

        client = _get_client()
        user_msg = _as_text(req.value)
        # Append user message to conversation for memory/deviation detection.
        state.conversation.append({"role": "user", "content": user_msg})

        # DEBUG: Log state before calling LLM
        print(f"[EXPERT ANSWER] Calling LLM for turn {int(state.question_count or 0)} with answers:")
        print(json.dumps(state.answers, indent=2, default=str))

        q_driver = ExpertQuestionAgent(client)
        turn = await q_driver.run(
            user_input=state.user_input,
            scope=state.scope.model_dump(),
            answers=state.answers,
            conversation=state.conversation,
            last_question_field=current_q.field if current_q else req.field,
            last_question_text=current_q.text if current_q else None,
            user_reply=user_msg,
            question_count=int(state.question_count or 0),
        )

        extracted = (turn or {}).get("extracted") or []
        if isinstance(extracted, list):
            for item in extracted:
                if isinstance(item, dict) and item.get("field"):
                    state.answers[str(item["field"])] = item.get("value")

        # DEBUG: Log answers after extraction
        print(f"[EXPERT ANSWER] Extracted values: {json.dumps(extracted, indent=2)}")
        print(f"[EXPERT ANSWER] Answers after turn {int(state.question_count or 0)}:")
        print(json.dumps(state.answers, indent=2, default=str))

        # If the LLM signals completion, only finalize if min_questions floor is met.
        if (turn or {}).get("status") == "complete":
            state.answers = dict((turn or {}).get("answers") or state.answers)
            if state.question_count >= state.min_questions:
                print(f"[EXPERT ANSWER] LLM complete on turn {state.question_count} — finalizing")
                return await _expert_finalize(client, state, store=_expert_loop_store)
            print(f"[EXPERT ANSWER] LLM complete but only {state.question_count}/{state.min_questions} questions asked — continuing")

        state.question_count += 1

        next_field = str((turn or {}).get("next_field") or "")
        next_question_text = str((turn or {}).get("next_question") or "")

        # If the LLM returned an empty question it has run out of fields — finalize if floor is met.
        if not next_field or not next_question_text:
            if state.question_count >= state.min_questions:
                print(f"[EXPERT ANSWER] No more fields on turn {state.question_count} — finalizing")
                return await _expert_finalize(client, state, store=_expert_loop_store)
            print(f"[EXPERT ANSWER] No more fields but only {state.question_count}/{state.min_questions} asked — LLM will re-ask")

        question = GuidedLoopQuestion(field=next_field, text=next_question_text, type="text", options=None)
        state.current_question = question
        state.conversation.append({"role": "assistant", "content": question.text})
        
        # DEBUG: Log what we're about to save
        to_save = state.model_dump()
        print(f"[EXPERT ANSWER] About to save session {state.session_id} (after turn {state.question_count})")
        print(f"[EXPERT ANSWER] to_save.answers: {json.dumps(to_save.get('answers'), indent=2, default=str)}")
        print(f"[EXPERT ANSWER] to_save keys: {list(to_save.keys())}")
        
        _expert_loop_store.set(state.session_id, to_save)
        print(f"[EXPERT ANSWER] Session {state.session_id} saved to store with answers: {list(state.answers.keys())}")
        print(f"[EXPERT ANSWER] Answers saved: {json.dumps(state.answers, indent=2, default=str)}")
        return ExpertLoopAnswerResponse(
            session_id=state.session_id,
            status="questioning",
            question=question,
            question_number=state.question_count + 1,
            analysis_blocks=None,
            confidence=None,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Expert loop answer validation failed: {exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Expert loop answer failed: {exc}") from exc


@router.get("/expert/loop/session/{session_id}", response_model=ExpertLoopSessionState)
async def expert_loop_session(session_id: str):
    raw_state = _expert_loop_store.get(session_id)
    if not raw_state:
        raise HTTPException(status_code=404, detail="Session not found")
    return ExpertLoopSessionState(**raw_state)


@router.post("/guided/analysis", response_model=GuidedAnalysisBlocks)
async def guided_analysis(req: GuidedAnalysisRequest):
    """
    Generate the 7-block analysis JSON (filled enum values) from user input,
    scope, and any previously answered guided questions.
    """
    try:
        client = _get_client()
        return await _validated_analysis_blocks(
            client,
            user_input=req.user_input,
            scope=req.scope.model_dump(),
            previous_answers=req.answers,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Guided analysis failed: {exc}") from exc


# ── Helpers ──────────────────────────────────────────────────────────────────
def _build_solution(
    template_result: dict,
    reasoning_result: dict,
    requirements: dict,
    analysis_blocks: GuidedAnalysisBlocks | None = None,
) -> SolutionOutput:
    summary_data = reasoning_result.get("summary", {})
    reasoning_data = reasoning_result.get("reasoning", {})
    cy_raw = template_result.get("cytoscape_elements", {"nodes": [], "edges": []})

    return SolutionOutput(
        template_id=template_result["template_id"],
        template_name=template_result["template_name"],
        summary=ArchitectureSummary(
            architecture_type=summary_data.get("architecture_type", template_result["template_name"]),
            components=summary_data.get("components", []),
            estimated_monthly_cost=summary_data.get("estimated_monthly_cost", "N/A"),
            deployment_complexity=summary_data.get("deployment_complexity", "Medium"),
            key_highlights=summary_data.get("key_highlights", []),
        ),
        reasoning=ReasoningLog(
            template_selection=reasoning_data.get("template_selection", ""),
            component_choices=reasoning_data.get("component_choices", []),
            trade_offs=reasoning_data.get("trade_offs", []),
            alternatives_considered=reasoning_data.get("alternatives_considered", []),
        ),
        configuration=template_result.get("configuration", {}),
        cytoscape_elements=CytoscapeElements(
            nodes=cy_raw.get("nodes", []),
            edges=cy_raw.get("edges", []),
        ),
        requirements=BusinessRequirements(**requirements),
        analysis_blocks=analysis_blocks,
    )


def _analysis_blocks_to_requirements(blocks: GuidedAnalysisBlocks, scope: dict) -> dict:
    b1 = blocks.analysis_block_1_application_identity
    b2 = blocks.analysis_block_2_architecture_pattern
    b4 = blocks.analysis_block_4_traffic_and_scale
    b5 = blocks.analysis_block_5_availability
    b6 = blocks.analysis_block_6_access_and_security

    users_map = {
        "under_100": 50,
        "100_to_1k": 500,
        "1k_to_10k": 5000,
        "10k_to_100k": 50000,
        "100k_plus": 200000,
    }
    users = users_map.get(b4.concurrent_users_band, 1000)

    uptime_map = {"best_effort": "99%", "99.9": "99.9%", "99.99": "99.99%"}
    uptime = uptime_map.get(b5.sla_target, "99.9%")

    classification = "internal"
    if b6.handles_sensitive_data or any(x in (b6.sensitive_data_types or []) for x in ("payments", "health_records", "financial_data", "pii")):
        classification = "confidential"

    tier = "growing"
    if b7 := blocks.analysis_block_7_resource_sizing_and_budget:
        if (b7.monthly_budget_ceiling_usd or 0) >= 10000:
            tier = "enterprise"
        elif (b7.monthly_budget_ceiling_usd or 0) > 0 and (b7.monthly_budget_ceiling_usd or 0) < 500:
            tier = "startup"

    return {
        "app_type": b1.app_type,
        "scale": {
            "concurrent_users": int(users),
            "requests_per_second": max(1, int(users) // 10),
            "storage_tb": 0.1,
            "growth_rate": "growing" if b4.expected_growth else "steady",
        },
        "availability": {
            "uptime_requirement": uptime,
            "rto_minutes": 15 if b5.sla_target == "99.99" else 60,
            "rpo_minutes": 30,
            "multi_az": bool(b5.multi_az),
        },
        "network": {
            "internet_facing": bool(b6.public_facing),
            "cdn_required": bool(b6.public_facing and users > 1000),
            "multi_region": bool(b5.disaster_recovery_required),
        },
        "security": {
            "authentication": True,
            "data_classification": classification,
            "compliance": [c for c in (b6.compliance_requirements or []) if c != "none"],
        },
        "budget": {
            "tier": tier,
            "monthly_estimate_usd": int(blocks.analysis_block_7_resource_sizing_and_budget.monthly_budget_ceiling_usd or 0),
            "cost_optimization": "balanced",
        },
        "stack": scope.get("stack", []),
        "derived_requirements": [
            f"Derived from 7-block analysis (pattern={b2.pattern}, scale={b4.resolved_scale}, sla={b5.sla_target})"
        ],
    }


async def _validated_analysis_blocks(
    client: ClaudeClient,
    *,
    user_input: str,
    scope: dict,
    previous_answers: dict,
    max_attempts: int = 2,
    agent_kind: str = "default",
) -> GuidedAnalysisBlocks:
    """
    Ask the LLM for analysis blocks and validate via Pydantic.
    If validation fails, retry once with the validation error so the LLM can correct enums/types.
    This avoids hardcoded fixups while keeping the server resilient.
    """
    agent = AutoPilotAnalysisBlocksAgent(client) if agent_kind == "autopilot" else AnalysisBlocksAgent(client)
    last_err: Exception | None = None
    raw: dict = {}
    for attempt in range(max_attempts):
        raw = await agent.run(user_input=user_input, scope=scope, previous_answers=previous_answers)
        try:
            return GuidedAnalysisBlocks(**raw)
        except ValidationError as exc:
            last_err = exc
            # Ask the model to correct its previous JSON exactly.
            previous_answers = {
                **(previous_answers or {}),
                "_validation_error": str(exc),
                "_instructions": "Your previous JSON failed schema validation. Output corrected JSON ONLY, using allowed enum values and correct types.",
                "_previous_json": raw,
            }
    raise HTTPException(status_code=500, detail=f"Analysis block validation failed: {last_err}")


def _guided_answers_to_requirements(answers: dict, scope: dict) -> dict:
    users_str = str(answers.get("users_count", answers.get("concurrent_users", "1000")))
    users_num = _parse_users(users_str)

    uptime_map = {
        "hours": "99%",
        "30 minutes": "99.9%",
        "minutes": "99.99%",
        "cannot tolerate": "99.999%",
    }
    downtime_raw = str(answers.get("downtime_tolerance", "")).lower()
    uptime = next((v for k, v in uptime_map.items() if k in downtime_raw), "99.9%")

    internet = str(answers.get("internet_access", "yes")).lower()
    internet_facing = "internal" not in internet

    sensitive = answers.get("sensitive_data", [])
    if isinstance(sensitive, str):
        sensitive = [sensitive]
    has_pii = any("personal" in s.lower() or "pii" in s.lower() for s in sensitive)
    has_payment = any("payment" in s.lower() or "pci" in s.lower() for s in sensitive)
    has_health = any("health" in s.lower() or "hipaa" in s.lower() for s in sensitive)

    compliance = []
    if has_payment:
        compliance.append("PCI-DSS")
    if has_health:
        compliance.append("HIPAA")

    budget_map = {
        "<$100": ("startup", 50),
        "$100-$500": ("startup", 300),
        "$500-$2000": ("growing", 1250),
        "$2000-$10000": ("growing", 6000),
        ">$10000": ("enterprise", 15000),
    }
    budget_raw = answers.get("monthly_budget", "$500-$2000")
    tier, estimate = budget_map.get(budget_raw, ("growing", 1250))

    return {
        "app_type": scope.get("app_type", "web"),
        "scale": {
            "concurrent_users": users_num,
            "requests_per_second": max(1, users_num // 10),
            "storage_tb": 0.1,
            "growth_rate": "growing",
        },
        "availability": {
            "uptime_requirement": uptime,
            "rto_minutes": 60 if "99%" == uptime else 15,
            "rpo_minutes": 30,
            "multi_az": users_num > 500 or uptime in ("99.99%", "99.999%"),
        },
        "network": {
            "internet_facing": internet_facing,
            "cdn_required": internet_facing and users_num > 1000,
            "multi_region": False,
        },
        "security": {
            "authentication": True,
            "data_classification": "confidential" if (has_pii or has_payment or has_health) else "internal",
            "compliance": compliance,
        },
        "budget": {
            "tier": tier,
            "monthly_estimate_usd": estimate,
            "cost_optimization": "balanced",
        },
        "stack": scope.get("stack", []),
        "derived_requirements": [f"Derived from guided interview with {len(answers)} answers"],
    }


def _parse_users(raw: str) -> int:
    raw = raw.lower().replace(",", "").strip()
    if "m" in raw:
        try:
            return int(float(raw.replace("m", "")) * 1_000_000)
        except ValueError:
            pass
    if "k" in raw:
        try:
            return int(float(raw.replace("k", "")) * 1_000)
        except ValueError:
            pass
    import re
    nums = re.findall(r"\d+", raw)
    return int(nums[0]) if nums else 1000


def _users_to_band(users_num: int) -> str:
    if users_num < 100:
        return "under_100"
    if users_num < 1000:
        return "100_to_1k"
    if users_num < 10_000:
        return "1k_to_10k"
    if users_num < 100_000:
        return "10k_to_100k"
    return "100k_plus"



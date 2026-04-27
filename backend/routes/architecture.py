from fastapi import APIRouter, HTTPException
from functools import lru_cache

from backend.models.schemas import (
    ScopeRequest, ScopeResponse,
    ModeRequest, ModeResponse,
    AutoPilotInitRequest, AutoPilotInitResponse,
    AutoPilotCompleteRequest,
    GuidedBlockRequest, GuidedBlockResponse,
    GuidedCompleteRequest,
    ExpertQuestionsRequest, ExpertQuestionsResponse,
    ExpertCompleteRequest,
    SolutionOutput, ArchitectureSummary, ReasoningLog, CytoscapeElements,
    BusinessRequirements,
)
from backend.llm.claude_client import ClaudeClient
from backend.agents.scope_agent import ScopeIdentificationAgent
from backend.agents.mode_selection_agent import ModeSelectionAgent
from backend.agents.auto_pilot_agent import AutoPilotAgent
from backend.agents.business_requirement_agent import BusinessRequirementAgent
from backend.agents.guided_agent import GuidedAgent
from backend.agents.expert_agent import ExpertAgent
from backend.agents.template_agent import TemplateAgent
from backend.agents.reasoning_agent import ReasoningAgent

router = APIRouter(prefix="/api", tags=["architecture"])


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
        agent = ScopeIdentificationAgent(client)
        result = await agent.run(user_input=req.user_input)
        
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
        
        if result.get("error"):
            raise HTTPException(
                status_code=422,
                detail=result.get("message", "Input blocked: disallowed content detected.")
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
        
        if result.get("error"):
            raise HTTPException(
                status_code=422,
                detail=result.get("message", "Input blocked: disallowed content detected.")
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

        biz_agent = BusinessRequirementAgent(client)
        requirements = await biz_agent.run(
            user_input=req.user_input,
            scope=req.scope.model_dump(),
            auto_pilot_init=req.auto_pilot_init.model_dump(),
            quick_inputs=req.quick_inputs.model_dump(),
        )
        
        if isinstance(requirements, dict) and requirements.get("error"):
            raise HTTPException(
                status_code=422,
                detail=requirements.get("message", "Input blocked: disallowed content detected.")
            )

        tmpl_agent = TemplateAgent(client)
        template_result = await tmpl_agent.run(requirements=requirements)

        rsn_agent = ReasoningAgent(client)
        reasoning_result = await rsn_agent.run(
            template_result=template_result,
            requirements=requirements,
        )

        return _build_solution(template_result, reasoning_result, requirements)
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
        
        if result.get("error"):
            raise HTTPException(
                status_code=422,
                detail=result.get("message", "Input blocked: disallowed content detected.")
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

        requirements = _guided_answers_to_requirements(flat_answers, req.scope.model_dump())

        tmpl_agent = TemplateAgent(client)
        template_result = await tmpl_agent.run(requirements=requirements)

        rsn_agent = ReasoningAgent(client)
        reasoning_result = await rsn_agent.run(
            template_result=template_result,
            requirements=requirements,
        )

        return _build_solution(template_result, reasoning_result, requirements)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Guided complete failed: {exc}") from exc


# ── Expert Mode ─────────────────────────────────────────────────────────────
@router.post("/expert/questions", response_model=ExpertQuestionsResponse)
async def expert_questions(req: ExpertQuestionsRequest):
    try:
        client = _get_client()
        agent = ExpertAgent(client)
        result = await agent.run(
            user_input=req.user_input,
            scope=req.scope.model_dump(),
            round=req.round,
            conversation_history=[t.model_dump() for t in req.conversation_history],
            analysis_blocks=req.analysis_blocks,
        )
        return ExpertQuestionsResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Expert questions failed: {exc}") from exc


@router.post("/expert/complete", response_model=SolutionOutput)
async def expert_complete(req: ExpertCompleteRequest):
    try:
        client = _get_client()
        requirements = _expert_blocks_to_requirements(req.analysis_blocks, req.scope.model_dump())

        tmpl_agent = TemplateAgent(client)
        template_result = await tmpl_agent.run(requirements=requirements)

        rsn_agent = ReasoningAgent(client)
        reasoning_result = await rsn_agent.run(
            template_result=template_result,
            requirements=requirements,
        )

        return _build_solution(template_result, reasoning_result, requirements)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Expert complete failed: {exc}") from exc


# ── Helpers ──────────────────────────────────────────────────────────────────
def _build_solution(template_result: dict, reasoning_result: dict, requirements: dict) -> SolutionOutput:
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
    )


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


def _expert_blocks_to_requirements(blocks: dict, scope: dict) -> dict:
    b1 = blocks.get("analysis_block_1_application_identity", {})
    b2 = blocks.get("analysis_block_2_architecture_pattern", {})
    b4 = blocks.get("analysis_block_4_traffic_and_scale", {})
    b5 = blocks.get("analysis_block_5_availability", {})
    b6 = blocks.get("analysis_block_6_access_and_security", {})
    b7 = blocks.get("analysis_block_7_resource_sizing_and_budget", {})

    def _is_true(val) -> bool:
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("true", "yes", "1")

    users_band_map = {
        "under_100": 50,
        "100_to_1k": 500,
        "1k_to_10k": 5000,
        "10k_to_100k": 50000,
        "100k_plus": 200000,
    }
    users_num = users_band_map.get(b4.get("concurrent_users_band", "100_to_1k"), 500)

    storage_map = {
        "small_under_10gb": 0.01,
        "medium_10_to_500gb": 0.25,
        "large_500gb_plus": 1.0,
    }
    storage_tb = storage_map.get(b4.get("data_storage_band", "medium_10_to_500gb"), 0.25)

    sla_map = {"best_effort": "99%", "99.9": "99.9%", "99.99": "99.99%"}
    sla = str(b5.get("sla_target", "99.9"))
    uptime = sla_map.get(sla, "99.9%")

    multi_az = _is_true(b5.get("multi_az")) or sla == "99.99"
    public_facing = _is_true(b6.get("public_facing", True))

    compliance_raw = b6.get("compliance_requirements", [])
    if isinstance(compliance_raw, str):
        compliance_raw = [compliance_raw]
    compliance = [c for c in compliance_raw if c and c not in ("none", "None")]

    handles_sensitive = _is_true(b6.get("handles_sensitive_data"))

    budget_raw = b7.get("monthly_budget_ceiling_usd")
    try:
        budget_usd = int(float(str(budget_raw))) if budget_raw not in (None, "null", "") else 1000
    except (ValueError, TypeError):
        budget_usd = 1000

    tier = "startup" if budget_usd < 500 else "growing" if budget_usd < 5000 else "enterprise"

    stack_parts = [
        b1.get("language"), b1.get("framework"),
        b1.get("frontend_framework"), b1.get("database_engine"),
    ]
    stack = [s for s in stack_parts if s and s not in ("null", "none", None)]
    if not stack:
        stack = scope.get("stack", [])

    return {
        "app_type": b1.get("app_type", scope.get("app_type", "web_application")),
        "scale": {
            "concurrent_users": users_num,
            "requests_per_second": max(1, users_num // 10),
            "storage_tb": storage_tb,
            "growth_rate": "growing" if _is_true(b4.get("expected_growth")) else "steady",
        },
        "availability": {
            "uptime_requirement": uptime,
            "rto_minutes": 15 if sla == "99.99" else 60,
            "rpo_minutes": 30 if sla == "99.99" else 60,
            "multi_az": multi_az,
        },
        "network": {
            "internet_facing": public_facing,
            "cdn_required": public_facing and users_num > 1000,
            "multi_region": _is_true(b5.get("disaster_recovery_required")),
        },
        "security": {
            "authentication": True,
            "data_classification": "confidential" if handles_sensitive else "internal",
            "compliance": compliance,
        },
        "budget": {
            "tier": tier,
            "monthly_estimate_usd": budget_usd,
            "cost_optimization": "balanced",
        },
        "stack": stack,
        "derived_requirements": [
            f"Expert mode: {b2.get('pattern', 'three_tier')} architecture",
            f"Environment: {b7.get('environment', 'production')}",
        ],
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

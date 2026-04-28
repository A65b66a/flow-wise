from pydantic import BaseModel, Field
from typing import Any, Generic, Optional, TypeVar

T = TypeVar('T')


# ── Base Response ───────────────────────────────────────────────────────────
class BaseResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None
    error_code: Optional[str] = None
    type: Optional[str] = None
    details: Optional[dict] = None


# ── Scope ──────────────────────────────────────────────────────────────────
class ScopeRequest(BaseModel):
    user_input: str


class ScopeResponse(BaseModel):
    status: str = "proceed"  # "proceed" | "failed"
    message: str = ""
    app_type: str = "web"
    stack: list[str] = Field(default_factory=list)
    scale_hint: str = "medium"
    domain: str = "general"
    confidence_score: float = 0.0
    reasoning: list[str] = Field(default_factory=list)


# ── Mode ───────────────────────────────────────────────────────────────────
class ModeRequest(BaseModel):
    user_input: str
    scope: ScopeResponse


class ModeScores(BaseModel):
    auto_score: float = 0.0
    guided_score: float = 0.0
    expert_score: float = 0.0


class ModeResponse(BaseModel):
    recommended_mode: str  # AUTO | GUIDED | EXPERT
    reasoning: str
    confidence: float
    mode_signals: ModeScores = Field(default_factory=ModeScores)


# ── Auto Pilot ─────────────────────────────────────────────────────────────
class AutoPilotInitRequest(BaseModel):
    user_input: str
    scope: ScopeResponse


class MissingField(BaseModel):
    id: str
    label: str
    question: str
    placeholder: str
    type: str
    options: list[str] = Field(default_factory=list)


class ConfirmedDetections(BaseModel):
    app_type: str
    stack: list[str]
    architecture_pattern: str
    session_store: str
    deployment_model: str


class AutoPilotInitResponse(BaseModel):
    confirmed_detections: ConfirmedDetections
    missing_fields: list[MissingField]
    architecture_hint: str


class QuickInputs(BaseModel):
    users: str
    visibility: str = "public"
    uptime: str = "99.9%"


class AutoPilotCompleteRequest(BaseModel):
    user_input: str
    scope: ScopeResponse
    auto_pilot_init: AutoPilotInitResponse
    quick_inputs: QuickInputs


# ── Guided Mode ────────────────────────────────────────────────────────────
class GuidedQuestion(BaseModel):
    id: str
    text: str
    why: str
    type: str  # text | select | multiselect | boolean | number
    placeholder: str = ""
    options: list[str] = Field(default_factory=list)
    required: bool = False


class GuidedBlockRequest(BaseModel):
    block: int
    user_input: str
    scope: ScopeResponse
    previous_answers: dict[str, Any] = Field(default_factory=dict)


class GuidedBlockResponse(BaseModel):
    block: int
    title: str
    description: str
    questions: list[GuidedQuestion]


class GuidedCompleteRequest(BaseModel):
    user_input: str
    scope: ScopeResponse
    answers: dict[str, Any]  # { "block_1": { "q_id": "answer", ... }, ... }


# ── Business Requirements ──────────────────────────────────────────────────
class ScaleSpec(BaseModel):
    concurrent_users: int = 0
    requests_per_second: int = 0
    storage_tb: float = 0.0
    growth_rate: str = "steady"


class AvailabilitySpec(BaseModel):
    uptime_requirement: str = "99.9%"
    rto_minutes: int = 60
    rpo_minutes: int = 30
    multi_az: bool = True


class NetworkSpec(BaseModel):
    internet_facing: bool = True
    cdn_required: bool = False
    multi_region: bool = False


class SecuritySpec(BaseModel):
    authentication: bool = True
    data_classification: str = "internal"
    compliance: list[str] = Field(default_factory=list)


class BudgetSpec(BaseModel):
    tier: str = "growing"
    monthly_estimate_usd: int = 0
    cost_optimization: str = "balanced"


class BusinessRequirements(BaseModel):
    app_type: str
    scale: ScaleSpec = Field(default_factory=ScaleSpec)
    availability: AvailabilitySpec = Field(default_factory=AvailabilitySpec)
    network: NetworkSpec = Field(default_factory=NetworkSpec)
    security: SecuritySpec = Field(default_factory=SecuritySpec)
    budget: BudgetSpec = Field(default_factory=BudgetSpec)
    stack: list[str] = Field(default_factory=list)
    derived_requirements: list[str] = Field(default_factory=list)


# ── Expert Mode ────────────────────────────────────────────────────────────
class ExpertQuestion(BaseModel):
    id: str
    text: str
    why: str
    type: str  # text | select | multiselect | boolean
    placeholder: str = ""
    options: list[str] = Field(default_factory=list)
    block_ref: str = ""


class ExpertQAEntry(BaseModel):
    question: str
    answer: Any


class ExpertTurn(BaseModel):
    round: int
    qa_pairs: list[ExpertQAEntry] = Field(default_factory=list)


class ExpertQuestionsRequest(BaseModel):
    user_input: str
    scope: ScopeResponse
    round: int = 1
    conversation_history: list[ExpertTurn] = Field(default_factory=list)
    analysis_blocks: dict[str, Any] = Field(default_factory=dict)


class ExpertQuestionsResponse(BaseModel):
    round: int
    questions: list[ExpertQuestion]
    analysis_blocks: dict[str, Any]
    is_complete: bool = False
    blocks_filled_count: int = 0
    missing_critical_fields: list[str] = Field(default_factory=list)
    source: str = "llm"  # "llm" | "fallback"


class ExpertCompleteRequest(BaseModel):
    user_input: str
    scope: ScopeResponse
    analysis_blocks: dict[str, Any]


# ── Solution Output ────────────────────────────────────────────────────────
class ArchitectureSummary(BaseModel):
    architecture_type: str
    components: list[str]
    estimated_monthly_cost: str
    deployment_complexity: str
    key_highlights: list[str]


class ReasoningLog(BaseModel):
    template_selection: str
    component_choices: list[str]
    trade_offs: list[str]
    alternatives_considered: list[str]


class CytoscapeNode(BaseModel):
    data: dict[str, Any]
    classes: str = ""


class CytoscapeEdge(BaseModel):
    data: dict[str, Any]
    classes: str = ""


class CytoscapeElements(BaseModel):
    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)


class SolutionOutput(BaseModel):
    template_id: str
    template_name: str
    summary: ArchitectureSummary
    reasoning: ReasoningLog
    configuration: dict[str, Any]
    cytoscape_elements: CytoscapeElements
    requirements: BusinessRequirements

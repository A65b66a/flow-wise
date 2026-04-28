from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any
from typing import Literal


# ── Scope ──────────────────────────────────────────────────────────────────
class ScopeRequest(BaseModel):
    user_input: str


class ScopeResponse(BaseModel):
    app_type: str
    stack: list[str]
    scale_hint: str
    domain: str
    confidence_score: float
    detected_signals: list[str]


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


# ── Smart Guided Mode ───────────────────────────────────────────────────────
class SmartGuidedQuestionsRequest(BaseModel):
    user_input: str
    scope: ScopeResponse


class SmartGuidedQuestionsResponse(BaseModel):
    title: str
    description: str
    questions: list[GuidedQuestion]


class SmartGuidedCompleteRequest(BaseModel):
    user_input: str
    scope: ScopeResponse
    answers: dict[str, Any]  # { "q_id": "answer", ... }


# ── Conversational Guided Mode ────────────────────────────────────────────
class ConversationTurn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ConversationalMessageRequest(BaseModel):
    user_input: str
    scope: ScopeResponse
    # Optional server-side session id for stateful conversational guided mode.
    # If omitted, the server may create a new session.
    session_id: str | None = None
    conversation: list[ConversationTurn] = Field(default_factory=list)
    message: str
    # Prompt-driven question budget for conversational guided.
    # The LLM is responsible for asking at least this many questions before completing.
    min_questions: int = 5


class ConversationalMessageResponse(BaseModel):
    is_complete: bool
    session_id: str | None = None
    message: str | None = None
    collected_answers: dict[str, Any] | None = None
    # Optional UI hints (may be null for pure-chat rendering).
    field: str | None = None
    question_type: str | None = None  # single_choice | multi_choice | number | text
    options: list[str] | None = None


class ConversationalReviewRequest(BaseModel):
    user_input: str
    scope: ScopeResponse
    answers: dict[str, Any] = Field(default_factory=dict)


class ConversationalReviewResponse(BaseModel):
    status: Literal["questioning", "complete"]
    question: GuidedLoopQuestion | None = None
    analysis_blocks: GuidedAnalysisBlocks | None = None
    confidence: AnalysisConfidence | None = None


# ── Guided Analysis Blocks (7-block schema) ─────────────────────────────────
AppType = Literal[
    "web_application",
    "api_service",
    "data_pipeline",
    "ml_model",
    "ecommerce",
    "real_time",
    "devops_tool",
    "other",
]
Framework = Literal[
    "django",
    "laravel",
    "nodejs",
    "spring_boot",
    "fastapi",
    "rails",
    "nextjs",
    "other",
]
Language = Literal["python", "php", "javascript", "java", "go", "ruby", "typescript", "other"]
DatabaseEngine = Literal[
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "elasticsearch",
    "influxdb",
    "clickhouse",
    "sqlite",
]
Domain = Literal["healthcare", "fintech", "ecommerce", "media", "devops", "general", "other"]
FrontendFramework = Literal["react", "vue", "angular", "nextjs", "nuxt", "svelte", "other"]


class AnalysisBlock1ApplicationIdentity(BaseModel):
    app_type: AppType
    app_name: str | None = None
    frontend_framework: FrontendFramework | None = None
    framework: Framework | None = None
    language: Language | None = None
    database_required: bool
    database_engine: DatabaseEngine | None = None
    domain: Domain


Pattern = Literal[
    "single_vm",
    "two_tier",
    "three_tier",
    "microservices",
    "event_driven",
    "data_pipeline",
    "ml_pipeline",
]
MessageQueueEngine = Literal["rabbitmq", "kafka", "none"]
CacheEngine = Literal["redis", "memcached", "none"]


class AnalysisBlock2ArchitecturePattern(BaseModel):
    pattern: Pattern
    separate_frontend_backend: bool
    multiple_services: bool
    api_gateway_required: bool
    load_balancer_required: bool
    message_queue_required: bool
    message_queue_engine: MessageQueueEngine = "none"
    cache_required: bool
    cache_engine: CacheEngine = "none"


class AnalysisBlock3NetworkDesign(BaseModel):
    network_mode: Literal["auto", "manual"] = "auto"
    vpc_cidr: str = "10.0.0.0/16"
    public_subnet_cidr: str = "10.0.1.0/24"
    private_subnet_cidr: str = "10.0.2.0/24"
    db_subnet_cidr: str = "10.0.3.0/24"
    nat_gateway: bool = True
    admin_cidr_blocks: list[str] = Field(default_factory=list)


ConcurrentUsersBand = Literal["under_100", "100_to_1k", "1k_to_10k", "10k_to_100k", "100k_plus"]
DataStorageBand = Literal["small_under_10gb", "medium_10_to_500gb", "large_500gb_plus"]
TrafficPattern = Literal["steady", "spiky_events", "scheduled_batch", "realtime_continuous"]
ResolvedScale = Literal["small", "medium", "large"]


class AnalysisBlock4TrafficAndScale(BaseModel):
    concurrent_users_band: ConcurrentUsersBand
    data_storage_band: DataStorageBand
    traffic_pattern: TrafficPattern
    expected_growth: bool
    resolved_scale: ResolvedScale


DowntimeImpact = Literal["casual_acceptable", "serious_issue", "business_critical"]
SlaTarget = Literal["best_effort", "99.9", "99.99"]
BackupPolicy = Literal["none", "daily", "hourly"]


class AnalysisBlock5Availability(BaseModel):
    downtime_impact: DowntimeImpact
    single_server_failure_tolerance: bool
    disaster_recovery_required: bool
    sla_target: SlaTarget
    web_vm_count: int = Field(ge=1, le=3)
    app_vm_count: int = Field(ge=1, le=3)
    db_replica: bool
    multi_az: bool
    backup_policy: BackupPolicy


ComplianceRequirement = Literal["HIPAA", "PCI-DSS", "GDPR", "SOC2", "none"]
SensitiveDataType = Literal["payments", "health_records", "financial_data", "pii", "none"]
TlsVersion = Literal["1.2", "1.3"]


class AnalysisBlock6AccessAndSecurity(BaseModel):
    public_facing: bool
    team_ssh_access: bool
    compliance_requirements: list[ComplianceRequirement] = Field(default_factory=list)
    handles_sensitive_data: bool
    sensitive_data_types: list[SensitiveDataType] = Field(default_factory=list)
    bastion_required: bool
    waf_required: bool
    encryption_at_rest: bool
    encryption_in_transit: bool
    audit_log_required: bool
    tls_version: TlsVersion = "1.2"


VmSizePreference = Literal[
    "small_2vcpu_4gb",
    "medium_4vcpu_8gb",
    "large_8vcpu_16gb",
    "xlarge_16vcpu_32gb",
    "auto_recommend",
]
VmType = Literal["small", "medium", "large", "xlarge"]
Environment = Literal["development", "staging", "production"]
DbStorageGb = int


class AnalysisBlock7ResourceSizingAndBudget(BaseModel):
    vm_size_preference: VmSizePreference
    monthly_budget_ceiling_usd: int | None = None
    environment: Environment
    web_vm_type: VmType
    app_vm_type: VmType
    db_vm_type: VmType
    db_storage_gb: DbStorageGb = Field(ge=1)
    cost_estimate_monthly_inr: int | None = None
    cost_optimised_variant_available: bool


class GuidedAnalysisBlocks(BaseModel):
    analysis_block_1_application_identity: AnalysisBlock1ApplicationIdentity
    analysis_block_2_architecture_pattern: AnalysisBlock2ArchitecturePattern
    analysis_block_3_network_design: AnalysisBlock3NetworkDesign
    analysis_block_4_traffic_and_scale: AnalysisBlock4TrafficAndScale
    analysis_block_5_availability: AnalysisBlock5Availability
    analysis_block_6_access_and_security: AnalysisBlock6AccessAndSecurity
    analysis_block_7_resource_sizing_and_budget: AnalysisBlock7ResourceSizingAndBudget


# ── Guided Loop Mode (confidence-driven, multi-turn) ─────────────────────────
ConfidenceOverall = Literal["high", "medium", "low"]


class AnalysisConfidence(BaseModel):
    overall: ConfidenceOverall
    low_confidence_fields: list[str] = Field(default_factory=list)
    reasoning: str


GuidedLoopQuestionType = Literal["single_choice", "multi_choice", "number", "text"]


class GuidedLoopQuestion(BaseModel):
    field: str
    text: str
    type: GuidedLoopQuestionType
    options: list[str] | None = None


class GuidedLoopStartRequest(BaseModel):
    user_input: str
    scope: ScopeResponse
    max_questions: int = 10


class GuidedLoopStartResponse(BaseModel):
    session_id: str
    status: Literal["questioning", "complete", "failed"]
    question: GuidedLoopQuestion | None = None
    question_number: int | None = None
    analysis_blocks: GuidedAnalysisBlocks | None = None
    confidence: AnalysisConfidence | None = None


class GuidedLoopAnswerRequest(BaseModel):
    session_id: str
    field: str
    value: Any


class GuidedLoopAnswerResponse(BaseModel):
    session_id: str
    status: Literal["questioning", "complete", "failed"]
    question: GuidedLoopQuestion | None = None
    question_number: int | None = None
    analysis_blocks: GuidedAnalysisBlocks | None = None
    confidence: AnalysisConfidence | None = None


class GuidedLoopSessionState(BaseModel):
    session_id: str
    mode: Literal["guided_loop"] = "guided_loop"
    user_input: str
    scope: ScopeResponse
    answers: dict[str, Any] = Field(default_factory=dict)
    question_count: int = 0
    max_questions: int = 10
    analysis_blocks: GuidedAnalysisBlocks | None = None
    confidence: AnalysisConfidence | None = None
    status: Literal["questioning", "complete", "failed"] = "questioning"


# ── Expert Loop Mode (ask many fields) ───────────────────────────────────────
class ExpertLoopStartRequest(BaseModel):
    user_input: str
    scope: ScopeResponse
    min_questions: int = 20


class ExpertLoopStartResponse(BaseModel):
    session_id: str
    status: Literal["questioning", "complete", "failed"]
    question: GuidedLoopQuestion | None = None
    question_number: int | None = None
    analysis_blocks: GuidedAnalysisBlocks | None = None
    confidence: AnalysisConfidence | None = None
    solution: "SolutionOutput | None" = None


class ExpertLoopAnswerRequest(BaseModel):
    session_id: str
    field: str
    value: Any


class ExpertLoopAnswerResponse(BaseModel):
    session_id: str
    status: Literal["questioning", "complete", "failed"]
    question: GuidedLoopQuestion | None = None
    question_number: int | None = None
    analysis_blocks: GuidedAnalysisBlocks | None = None
    confidence: AnalysisConfidence | None = None
    solution: "SolutionOutput | None" = None


class ExpertLoopSessionState(BaseModel):
    session_id: str
    mode: Literal["expert_loop"] = "expert_loop"
    user_input: str
    scope: ScopeResponse
    conversation: list[ConversationTurn] = Field(default_factory=list)
    answers: dict[str, Any] = Field(default_factory=dict)
    question_count: int = 0
    min_questions: int = 20
    current_question: GuidedLoopQuestion | None = None
    analysis_blocks: GuidedAnalysisBlocks | None = None
    confidence: AnalysisConfidence | None = None
    status: Literal["questioning", "complete", "failed"] = "questioning"


class GuidedAnalysisRequest(BaseModel):
    user_input: str
    scope: ScopeResponse
    answers: dict[str, Any] = Field(default_factory=dict)
    block: int | None = None  # if provided, generate only this block


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
    analysis_blocks: GuidedAnalysisBlocks | None = None

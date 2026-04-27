import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.agents.scope_agent import ScopeIdentificationAgent


def make_agent(generate_json_return):
    client = MagicMock()
    client.generate_json = AsyncMock(return_value=generate_json_return)
    return ScopeIdentificationAgent(client)


def _valid_raw(**overrides):
    base = {
        "status": "proceed",
        "app_type": "web",
        "stack": ["React", "Node.js"],
        "scale_hint": "medium",
        "domain": "e-commerce",
        "confidence_score": 0.85,
        "reasoning": [
            "app_type: web application",
            "domain: e-commerce platform",
            "scale: medium (50k users)",
            "stack: React, Node.js explicitly mentioned",
        ],
    }
    base.update(overrides)
    return base


# ── Happy path ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_normal_input_returns_all_fields():
    agent = make_agent(_valid_raw())
    result = await agent.run("e-commerce site with React and Node")
    assert result["status"] == "proceed"
    assert result["app_type"] == "web"
    assert result["stack"] == ["React", "Node.js"]
    assert result["scale_hint"] == "medium"
    assert result["domain"] == "e-commerce"
    assert result["confidence_score"] == 0.85
    assert len(result["reasoning"]) == 4


@pytest.mark.asyncio
async def test_proceed_has_empty_message():
    agent = make_agent(_valid_raw())
    result = await agent.run("some valid app")
    assert result["message"] == ""


@pytest.mark.asyncio
async def test_confidence_score_as_string_is_coerced():
    agent = make_agent(_valid_raw(confidence_score="0.9"))
    result = await agent.run("some app")
    assert result["confidence_score"] == 0.9


# ── Default fallbacks ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_llm_response_uses_all_defaults():
    agent = make_agent({})
    result = await agent.run("vague description")
    assert result["status"] == "proceed"
    assert result["app_type"] == "web"
    assert result["stack"] == []
    assert result["scale_hint"] == "medium"
    assert result["domain"] == "general"
    assert result["confidence_score"] == 0.5
    assert result["reasoning"] == []


@pytest.mark.asyncio
async def test_partial_response_uses_defaults_for_missing_fields():
    agent = make_agent({"status": "proceed", "app_type": "api", "domain": "fintech"})
    result = await agent.run("a fintech API")
    assert result["app_type"] == "api"
    assert result["domain"] == "fintech"
    assert result["stack"] == []
    assert result["scale_hint"] == "medium"
    assert result["confidence_score"] == 0.5


@pytest.mark.asyncio
async def test_non_numeric_confidence_score_falls_back_to_default():
    agent = make_agent(_valid_raw(confidence_score="high"))
    result = await agent.run("some app")
    assert result["confidence_score"] == 0.5


@pytest.mark.asyncio
async def test_none_confidence_score_falls_back_to_default():
    agent = make_agent(_valid_raw(confidence_score=None))
    result = await agent.run("some app")
    assert result["confidence_score"] == 0.5


# ── Failed status: content policy ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_content_policy_violation_returns_failed_status():
    agent = make_agent({
        "status": "failed",
        "message": "Request blocked: input contains disallowed content.",
        "reasoning": ["Content policy violation detected"],
    })
    result = await agent.run("some bad input")
    assert result["status"] == "failed"
    assert "blocked" in result["message"]
    assert result["reasoning"] == ["Content policy violation detected"]


@pytest.mark.asyncio
async def test_failed_response_still_has_scope_field_defaults():
    agent = make_agent({
        "status": "failed",
        "message": "blocked",
        "reasoning": ["Content policy violation detected"],
    })
    result = await agent.run("bad input")
    assert result["app_type"] == "web"
    assert result["stack"] == []
    assert result["scale_hint"] == "medium"
    assert result["domain"] == "general"
    assert result["confidence_score"] == 0.0


# ── Failed status: invalid input ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_input_returns_failed_status():
    agent = make_agent({
        "status": "failed",
        "message": "This tool designs cloud application architecture.",
        "reasoning": ["Input is a food request, not a software application description"],
    })
    result = await agent.run("i want burger")
    assert result["status"] == "failed"
    assert result["message"] != ""
    assert len(result["reasoning"]) > 0


@pytest.mark.asyncio
async def test_failed_message_is_populated():
    agent = make_agent({
        "status": "failed",
        "message": "Not a valid cloud app description.",
        "reasoning": ["No software system described"],
    })
    result = await agent.run("what is the weather")
    assert result["message"] == "Not a valid cloud app description."


# ── Input edge cases ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_string_input_does_not_raise():
    agent = make_agent(_valid_raw(app_type="web", confidence_score=0.1))
    result = await agent.run("")
    assert result["app_type"] == "web"


@pytest.mark.asyncio
async def test_very_long_input_does_not_raise():
    agent = make_agent(_valid_raw(app_type="saas", scale_hint="enterprise", confidence_score=0.95))
    long_input = "I want to build " + ("a very large enterprise SaaS platform " * 200)
    result = await agent.run(long_input)
    assert result["app_type"] == "saas"


@pytest.mark.asyncio
async def test_special_characters_in_input_do_not_raise():
    agent = make_agent(_valid_raw())
    result = await agent.run("app with special chars: <>&\"'{}[]")
    assert result["status"] == "proceed"


# ── LLM / network errors ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_llm_exception_propagates():
    client = MagicMock()
    client.generate_json = AsyncMock(side_effect=RuntimeError("API timeout"))
    agent = ScopeIdentificationAgent(client)
    with pytest.raises(RuntimeError, match="API timeout"):
        await agent.run("some input")


# ── All valid enum values ─────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("app_type", [
    "web", "mobile-backend", "api", "data-pipeline",
    "microservices", "batch-processing", "real-time", "iot", "saas",
])
async def test_all_valid_app_types(app_type):
    agent = make_agent(_valid_raw(app_type=app_type))
    result = await agent.run("some app")
    assert result["app_type"] == app_type


@pytest.mark.asyncio
@pytest.mark.parametrize("scale_hint", ["small", "medium", "large", "enterprise"])
async def test_all_valid_scale_hints(scale_hint):
    agent = make_agent(_valid_raw(scale_hint=scale_hint))
    result = await agent.run("some app")
    assert result["scale_hint"] == scale_hint


@pytest.mark.asyncio
@pytest.mark.parametrize("domain", [
    "e-commerce", "healthcare", "fintech", "social-media",
    "iot", "saas", "education", "media", "logistics", "general",
])
async def test_all_valid_domains(domain):
    agent = make_agent(_valid_raw(domain=domain))
    result = await agent.run("some app")
    assert result["domain"] == domain

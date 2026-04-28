from __future__ import annotations

from typing import Any

from backend.agents.base import BaseAgent
from backend.models.schemas import GuidedAnalysisBlocks


MAX_QUESTIONS = 12


def _extract_internal_metadata(text: str) -> tuple[str, dict[str, Any]]:
    """
    Extract and remove a single trailing internal metadata block from assistant text.

    Expected format (must be at the very end of the assistant message):
      <internal>{"finalization": true}</internal>

    Returns (clean_text, metadata_dict). If not present or malformed, returns (text, {}).
    """
    if not text:
        return text, {}

    end_tag = "</internal>"
    start_tag = "<internal>"
    raw = text.strip()
    if not raw.endswith(end_tag):
        return text, {}

    start = raw.rfind(start_tag)
    if start < 0:
        return text, {}

    payload = raw[start + len(start_tag) : -len(end_tag)].strip()
    clean = raw[:start].rstrip()
    try:
        # We reuse the existing JSON extractor for resilience.
        from backend.utils.json_utils import extract_json

        meta = extract_json(payload) or {}
        return clean, meta if isinstance(meta, dict) else {}
    except Exception:
        return text, {}

_SYSTEM = """You are a friendly cloud architecture assistant.
Goal: ask a short series of business-first questions to collect enough info to populate a 7-block analysis, then return completion JSON.

STYLE
- Warm, plain English. No cloud jargon (VPC/CIDR/SLA/WAF/load balancer/API gateway/etc).
- Short messages. ONE question per assistant message.
- Acknowledge the user briefly, then ask the next question.
- Avoid repetitive phrasing: do NOT reuse the same question pattern or opener across turns (e.g., don’t keep saying “Quick check…”).
- Rephrase questions to match the user’s business (use examples that fit their domain).
- No emojis. Do NOT use any emoji characters anywhere (e.g., 🎓 ✅ 🙂 🚀).
- No cheerleading or generic enthusiasm. Do NOT say things like: “that’s a great initiative”, “great idea”, “awesome”, “love that”, “exciting”, “fantastic”.
  Sound like a calm helpful colleague: a brief acknowledgement (optional) then the question.
- After the question, add ONE short plain-English sentence explaining what the answer helps decide.
  Do NOT use labels like `Reason:` — write it like a normal sentence.
- Acknowledgements must reduce ambiguity. If the user implies restricted access (e.g., “school login”, “employee login”, “SSO”, “members only”),
  restate it explicitly as restricted/internal (e.g., “restricted to school users via login”), not vaguely.
- Never include internal labels like [FINALIZATION], [COMPLETE], [EXTRACTION] or any bracketed tags in user-facing messages. These are internal only.

INTERNAL METADATA (CRITICAL, NOT USER-FACING)
- At the end of every non-completion response, append EXACTLY ONE internal metadata block:
  <internal>{"finalization": true|false}</internal>
- This block is for the server only and will be stripped before the user sees it.
- Do NOT wrap it in brackets or markdown. Do NOT add any other internal tags.
- Do NOT include this block when you output the completion JSON.

HARD CONSTRAINTS
- 7-block-only: you will be given AVAILABLE_FIELD_PATHS. Every question MUST map to ONE OR MORE of those fields. Never show field paths.
- Numbers: never change user-provided numbers/percentages/money/dates. Repeat exactly; no rounding; no invented ranges. If implausible, ask ONE clarifying question.
- Anti-repeat: never ask something already answered.
  Before generating each question scan the FULL conversation history for already-answered fields.
  If a field was answered in any earlier message treat it as filled. Never ask about it again.
  If they ask “what do you mean?”, explain in 2–3 sentences + 1 business-relevant example, then re-ask the SAME question.
- Skip/edit: if user says “skip/not sure”, accept and move on (omit that field in completion). If they correct something, treat latest as truth.
- Consistency check (dependencies, GENERIC): after each user reply, compare the new info against what is already confirmed.
  - If there is a contradiction or a dependency mismatch, ask EXACTLY ONE clarification question before moving on.
  - After the user answers that clarification, resume the prior flow (continue the pending topic).
  Examples of dependency checks across the 7 blocks (apply generally, adapt to business context):
  - Identity/domain:
    - If they describe “internal employee-only dashboard” but later claim “public sign-up”, clarify visibility.
  - Architecture pattern:
    - If they demand “microservices” but also insist on “keep it super simple / one server”, clarify which matters most.
  - Scale/traffic:
    - If they give a very large peak-user number that conflicts with earlier “small internal tool” framing, clarify scale.
  - Availability:
    - If they say downtime is “minor inconvenience” but also demand “near-zero downtime”, clarify which is correct.
  - Security/sensitive data/compliance:
    - If they say “no sensitive data” but the app clearly has accounts/addresses/contact info, clarify whether they store PII.
    - Generic safety confirmation (ALL scenarios):
      - If the user downplays security/privacy (e.g., “non-sensitive”, “no special protection needed”, “we don’t care about security”)
        but the app still clearly handles any user accounts, contact details, addresses, photos/files, payments (even via a provider),
        or any other personal/business data, ask EXACTLY ONE quick confirmation before moving on:
        “Even if it’s not regulated, should we still do basic protections like encryption + access controls? (yes/no)"
      - After they answer that one confirmation, accept it and continue (do not argue).
    - If they mention PCI-DSS but there’s no clear card payment flow, clarify whether they take card payments (even via a provider) or meant something else.
    - IMPORTANT PCI RULE:
      - If they confirm payments are processed by a provider (e.g., Stripe/Razorpay) AND they do NOT store/handle card details directly,
        then you MUST NOT include PCI-DSS as a compliance requirement UNLESS the user explicitly insists they still need PCI-DSS for business/audit reasons.
      - If the user previously mentioned PCI-DSS but later clarifies "provider handles card data / we don't handle card details",
        treat that as a correction and remove PCI-DSS from compliance_requirements.
    - If they mention HIPAA but there’s no health/medical data, clarify whether they handle real health records.
    - If they mention GDPR but there’s no EU/user-region signal, clarify whether they have EU users.
  - Background work/queues:
    - If they say “no background work” but also describe emails/SMS/reports/imports, clarify whether those happen.
  - Budget/sizing tradeoffs:
    - If they want “lowest cost possible” but also want “high reliability + high scale”, clarify priority (cost vs reliability/performance).

MID-FLOW PREFERENCES (store in collected_answers.preferences)
- message_queue_engine: kafka|rabbitmq
- cache_engine: redis|memcached
- database_engine: postgresql|mysql|mongodb|sqlite|influxdb|clickhouse|elasticsearch
- pattern: single vm|two tier|three tier|microservices|event driven|data pipeline|ml pipeline
Ask EXACTLY ONE clarification question when a preference is ambiguous, then return to the pending question.

MESSAGE QUEUE SIGNAL DETECTION (set analysis_block_2_architecture_pattern.message_queue_required = true when present)
message_queue_required = true signals:
- near-instant alerts, push notifications, driver alerts,
  order updates, SMS triggers, real-time events,
  notifications, background tasks, scheduled tasks

SAFE DEFAULTS (never ask, just use)
- message_queue_engine → rabbitmq
- cache_engine         → redis
- environment          → production
- network_mode         → auto
- traffic_pattern      → spiky_events for delivery/ecommerce (otherwise use your best default)

YOU MUST COVER (before finalization)
1) Peak usage + steady vs spiky (scale/traffic)
2) Exposure (internal vs public vs both)
3) Reliability (business impact of 1 hour outage)
4) Sensitive data types (pii/payments/health_records/financial_data/none) using business-relevant examples
5) Compliance (GDPR/PCI-DSS/HIPAA/SOC2/none)
6) Background work (emails/notifications/scheduled/imports) yes/no
7) Growth in next 12 months yes/no

QUESTION ORDER (IMPORTANT)
- Do NOT ask the above in a fixed order for every user.
- Choose the next question based on what is most relevant to the user’s business and what is still missing/unclear.
- Keep it efficient: prefer questions that can naturally cover more than one missing item (while still asking ONE question per message).

SENSITIVE DATA QUESTIONING (CRITICAL)
- Always ask/clarify sensitive data using examples that match the user's business.
- Never mention health/medical records unless the app clearly involves healthcare/medical/patients OR the user explicitly mentions health/medical/patient data.
- Never mention detailed financial history unless the app clearly involves finance/banking/credit/loans OR the user explicitly mentions it.
- Examples to prefer by common app types:
  - Home services/cleaning/booking: names, phone numbers, addresses, payment via provider (Stripe), access instructions, photos of property (if applicable)
  - Ecommerce/marketplace: customer PII, orders, payments (only if handling card data directly)
  - Internal dashboard: employee accounts, customer contact details (PII)

QUESTION COUNT + FINALIZATION
- Ask at least MIN_QUESTIONS questions.
- You MAY ask a few extra questions for clarity, but do NOT exceed 3 additional questions beyond MIN_QUESTIONS.
  (So total questions asked must be <= MIN_QUESTIONS + 3.)
- After coverage AND >= MIN_QUESTIONS, ask ONE tailored finalization question (preferences/avoidances; rephrase per app).
  - Ask ONE finalization question only — ONE topic only.
  - Never combine two preference questions in the same message (no “also” / “and” follow-ups).
  - Pick the most impactful preference topic. Default to DATABASE preference unless a different single preference is clearly more impactful for this app.
  - Do not combine architecture and database in the same question.
- If the finalization answer is unclear/irrelevant, you MAY ask at most ONE clarification question, then complete on the next response.
  - Keep it generic and business-level (no deep technical follow-ups).
  - It must be easy to answer in one line and the user can say “skip”.
  - Only ask this if it materially changes the architecture recommendation; otherwise skip clarification and complete.

COMPLETION (CRITICAL)
After finalization (and optional 1 clarification), your VERY NEXT response MUST be:
1) One short acknowledgement line
2) Then ONLY this JSON (no extra keys/text/markdown):
{
  "status": "complete",
  "collected_answers": {
    "answers": {
      "<analysis_field_path>": "<value>",
      "...": "..."
    }
  }
}
Only include answers that the user explicitly stated/confirmed, mapped to 7-block field paths.

STOP CONDITION (CRITICAL)
After the finalization question is answered your VERY NEXT
response MUST be the completion JSON. No exceptions.
No additional questions. Use safe defaults for any
remaining unfilled fields.
"""


_REVIEW_Q_SYSTEM = """Write ONE neat, generic clarification question before generating the architecture.
Rules: one question, no internal field names, short/clear, user can say “skip”.
Return ONLY JSON:
{"field":"followup_bundle","text":"...","type":"text","options":null}
"""


class ConversationalGuidedAgent(BaseAgent):
    async def run(
        self,
        user_input: str,
        scope: dict[str, Any],
        conversation: list[dict[str, str]],
        user_message: str,
        session: dict[str, Any] | None = None,
        min_questions: int = 5,
    ) -> dict[str, Any]:
        """
        Prompt-driven conversational mode (original behavior).

        - One LLM call per turn (fast chat).
        - LLM asks at least MIN_QUESTIONS questions, then asks a finalization question,
          then returns completion JSON.
        - We do NOT run analysis/confidence per turn. Any missing details will be caught
          after completion (review step) and we can ask targeted follow-up questions.
        """
        available_fields = _analysis_field_paths()
        context = (
            f"Application description: {user_input}\n"
            f"App type: {scope.get('app_type')}\n"
            f"Domain: {scope.get('domain')}\n"
            f"Stack detected: {scope.get('stack')}\n"
            f"Scale hint: {scope.get('scale_hint')}\n"
            f"Detected signals: {scope.get('detected_signals')}\n\n"
            f"MIN_QUESTIONS: {int(min_questions)}\n"
            f"AVAILABLE_FIELD_PATHS: {available_fields}"
        )

        sess: dict[str, Any] = session or {}
        question_count = int(sess.get("question_count") or 0)
        finalization_asked = bool(sess.get("finalization_asked") or False)
        finalization_answered = bool(sess.get("finalization_answered") or False)

        system_prompt = _SYSTEM

        # If the user is answering the finalization question, force completion on this turn.
        # We treat "finalization answered" as: finalization was asked previously, and we now received a user reply.
        if finalization_asked and (not finalization_answered) and user_message:
            sess["finalization_answered"] = True
            system_prompt = (
                system_prompt
                + "\n\nThe finalization question has been answered. Your next response MUST be the completion JSON only. No more questions."
            )

        messages: list[dict[str, str]] = [{"role": "user", "content": context}]
        for turn in conversation:
            messages.append({"role": turn["role"], "content": turn["content"]})
        if user_message:
            messages.append({"role": "user", "content": user_message})

        # Hard stop: once we hit MAX_QUESTIONS, force completion via a final injection.
        if question_count >= MAX_QUESTIONS:
            messages.append(
                {
                    "role": "user",
                    "content": "You have reached the question limit. Output the completion JSON now with whatever you have collected.",
                }
            )
            system_prompt = (
                system_prompt
                + "\n\nYou have reached the question limit. Output the completion JSON now with whatever you have collected."
            )

        from anthropic import AsyncAnthropic
        from backend.config import CLAUDE_API_KEY, CLAUDE_MODEL
        from backend.utils.json_utils import extract_json

        client = AsyncAnthropic(api_key=CLAUDE_API_KEY)
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            # Slightly higher to reduce truncated completion JSON.
            max_tokens=900,
            system=system_prompt,
            messages=messages,
        )
        text = response.content[0].text.strip()

        def _as_complete(parsed: dict[str, Any], raw_text: str) -> dict[str, Any] | None:
            if (parsed or {}).get("status") != "complete":
                return None
            collected = (parsed.get("collected_answers") or {}).get("answers") or {}
            ack = None
            brace_idx = raw_text.find("{")
            if brace_idx > 0:
                prefix = raw_text[:brace_idx].strip()
                if prefix:
                    ack = prefix
            return {
                "is_complete": True,
                "message": ack,
                "collected_answers": collected,
                "field": None,
                "question_type": None,
                "options": None,
            }

        if text.startswith("{") or "\"status\"" in text:
            data = extract_json(text)
            done = _as_complete(data, text)
            if done:
                # Persist session state.
                sess["question_count"] = question_count
                return done

            # If the model *attempted* completion but the JSON is invalid/truncated, do a one-time repair.
            attempted_complete = ("\"status\"" in text or "'status'" in text) and ("complete" in text)
            if attempted_complete:
                repair_system = """You fix malformed/truncated JSON from another assistant.
Return ONLY valid JSON. No markdown, no extra text.

Required output format:
{
  "status": "complete",
  "collected_answers": {
    "answers": {
      "<analysis_field_path>": "<value>",
      "...": "..."
    }
  }
}

Rules:
- Only include keys that appear in the REQUIRED output format.
- Only use analysis_field_path values that are in AVAILABLE_FIELD_PATHS.
- Preserve user-provided numbers/percentages/money/dates exactly (no rounding).
"""
                repair_payload = {
                    "AVAILABLE_FIELD_PATHS": available_fields,
                    "raw_model_output": text,
                }
                repaired = await self.client.generate_json(
                    system_prompt=repair_system,
                    user_message=f"Repair into valid completion JSON from:\n\n{repair_payload}",
                    max_tokens=900,
                )
                done2 = _as_complete(repaired, raw_text="{")
                if done2:
                    # Never surface raw JSON to chat UI.
                    done2["message"] = None
                    sess["question_count"] = question_count
                    return done2

        # Strip internal metadata (never show to user) and persist session flags.
        clean_text, meta = _extract_internal_metadata(text)
        if isinstance(meta, dict) and bool(meta.get("finalization")):
            sess["finalization_asked"] = True
        text = clean_text

        # If we're not complete, count this assistant turn as a question turn.
        question_count += 1
        sess["question_count"] = question_count

        return {
            "is_complete": False,
            # Never show partial JSON blobs to the user; if it looks like completion, ask them to continue.
            "message": (
                "One sec — I hit a formatting hiccup while finalizing. Please send one more message (e.g., “continue”)."
                if ("\"status\"" in text and "complete" in text)
                else text
            ),
            "collected_answers": None,
            "field": None,
            "question_type": None,
            "options": None,
        }

    async def build_review_question(
        self,
        *,
        user_input: str,
        scope: dict[str, Any],
        items_to_clarify: list[str],
    ) -> dict[str, Any]:
        ctx = {
            "user_input": user_input,
            "app_type": scope.get("app_type"),
            "domain": scope.get("domain"),
            "detected_signals": scope.get("detected_signals"),
            "items_to_clarify": items_to_clarify,
        }
        return await self.client.generate_json(
            system_prompt=_REVIEW_Q_SYSTEM,
            user_message=f"Write the clarification question from this context:\n\n{ctx}",
            max_tokens=250,
        )


def _analysis_field_paths() -> list[str]:
    """
    Derive dotted field paths from the GuidedAnalysisBlocks Pydantic model.
    This keeps the conversational guided agent resilient to schema extensions.
    """
    paths: list[str] = []

    def walk(model, prefix: str) -> None:
        mf = getattr(model, "model_fields", {}) or {}
        for name, field in mf.items():
            ann = getattr(field, "annotation", None)
            if hasattr(ann, "model_fields"):
                walk(ann, f"{prefix}{name}.")
            else:
                paths.append(f"{prefix}{name}")

    walk(GuidedAnalysisBlocks, "")
    return sorted(set(paths))

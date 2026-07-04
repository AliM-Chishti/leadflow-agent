# ruff: noqa
import datetime
import os
import re
import json
import sys
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from typing import Optional, List, Any

# pyrefly: ignore [missing-import]
from google.adk.agents import LlmAgent
# pyrefly: ignore [missing-import]
from google.adk.tools import AgentTool
# pyrefly: ignore [missing-import]
from google.adk.workflow import Workflow, START
# pyrefly: ignore [missing-import]
from google.adk.events.event import Event
# pyrefly: ignore [missing-import]
from google.adk.events.request_input import RequestInput
# pyrefly: ignore [missing-import]
from google.adk.agents.context import Context
# pyrefly: ignore [missing-import]
from google.adk.apps import App, ResumabilityConfig
# pyrefly: ignore [missing-import]
from google.genai import types

# pyrefly: ignore [missing-import]
from google.adk.tools.mcp_tool import McpToolset
# pyrefly: ignore [missing-import]
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
# pyrefly: ignore [missing-import]
from mcp import StdioServerParameters

from .config import config

# --- MCP Toolset Configurations ---
current_dir = os.path.dirname(os.path.abspath(__file__))
mcp_server_path = os.path.join(current_dir, "mcp_server.py")

# --- Schemas ---

class LeadInput(BaseModel):
    lead_id: str = Field(..., description="Unique lead identifier")
    company_name: str = Field(..., description="Name of the company")
    contact_email: str = Field(..., description="Contact email of the lead")
    message: str = Field(..., description="Inquiry or message from the lead")
    employee_count: int = Field(default=0, description="Optional employee count")
    revenue: float = Field(default=0.0, description="Optional annual revenue")

class LeadOutput(BaseModel):
    lead_id: str
    company_name: str
    routing_tier: str
    status: str
    summary: str
    security_verdict: str
    manager_approved: bool

class LeadState(BaseModel):
    lead_id: str = ""
    company_name: str = ""
    contact_email: str = ""
    message: str = ""
    company_details: dict = {}
    fit_assessment: dict = {}
    audit_trail: list = []
    pii_redacted: bool = False
    security_verdict: str = "PENDING"
    routing_tier: str = "Tier-3"
    manager_approved: bool = False

# --- Sub-Agents ---

company_profiler = LlmAgent(
    name="company_profiler",
    model=config.model,
    instruction="""You are the Company Profiler agent.
Your job is to search for details about the company (annual revenue, employee count, industry) using tools.
If no tool details are found or you lack data, look up general benchmarks or estimate based on industry averages.
Provide a clear JSON summary of the company's firmographics.""",
    tools=[
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[mcp_server_path],
                )
            ),
            tool_filter=["fetch_company_details"]
        )
    ]
)

fit_evaluator = LlmAgent(
    name="fit_evaluator",
    model=config.model,
    instruction="""You are the Product Fit Evaluator agent.
Your job is to analyze the company's details (revenue, size, industry) and the lead's inquiry message to determine product fit.
Fit levels:
- Tier-1 (High Fit): Companies with >50 employees OR >$5M annual revenue.
- Tier-2 (Medium Fit): Companies with 10-50 employees OR $1M-$5M annual revenue.
- Tier-3 (Low Fit): Companies with <10 employees OR <$1M annual revenue.
State the reasoning and assign the tier (Tier-1, Tier-2, or Tier-3).""",
    tools=[
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[mcp_server_path],
                )
            ),
            tool_filter=["get_industry_benchmark"]
        )
    ]
)

# --- Orchestrator Agent ---

orchestrator = LlmAgent(
    name="orchestrator",
    model=config.model,
    instruction="""You are the LeadFlow Orchestrator.
Your goal is to qualify the B2B lead by coordinating sub-agents.
Use the company_profiler agent to profile the lead's company.
Use the fit_evaluator agent to assess product fit and determine the routing tier.
After qualification is complete and the tier is decided, call log_crm_lead to register the lead in the Sales CRM database.
Finally, return a comprehensive qualification summary containing:
- Company Profile
- Fit Assessment
- Assigned Routing Tier (Tier-1, Tier-2, or Tier-3)

Current Lead Data:
Company: {company_name}
Email: {contact_email}
Message: {message}
""",
    tools=[
        AgentTool(company_profiler),
        AgentTool(fit_evaluator),
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[mcp_server_path],
                )
            ),
            tool_filter=["log_crm_lead"]
        )
    ],
    output_key="orchestrator_output"
)

# --- Workflow Node Functions ---

def security_checkpoint(ctx: Context, node_input: LeadInput) -> Event:
    email = node_input.contact_email
    message = node_input.message
    lead_id = node_input.lead_id
    
    # 1. PII Scrubbing (Phone numbers in message)
    phone_pattern = r'\(?\b\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
    scrubbed_message, pii_count = re.subn(phone_pattern, '[PHONE_REDACTED]', message)
    pii_redacted = pii_count > 0
    
    # 2. Prompt Injection Check
    injection_keywords = [
        "ignore previous instructions",
        "ignore all instructions",
        "system prompt",
        "you are now",
        "ignore the above",
        "override",
        "dan mode"
    ]
    injection_detected = False
    lower_message = message.lower()
    for kw in injection_keywords:
        if kw in lower_message:
            injection_detected = True
            break
            
    # 3. Domain-Specific Rule: Competitor/Spam Domain and spam keywords Check
    competitor_domains = ["competitor.com", "rivalcorp.com", "spytech.com"]
    spam_keywords = ["crypto", "bitcoin", "casino", "lottery"]
    
    competitor_detected = False
    email_domain = email.split('@')[-1].lower() if '@' in email else ""
    if email_domain in competitor_domains:
        competitor_detected = True
        
    spam_detected = False
    for kw in spam_keywords:
        if kw in lower_message:
            spam_detected = True
            break
            
    # Decision Routing and Severity logging
    verdict = "SAFE"
    route = "safe"
    severity = "INFO"
    failure_reason = ""
    
    if injection_detected:
        verdict = "REJECTED"
        route = "rejected"
        severity = "CRITICAL"
        failure_reason = "Prompt injection attempt detected."
    elif competitor_detected:
        verdict = "REJECTED"
        route = "rejected"
        severity = "WARNING"
        failure_reason = "Lead belongs to a competitor domain."
    elif spam_detected:
        verdict = "REJECTED"
        route = "rejected"
        severity = "WARNING"
        failure_reason = "Lead message contains spam keywords."
        
    # 4. Structured JSON Audit Log
    audit_entry = {
        "timestamp": str(datetime.datetime.now()),
        "lead_id": lead_id,
        "company_name": node_input.company_name,
        "verdict": verdict,
        "severity": severity,
        "pii_redacted": pii_redacted,
        "injection_detected": injection_detected,
        "competitor_detected": competitor_detected,
        "spam_detected": spam_detected,
        "failure_reason": failure_reason
    }
    
    print(f"[AUDIT_LOG] {json.dumps(audit_entry)}")
    
    audit_trail_entry = {
        "timestamp": str(datetime.datetime.now()),
        "event": f"Security Check: {verdict}. " + (failure_reason if failure_reason else "No issues found.")
    }
    
    return Event(
        output=node_input,
        route=route,
        state={
            "lead_id": lead_id,
            "company_name": node_input.company_name,
            "contact_email": email,
            "message": scrubbed_message,
            "security_verdict": verdict,
            "pii_redacted": pii_redacted,
            "audit_trail": [audit_trail_entry]
        }
    )

def hitl_decision(ctx: Context, node_input: Any) -> Event:
    orchestrator_text = ""
    if isinstance(node_input, str):
        orchestrator_text = node_input
    elif hasattr(node_input, "text"):
        orchestrator_text = node_input.text
    elif isinstance(node_input, dict) and "text" in node_input:
        orchestrator_text = node_input["text"]
    else:
        orchestrator_text = str(node_input)

    is_tier_1 = "tier-1" in orchestrator_text.lower() or "tier 1" in orchestrator_text.lower()
    
    if is_tier_1:
        return Event(
            output=orchestrator_text,
            route="needs_approval",
            state={"routing_tier": "Tier-1"}
        )
    else:
        tier = "Tier-3"
        if "tier-2" in orchestrator_text.lower() or "tier 2" in orchestrator_text.lower():
            tier = "Tier-2"
        return Event(
            output=orchestrator_text,
            route="auto_processed",
            state={"routing_tier": tier, "manager_approved": True}
        )

async def human_review(ctx: Context, node_input: str):
    lead_id = ctx.state.get("lead_id", "default")
    interrupt_id = f"manager_approval_{lead_id}"
    if not ctx.resume_inputs or interrupt_id not in ctx.resume_inputs:
        yield RequestInput(
            interrupt_id=interrupt_id,
            message=f"Lead {ctx.state.get('company_name')} is classified as Tier-1. Approve? (yes/no)"
        )
        return
    
    decision = ctx.resume_inputs[interrupt_id].strip().lower()
    approved = decision in ["yes", "approve", "y"]
    
    yield Event(
        output=node_input,
        state={
            "manager_approved": approved,
            "audit_trail": ctx.state.get("audit_trail", []) + [{
                "timestamp": str(datetime.datetime.now()),
                "event": f"Manager decision: {'Approved' if approved else 'Rejected'} ({decision})"
            }]
        }
    )

def final_output(ctx: Context, node_input: Any):
    lead_id = ctx.state.get("lead_id", "")
    company_name = ctx.state.get("company_name", "")
    routing_tier = ctx.state.get("routing_tier", "Tier-3")
    security_verdict = ctx.state.get("security_verdict", "PENDING")
    manager_approved = ctx.state.get("manager_approved", False)
    
    if security_verdict == "REJECTED":
        summary = "Lead processing rejected due to security policy violation."
        status = "REJECTED"
    else:
        status = "APPROVED" if manager_approved else "HOLD_REJECTED"
        summary = f"Lead qualified successfully. Tier: {routing_tier}. Approved: {manager_approved}."

    output_data = LeadOutput(
        lead_id=lead_id,
        company_name=company_name,
        routing_tier=routing_tier,
        status=status,
        summary=summary,
        security_verdict=security_verdict,
        manager_approved=manager_approved
    )
    
    ui_text = f"""### LeadFlow Qualification Result
*   **Lead ID:** {lead_id}
*   **Company:** {company_name}
*   **Security Verdict:** {security_verdict}
*   **Routing Tier:** {routing_tier}
*   **Manager Approved:** {manager_approved}
*   **Status:** {status}

**Summary:** {summary}
"""
    yield Event(content=types.Content(role='model', parts=[types.Part.from_text(text=ui_text)]))
    yield Event(output=output_data.model_dump())

# --- Workflow Definition ---

root_agent = Workflow(
    name="leadflow_workflow",
    edges=[
        (START, security_checkpoint),
        (security_checkpoint, {"safe": orchestrator, "rejected": final_output}),
        (orchestrator, hitl_decision),
        (hitl_decision, {"needs_approval": human_review, "auto_processed": final_output}),
        (human_review, final_output),
    ],
    input_schema=LeadInput,
    output_schema=LeadOutput,
    state_schema=LeadState,
)

app = App(
    root_agent=root_agent,
    name="leadflow-agent",
    resumability_config=ResumabilityConfig(enabled=True)
)

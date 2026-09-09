import json

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext

from schemas.budget import BudgetAnalysis


MODEL = "gemini-2.5-flash"


BUDGET_AGENT_INSTRUCTION = """
You are CinePilot AI's Production Budget Agent.

Your responsibility is to create an initial production budget
estimate from structured screenplay analysis.

You will receive information about:

- characters
- locations
- props
- vehicles
- VFX requirements
- estimated shooting days
- scenes

Create a realistic PRELIMINARY estimate.

Important rules:

1. Do not claim that the amounts are actual vendor prices.
2. These are planning estimates only.
3. Explain the assumptions behind the estimates.
4. Identify the major cost drivers.
5. Do not invent specific vendors.
6. Return ONLY valid JSON.
7. Do not use Markdown.
8. Do not wrap the JSON in ```json.

Return this structure:

{
    "currency": "INR",
    "shoot_days": 0,
    "categories": [
        {
            "category": "",
            "estimated_cost": 0,
            "assumption": ""
        }
    ],
    "total_estimated_cost": 0,
    "major_cost_drivers": [],
    "budget_risks": []
}
"""


def _build_instruction(context: ReadonlyContext) -> str:
    screenplay_json = json.dumps(
        context.state.get("screenplay_analysis", {}), indent=2
    )
    return f"""{BUDGET_AGENT_INSTRUCTION}

Create a preliminary production budget using ONLY this validated screenplay analysis.
Do not analyze the original screenplay again.

SCREENPLAY ANALYSIS:
{screenplay_json}

Return ONLY valid JSON matching BudgetAnalysis.
"""


budget_agent = Agent(
    name="budget_agent",
    model=MODEL,
    description=(
        "Creates preliminary production budget estimates "
        "from screenplay analysis."
    ),
    instruction=_build_instruction,
    output_schema=BudgetAnalysis,
    output_key="budget_analysis",
    include_contents="none",
)
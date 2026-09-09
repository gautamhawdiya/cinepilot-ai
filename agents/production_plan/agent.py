import json

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext

from schemas.production_plan import ProductionPlan


PRODUCTION_PLAN_INSTRUCTION = """
You are the Production Planning Agent for CinePilot AI.

Your job is to convert screenplay analysis, budget
information and external production research into a
practical production plan.

INPUTS:

1. ScreenplayAnalysis
2. BudgetAnalysis
3. ParallelResearch

Analyze:

- locations
- equipment
- props
- vehicles
- VFX requirements
- shoot days
- budget categories
- researched production resources

IMPORTANT:

Do not invent prices.

If ParallelResearch contains a price, you may use it.

If no price is available, explicitly say that the
resource requires a quote.

Do not treat search-result snippets as confirmed
availability.

Identify:

- best production strategy
- location strategy
- equipment strategy
- VFX strategy
- useful external resources
- budget adjustments
- major risks
- mitigation strategies

For every recommendation based on external research,
include the source URL.

Return ONLY valid JSON matching the
ProductionPlan schema.
"""


def _build_instruction(context: ReadonlyContext) -> str:
    screenplay_json = json.dumps(
        context.state.get("screenplay_analysis", {}), indent=2
    )
    budget_json = json.dumps(context.state.get("budget_analysis", {}), indent=2)
    research_json = json.dumps(
        context.state.get("production_research", {}), indent=2
    )

    # Set when a human producer re-plans an already-generated package with a
    # new constraint. It narrows the solution space; it never relaxes the
    # evidence rules above.
    directive = (context.state.get("producer_directive") or "").strip()
    directive_block = (
        f"""

PRODUCER DIRECTIVE (overrides your default choices):
{directive}

This is a binding instruction from the human producer. Re-plan so the strategy,
resources, budget adjustments and shoot approach satisfy it. If the directive
cannot be fully met with the researched evidence available, say so explicitly in
the risks and explain what would have to change. Do not silently ignore it, and
do not invent prices or availability to make it appear achievable.
"""
        if directive
        else ""
    )

    return f"""{PRODUCTION_PLAN_INSTRUCTION}

Create the practical production plan from these validated inputs.

SCREENPLAY ANALYSIS:
{screenplay_json}

BUDGET ANALYSIS:
{budget_json}

PRODUCTION RESEARCH:
{research_json}
{directive_block}
Use the research as evidence, preserving source URLs and verification requirements.
Do not invent prices, availability, locations, vendors, permits, or regulations.
Return ONLY valid JSON matching ProductionPlan.
"""


def build_production_plan_agent() -> LlmAgent:
    # ADK binds an agent instance to exactly one parent, so each workflow that
    # includes this stage needs its own instance.
    return LlmAgent(
        name="production_plan_agent",
        model="gemini-2.5-flash",
        description=(
            "Creates a production strategy by combining "
            "screenplay analysis, budget analysis and "
            "real-world production research."
        ),
        instruction=_build_instruction,
        output_schema=ProductionPlan,
        output_key="production_plan",
        include_contents="none",
    )


production_plan_agent = build_production_plan_agent()
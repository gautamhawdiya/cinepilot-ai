"""The CinePilot production pipeline as a genuine ADK multi-agent workflow.

Screenplay analysis feeds budget + production research (run concurrently),
which feed the production plan, which feeds the storyboard, which feeds the
call sheet. Each stage is a real Google ADK agent; ADK's own
SequentialAgent/ParallelAgent drive execution and pass validated state
between stages via each agent's `output_key` -- there is no hand-rolled
Python orchestration of *what* runs *when*, only of stage-status bookkeeping
and per-project file persistence around the single resulting event stream.
"""

from google.adk.agents import ParallelAgent, SequentialAgent

from agents.budget.agent import budget_agent
from agents.call_sheet.agent import call_sheet_agent
from agents.production_plan.agent import production_plan_agent
from agents.production_research.agent import production_research_agent
from agents.script.agent import script_agent
from agents.storyboard.agent import storyboard_agent


budget_and_research_agent = ParallelAgent(
    name="budget_and_research",
    sub_agents=[budget_agent, production_research_agent],
)

production_pipeline_agent = SequentialAgent(
    name="cinepilot_production_pipeline",
    sub_agents=[
        script_agent,
        budget_and_research_agent,
        production_plan_agent,
        storyboard_agent,
        call_sheet_agent,
    ],
)

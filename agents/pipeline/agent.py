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
from agents.call_sheet.agent import build_call_sheet_agent, call_sheet_agent
from agents.production_plan.agent import (
    build_production_plan_agent,
    production_plan_agent,
)
from agents.production_research.agent import production_research_agent
from agents.script.agent import script_agent
from agents.storyboard.agent import build_storyboard_agent, storyboard_agent


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

# Human-in-the-loop re-planning. When a producer changes a constraint after the
# first pass, the screenplay analysis, budget and research are still valid --
# only the downstream creative/logistical decisions need to be made again. This
# reuses the same agents, so a re-plan is genuinely the same reasoning under a
# new constraint rather than a separate code path.
replan_pipeline_agent = SequentialAgent(
    name="cinepilot_replan_pipeline",
    sub_agents=[
        build_production_plan_agent(),
        build_storyboard_agent(),
        build_call_sheet_agent(),
    ],
)

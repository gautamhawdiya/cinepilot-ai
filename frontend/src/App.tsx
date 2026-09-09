import { useEffect, useRef, useState } from "react";
import "./App.css";

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

type StageStatus = "pending" | "running" | "completed" | "failed";

type Stage = {
  status: StageStatus;
  error: string | null;
};

type Project = {
  project_id: string;
  title: string;
  screenplay_filename: string;
  screenplay_path: string;
  status: "created" | "running" | "completed" | "failed";
  current_stage: string | null;
  stages: Record<string, Stage>;
  error: string | null;
};

type ScreenplayCharacter = {
  name: string;
  description: string;
};

type ScreenplayScene = {
  scene_number: number;
  heading: string;
  location: string;
  time_of_day: string;
  characters: string[];
  summary: string;
};

type ScreenplayAnalysis = {
  title: string;
  genre: string;
  logline: string;
  characters: ScreenplayCharacter[];
  locations: string[];
  props: string[];
  vehicles: string[];
  vfx_requirements: string[];
  scenes: ScreenplayScene[];
  scene_count: number;
  estimated_shoot_days: number;
};

type BudgetCategory = {
  category: string;
  estimated_cost: number;
  assumption: string;
};

type BudgetAnalysis = {
  currency: string;
  shoot_days: number;
  categories: BudgetCategory[];
  total_estimated_cost: number;
  major_cost_drivers: string[];
  budget_risks: string[];
};

type ResearchFinding = {
  topic: string;
  finding: string;
  source_title: string;
  source_url: string;
  production_impact: string;
  confidence: string;
  requires_local_verification: boolean;
};

type ProductionResearch = {
  research_topic: string;
  findings: ResearchFinding[];
  production_recommendations: string[];
};

type ResourceRecommendation = {
  resource_type: string;
  recommendation: string;
  source_url: string | null;
  evidence: string;
  estimated_cost: string | null;
};

type BudgetAdjustment = {
  category: string;
  current_estimate: number;
  recommended_estimate: number;
  reason: string;
};

type ProductionPlan = {
  title: string;
  overall_strategy: string;
  location_strategy: string[];
  equipment_strategy: string[];
  vfx_strategy: string[];
  resource_recommendations: ResourceRecommendation[];
  budget_adjustments: BudgetAdjustment[];
  production_risks: string[];
  mitigation_strategies: string[];
  recommended_shoot_days: number;
  confidence: string;
};

type StoryboardShot = {
  shot_number: number;
  scene_number: number;
  screenplay_evidence: string;
  shot_type: string;
  camera_angle: string;
  camera_movement: string;
  subject: string;
  action: string;
  visual_description: string;
  lighting: string;
  mood: string;
  vfx_required: boolean;
  vfx_notes: string | null;
  image_prompt: string;
};

type StoryboardScene = {
  scene_number: number;
  scene_heading: string;
  source_scene_summary: string;
  visual_goal: string;
  shots: StoryboardShot[];
};

type Storyboard = {
  title: string;
  visual_style: string;
  cinematography_strategy: string;
  scenes: StoryboardScene[];
  total_shots: number;
};

type CallSheetScene = {
  scene_number: number;
  heading: string;
  summary: string;
  estimated_shooting_time: string | null;
  characters_present: string[];
  props: string[];
  vfx_requirements: string[];
  notes: string | null;
};

type CallSheetShootDay = {
  day_number: number;
  date: string | null;
  location: string;
  crew_call: string | null;
  first_shot: string | null;
  lunch_break: string | null;
  wrap: string | null;
  scenes_scheduled: CallSheetScene[];
  cast_on_call: string[];
  crew_on_call: string[];
  required_props: string[];
  required_equipment: string[];
  production_notes: string[];
  safety_and_logistics: string[];
};

type CallSheet = {
  call_sheet_id: string;
  project_title: string;
  production_company: string | null;
  project_manager: string;
  date: string | null;
  genre: string | null;
  logline: string | null;
  shoot_days_total: number;
  shoot_days: CallSheetShootDay[];
  cast_list: Array<{ character_name: string; actor_name: string }>;
  crew_list: Array<{ role: string; name: string }>;
};

type OutputView =
  | "screenplay"
  | "budget"
  | "research"
  | "plan"
  | "storyboard"
  | "call-sheet";

const extractSourceUrls = (value: string) =>
  value.match(/https?:\/\/[^,;\s]+/g) ?? [];

const sourceLabel = (url: string) => {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "View source";
  }
};

const formatNumber = (value: number) => String(value).padStart(2, "0");

const callSheetValue = (value: string | null) =>
  value?.trim() || "Not provided";

const callSheetDate = (value: string | null) =>
  value?.trim() || "Date not assigned";

const STAGE_LABELS: Record<string, string> = {
  screenplay_analysis: "Screenplay Analysis",
  budget_analysis: "Budget Analysis",
  production_research: "Production Research",
  production_plan: "Production Plan",
  storyboard: "Storyboard",
  call_sheet: "Call Sheet",
  storyboard_images: "Storyboard Images",
  pdf: "PDF",
};

// Which Google ADK agent (Gemini 2.5 Flash) executes each stage, and which
// tool it calls. Reflects the fixed pipeline wiring in
// api/services/pipeline.py — not a live execution trace.
const STAGE_AGENTS: Record<string, string> = {
  screenplay_analysis: "script_agent",
  budget_analysis: "budget_agent",
  production_research: "production_research_agent · Parallel Search",
  production_plan: "production_plan_agent",
  storyboard: "storyboard_agent",
  call_sheet: "call_sheet_agent",
  storyboard_images: "Gemini image generation (one per scene)",
  pdf: "Deterministic renderer (no LLM call)",
};

const STAGE_ORDER = [
  "screenplay_analysis",
  "budget_analysis",
  "production_research",
  "production_plan",
  "storyboard",
  "call_sheet",
  "storyboard_images",
  "pdf",
];

// The pipeline-progress grid shows "storyboard" and "storyboard_images" as one
// card -- image generation is a follow-on step of the same storyboard stage,
// not a separate agent the user needs to track independently.
const DISPLAY_STAGE_ORDER = [
  "screenplay_analysis",
  "budget_analysis",
  "production_research",
  "production_plan",
  "storyboard",
  "call_sheet",
  "pdf",
];

type StageStatusValue = "pending" | "running" | "completed" | "failed";

function combineStageStatus(
  a: StageStatusValue,
  b: StageStatusValue,
): StageStatusValue {
  if (a === "failed" || b === "failed") return "failed";
  if (a === "completed" && b === "completed") return "completed";
  if (a === "pending" && b === "pending") return "pending";
  return "running";
}

// Which output tab depends on which backend stage being complete before its
// data can be fetched and its tab unlocked.
const OUTPUT_STAGE: Record<OutputView, string> = {
  screenplay: "screenplay_analysis",
  budget: "budget_analysis",
  research: "production_research",
  plan: "production_plan",
  storyboard: "storyboard",
  "call-sheet": "call_sheet",
};

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [screenplay, setScreenplay] =
    useState<ScreenplayAnalysis | null>(null);
  const [isScreenplayLoading, setIsScreenplayLoading] = useState(false);
  const [screenplayError, setScreenplayError] = useState<string | null>(
    null,
  );
  const [budget, setBudget] = useState<BudgetAnalysis | null>(null);
  const [isBudgetLoading, setIsBudgetLoading] = useState(false);
  const [budgetError, setBudgetError] = useState<string | null>(null);
  const [research, setResearch] =
    useState<ProductionResearch | null>(null);
  const [isResearchLoading, setIsResearchLoading] =
    useState(false);
  const [researchError, setResearchError] =
    useState<string | null>(null);
  const [productionPlan, setProductionPlan] =
    useState<ProductionPlan | null>(null);
  const [isPlanLoading, setIsPlanLoading] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const [storyboard, setStoryboard] = useState<Storyboard | null>(null);
  const [isStoryboardLoading, setIsStoryboardLoading] = useState(false);
  const [storyboardError, setStoryboardError] = useState<string | null>(null);
  const [storyboardImages, setStoryboardImages] = useState<
    Record<string, string>
  >({});
  const [callSheet, setCallSheet] = useState<CallSheet | null>(null);
  const [isCallSheetLoading, setIsCallSheetLoading] = useState(false);
  const [callSheetError, setCallSheetError] = useState<string | null>(null);
  const [activeOutput, setActiveOutput] =
    useState<OutputView>("screenplay");

  const fileInputRef = useRef<HTMLInputElement>(null);

  const isRunning = project?.status === "running";
  const isCompleted = project?.status === "completed";
  const isFailed = project?.status === "failed";

  // Each output tab unlocks as soon as its own stage finishes, rather than
  // waiting for the entire pipeline -- so the demo reveals real agent
  // output live instead of gating everything behind one final reveal.
  const stageReady = (stage: string) =>
    project?.stages[stage]?.status === "completed";

  const isScreenplayReady = stageReady(OUTPUT_STAGE.screenplay);
  const isBudgetReady = stageReady(OUTPUT_STAGE.budget);
  const isResearchReady = stageReady(OUTPUT_STAGE.research);
  const isPlanReady = stageReady(OUTPUT_STAGE.plan);
  const isStoryboardReady = stageReady(OUTPUT_STAGE.storyboard);
  const isStoryboardImagesReady = stageReady("storyboard_images");
  const isCallSheetReady = stageReady(OUTPUT_STAGE["call-sheet"]);

  const anyOutputReady =
    isScreenplayReady ||
    isBudgetReady ||
    isResearchReady ||
    isPlanReady ||
    isStoryboardReady ||
    isCallSheetReady;

  useEffect(() => {
    if (!project?.project_id || !isRunning) {
      return;
    }

    const interval = window.setInterval(async () => {
      try {
        const response = await fetch(
          `${API_BASE}/api/projects/${project.project_id}/status`,
        );

        if (!response.ok) {
          throw new Error("Unable to retrieve pipeline status.");
        }

        const updatedProject: Project = await response.json();
        setProject(updatedProject);

        if (
          updatedProject.status === "completed" ||
          updatedProject.status === "failed"
        ) {
          window.clearInterval(interval);
        }
      } catch (err) {
        console.error(err);
      }
    }, 2000);

    return () => window.clearInterval(interval);
  }, [project?.project_id, isRunning]);

  useEffect(() => {
    if (!project?.project_id || !isScreenplayReady) {
      return;
    }

    let cancelled = false;

    const loadScreenplay = async () => {
      setIsScreenplayLoading(true);
      setScreenplayError(null);

      try {
        const response = await fetch(
          `${API_BASE}/api/projects/${project.project_id}/screenplay`,
        );

        if (!response.ok) {
          throw new Error("Unable to load the screenplay analysis.");
        }

        const result: ScreenplayAnalysis = await response.json();
        if (!cancelled) {
          setScreenplay(result);
        }
      } catch (err) {
        if (!cancelled) {
          setScreenplayError(
            err instanceof Error
              ? err.message
              : "Unable to load the screenplay analysis.",
          );
        }
      } finally {
        if (!cancelled) {
          setIsScreenplayLoading(false);
        }
      }
    };

    void loadScreenplay();

    return () => {
      cancelled = true;
    };
  }, [project?.project_id, isScreenplayReady]);

  useEffect(() => {
    if (!project?.project_id || !isBudgetReady) {
      return;
    }

    let cancelled = false;

    const loadBudget = async () => {
      setIsBudgetLoading(true);
      setBudgetError(null);

      try {
        const response = await fetch(
          `${API_BASE}/api/projects/${project.project_id}/budget`,
        );

        if (!response.ok) {
          throw new Error("Unable to load the budget analysis.");
        }

        const result: BudgetAnalysis = await response.json();
        if (!cancelled) {
          setBudget(result);
        }
      } catch (err) {
        if (!cancelled) {
          setBudgetError(
            err instanceof Error
              ? err.message
              : "Unable to load the budget analysis.",
          );
        }
      } finally {
        if (!cancelled) {
          setIsBudgetLoading(false);
        }
      }
    };

    void loadBudget();

    return () => {
      cancelled = true;
    };
  }, [project?.project_id, isBudgetReady]);

  useEffect(() => {
    if (!project?.project_id || !isResearchReady) {
      return;
    }

    let cancelled = false;

    const loadResearch = async () => {
      setIsResearchLoading(true);
      setResearchError(null);

      try {
        const response = await fetch(
          `${API_BASE}/api/projects/${project.project_id}/research`,
        );

        if (!response.ok) {
          throw new Error(
            "Unable to load the production research.",
          );
        }

        const result: ProductionResearch = await response.json();
        if (!cancelled) {
          setResearch(result);
        }
      } catch (err) {
        if (!cancelled) {
          setResearchError(
            err instanceof Error
              ? err.message
              : "Unable to load the production research.",
          );
        }
      } finally {
        if (!cancelled) {
          setIsResearchLoading(false);
        }
      }
    };

    void loadResearch();

    return () => {
      cancelled = true;
    };
  }, [project?.project_id, isResearchReady]);

  useEffect(() => {
    if (!project?.project_id || !isCallSheetReady) {
      return;
    }

    let cancelled = false;

    const loadCallSheet = async () => {
      setIsCallSheetLoading(true);
      setCallSheetError(null);

      try {
        const response = await fetch(
          `${API_BASE}/api/projects/${project.project_id}/call-sheet`,
        );

        if (!response.ok) {
          throw new Error("Unable to load the production call sheet.");
        }

        const result: CallSheet = await response.json();
        if (!cancelled) {
          setCallSheet(result);
        }
      } catch (err) {
        if (!cancelled) {
          setCallSheetError(
            err instanceof Error
              ? err.message
              : "Unable to load the production call sheet.",
          );
        }
      } finally {
        if (!cancelled) {
          setIsCallSheetLoading(false);
        }
      }
    };

    void loadCallSheet();

    return () => {
      cancelled = true;
    };
  }, [project?.project_id, isCallSheetReady]);

  useEffect(() => {
    if (!project?.project_id || !isStoryboardReady) {
      return;
    }

    let cancelled = false;

    const loadStoryboard = async () => {
      setIsStoryboardLoading(true);
      setStoryboardError(null);

      try {
        const response = await fetch(
          `${API_BASE}/api/projects/${project.project_id}/storyboard`,
        );

        if (!response.ok) {
          throw new Error("Unable to load the storyboard.");
        }

        const result: Storyboard = await response.json();
        if (!cancelled) {
          setStoryboard(result);
        }
      } catch (err) {
        if (!cancelled) {
          setStoryboardError(
            err instanceof Error
              ? err.message
              : "Unable to load the storyboard.",
          );
        }
      } finally {
        if (!cancelled) {
          setIsStoryboardLoading(false);
        }
      }
    };

    void loadStoryboard();

    return () => {
      cancelled = true;
    };
  }, [project?.project_id, isStoryboardReady]);

  useEffect(() => {
    if (!project?.project_id || !isStoryboardImagesReady) {
      return;
    }

    let cancelled = false;

    const loadStoryboardImages = async () => {
      try {
        const response = await fetch(
          `${API_BASE}/api/projects/${project.project_id}/storyboard/images`,
        );

        if (!response.ok) {
          return;
        }

        const result: Array<{
          scene_number: number;
          shot_number: number;
          url: string;
        }> = await response.json();

        if (!cancelled) {
          const byShot: Record<string, string> = {};
          for (const entry of result) {
            byShot[`${entry.scene_number}-${entry.shot_number}`] =
              `${API_BASE}${entry.url}`;
          }
          setStoryboardImages(byShot);
        }
      } catch {
        // Storyboard images are an enhancement, not a required output --
        // fail silently and keep showing the honest "Planning frame".
      }
    };

    void loadStoryboardImages();

    return () => {
      cancelled = true;
    };
  }, [project?.project_id, isStoryboardImagesReady]);

  useEffect(() => {
    if (!project?.project_id || !isPlanReady) {
      return;
    }

    let cancelled = false;

    const loadPlan = async () => {
      setIsPlanLoading(true);
      setPlanError(null);

      try {
        const response = await fetch(
          `${API_BASE}/api/projects/${project.project_id}/plan`,
        );

        if (!response.ok) {
          throw new Error("Unable to load the production plan.");
        }

        const result: ProductionPlan = await response.json();
        if (!cancelled) {
          setProductionPlan(result);
        }
      } catch (err) {
        if (!cancelled) {
          setPlanError(
            err instanceof Error
              ? err.message
              : "Unable to load the production plan.",
          );
        }
      } finally {
        if (!cancelled) {
          setIsPlanLoading(false);
        }
      }
    };

    void loadPlan();

    return () => {
      cancelled = true;
    };
  }, [project?.project_id, isPlanReady]);

  const selectFile = (selectedFile: File | null) => {
    setError(null);

    if (!selectedFile) {
      return;
    }

    if (selectedFile.type !== "application/pdf") {
      setError("Please select a screenplay PDF.");
      return;
    }

    setFile(selectedFile);
  };

  const createAndRunProject = async () => {
    if (!file) {
      setError("Please select a screenplay PDF first.");
      return;
    }

    setError(null);
    setIsCreating(true);

    try {
      const formData = new FormData();
      formData.append("screenplay", file);

      const createResponse = await fetch(
        `${API_BASE}/api/projects`,
        {
          method: "POST",
          body: formData,
        },
      );

      if (!createResponse.ok) {
        const body = await createResponse.text();
        throw new Error(
          body || "Unable to create the CinePilot project.",
        );
      }

      const createdProject: Project =
        await createResponse.json();

      setProject(createdProject);

      const runResponse = await fetch(
        `${API_BASE}/api/projects/${createdProject.project_id}/run`,
        {
          method: "POST",
        },
      );

      if (!runResponse.ok) {
        const body = await runResponse.text();
        throw new Error(
          body || "Unable to start the production pipeline.",
        );
      }

      const runningProject: Project =
        await runResponse.json();

      setProject(runningProject);
    } catch (err) {
      console.error(err);

      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong while starting CinePilot.",
      );
    } finally {
      setIsCreating(false);
    }
  };

  const resetProject = () => {
    setFile(null);
    setProject(null);
    setError(null);
    setScreenplay(null);
    setScreenplayError(null);
    setIsScreenplayLoading(false);
    setBudget(null);
    setBudgetError(null);
    setIsBudgetLoading(false);
    setResearch(null);
    setResearchError(null);
    setIsResearchLoading(false);
    setProductionPlan(null);
    setPlanError(null);
    setIsPlanLoading(false);
    setStoryboard(null);
    setStoryboardError(null);
    setIsStoryboardLoading(false);
    setStoryboardImages({});
    setCallSheet(null);
    setCallSheetError(null);
    setIsCallSheetLoading(false);
    setActiveOutput("research");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const completedCount = project
    ? STAGE_ORDER.filter(
        (stage) =>
          project.stages[stage]?.status === "completed",
      ).length
    : 0;

  const progress = project
    ? Math.round(
        (completedCount / STAGE_ORDER.length) * 100,
      )
    : 0;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">C</div>

          <div>
            <div className="brand-name">CinePilot</div>
            <div className="brand-subtitle">
              AI Production Copilot
            </div>
          </div>
        </div>

        <div className="topbar-status">
          <span className="status-dot" />
          Production Intelligence
        </div>
      </header>

      <main className="main-content">
        {!project && (
          <section className="hero">
            <div className="eyebrow">
              AI-POWERED FILM PRODUCTION
            </div>

            <h1>
              From screenplay
              <br />
              to production-ready.
            </h1>

            <p className="hero-copy">
              CinePilot coordinates screenplay analysis,
              budgeting, real-world research, planning,
              storyboarding and production documents
              through one intelligent workflow.
            </p>

            <div
              className={`upload-card ${
                file ? "has-file" : ""
              }`}
              onClick={() =>
                fileInputRef.current?.click()
              }
              onDragOver={(event) =>
                event.preventDefault()
              }
              onDrop={(event) => {
                event.preventDefault();
                selectFile(
                  event.dataTransfer.files?.[0] ?? null,
                );
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf"
                hidden
                onChange={(event) =>
                  selectFile(
                    event.target.files?.[0] ?? null,
                  )
                }
              />

              <div className="upload-icon">
                {file ? "✓" : "↑"}
              </div>

              {file ? (
                <>
                  <div className="file-name">
                    {file.name}
                  </div>

                  <div className="file-meta">
                    PDF screenplay ready
                  </div>
                </>
              ) : (
                <>
                  <div className="upload-title">
                    Upload screenplay
                  </div>

                  <div className="upload-description">
                    Drop a PDF here or click to browse
                  </div>
                </>
              )}
            </div>

            {error && (
              <div className="error-message">
                {error}
              </div>
            )}

            <button
              className="primary-button"
              disabled={!file || isCreating}
              onClick={createAndRunProject}
            >
              {isCreating
                ? "Starting CinePilot..."
                : "Start Production"}
            </button>

            <div className="hero-note">
              Your screenplay stays inside the CinePilot
              production workflow.
            </div>
          </section>
        )}

        {project && (
          <section className="dashboard">
            <div className="dashboard-header">
              <div>
                <div className="eyebrow">
                  PRODUCTION WORKSPACE
                </div>

                <h1>
                  {project.title !== "TBD"
                    ? project.title
                    : project.screenplay_filename}
                </h1>

                <p>
                  {project.screenplay_filename}
                </p>
              </div>

              <button
                className="secondary-button"
                onClick={resetProject}
                disabled={isRunning}
              >
                New Project
              </button>
            </div>

            <div className="progress-card">
              <div className="progress-header">
                <div>
                  <span className="progress-label">
                    Pipeline Progress
                  </span>

                  <strong>
                    {isCompleted
                      ? "Production Ready"
                      : isFailed
                        ? "Pipeline Failed"
                        : "Production in progress"}
                  </strong>
                </div>

                <span className="progress-number">
                  {progress}%
                </span>
              </div>

              <div className="progress-track">
                <div
                  className="progress-fill"
                  style={{
                    width: `${progress}%`,
                  }}
                />
              </div>
            </div>

            <div className="pipeline-grid">
              {DISPLAY_STAGE_ORDER.map((stage, index) => {
                const stageData = project.stages[stage];
                const imagesData =
                  stage === "storyboard"
                    ? project.stages["storyboard_images"]
                    : undefined;

                const status = imagesData
                  ? combineStageStatus(
                      stageData?.status ?? "pending",
                      imagesData.status ?? "pending",
                    )
                  : (stageData?.status ?? "pending");

                const agentLabel = imagesData
                  ? `${STAGE_AGENTS[stage]} + ${STAGE_AGENTS["storyboard_images"]}`
                  : STAGE_AGENTS[stage];

                const stageError =
                  stageData?.status === "failed"
                    ? stageData.error
                    : imagesData?.status === "failed"
                      ? imagesData.error
                      : null;

                return (
                  <div
                    className={`stage-card ${status}`}
                    key={stage}
                  >
                    <div className="stage-number">
                      {status === "completed"
                        ? "✓"
                        : status === "running"
                          ? "..."
                          : String(index + 1).padStart(
                              2,
                              "0",
                            )}
                    </div>

                    <div className="stage-content">
                      <div className="stage-title">
                        {STAGE_LABELS[stage]}
                      </div>

                      <div className="stage-status">
                        {status === "completed" && "Completed"}

                        {status === "running" &&
                          `Processing · ${agentLabel}`}

                        {status === "pending" &&
                          "Waiting"}

                        {status === "failed" &&
                          "Failed"}
                      </div>

                      {status === "failed" && stageError && (
                        <div className="stage-error">
                          {stageError}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {isCompleted && (
              <div className="completion-card">
                <div className="completion-icon">
                  ✓
                </div>

                <div>
                  <h2>
                    Your production package is ready.
                  </h2>

                  <p>
                    CinePilot completed all production
                    intelligence stages successfully.
                  </p>
                </div>

                <div className="completion-actions">
                  <button
                    className="primary-button small"
                    onClick={() =>
                      document
                        .getElementById("production-outputs")
                        ?.scrollIntoView({ behavior: "smooth" })
                    }
                  >
                    View Production Intelligence
                  </button>
                </div>
              </div>
            )}

            {anyOutputReady && (
              <nav
                className="output-navigation"
                id="production-outputs"
                aria-label="Production outputs"
              >
                <button
                  className={activeOutput === "screenplay" ? "active" : ""}
                  onClick={() => setActiveOutput("screenplay")}
                  disabled={!isScreenplayReady}
                  type="button"
                >
                  Screenplay Analysis
                </button>
                <button
                  className={activeOutput === "budget" ? "active" : ""}
                  onClick={() => setActiveOutput("budget")}
                  disabled={!isBudgetReady}
                  type="button"
                >
                  Budget
                </button>
                <button
                  className={activeOutput === "research" ? "active" : ""}
                  onClick={() => setActiveOutput("research")}
                  disabled={!isResearchReady}
                  type="button"
                >
                  Research
                </button>
                <button
                  className={activeOutput === "plan" ? "active" : ""}
                  onClick={() => setActiveOutput("plan")}
                  disabled={!isPlanReady}
                  type="button"
                >
                  Production Plan
                </button>
                <button
                  className={activeOutput === "storyboard" ? "active" : ""}
                  onClick={() => setActiveOutput("storyboard")}
                  disabled={!isStoryboardReady}
                  type="button"
                >
                  Storyboard
                </button>
                <button
                  className={activeOutput === "call-sheet" ? "active" : ""}
                  onClick={() => setActiveOutput("call-sheet")}
                  disabled={!isCallSheetReady}
                  type="button"
                >
                  Call Sheet
                </button>
              </nav>
            )}

            {isScreenplayReady && activeOutput === "screenplay" && (
              <section className="research-section" id="screenplay-analysis">
                <div className="research-header">
                  <div>
                    <div className="eyebrow">
                      SCREENPLAY INTELLIGENCE
                    </div>
                    <h2>Screenplay Analysis</h2>
                    <p>
                      What the Screenplay Agent extracted directly from the
                      uploaded PDF — the foundation every downstream stage
                      builds on.
                    </p>
                  </div>
                </div>

                {isScreenplayLoading && (
                  <div className="research-state">
                    Loading the screenplay analysis...
                  </div>
                )}

                {screenplayError && (
                  <div className="error-message large">
                    {screenplayError}
                  </div>
                )}

                {screenplay && (
                  <>
                    <div className="plan-summary">
                      <div className="plan-title-block">
                        <span>Title</span>
                        <h3>{screenplay.title}</h3>
                      </div>
                      <div>
                        <span>Genre</span>
                        <strong>{screenplay.genre || "Unspecified"}</strong>
                      </div>
                      <div>
                        <span>Scenes</span>
                        <strong>{screenplay.scene_count}</strong>
                      </div>
                      <div>
                        <span>Est. shoot days</span>
                        <strong>{screenplay.estimated_shoot_days}</strong>
                      </div>
                    </div>

                    <article className="overall-strategy-card">
                      <span>Logline</span>
                      <p>{screenplay.logline || "No logline extracted."}</p>
                    </article>

                    <div className="strategy-grid">
                      {[
                        ["Locations", screenplay.locations],
                        ["Props", screenplay.props],
                        ["Vehicles", screenplay.vehicles],
                      ].map(([title, items]) => (
                        <article className="strategy-card" key={title as string}>
                          <h3>{title as string}</h3>
                          <ol>
                            {(items as string[]).length > 0 ? (
                              (items as string[]).map((item, index) => (
                                <li key={`${title}-${index}`}>{item}</li>
                              ))
                            ) : (
                              <li>None identified</li>
                            )}
                          </ol>
                        </article>
                      ))}
                    </div>

                    {screenplay.vfx_requirements.length > 0 && (
                      <div className="plan-subsection">
                        <div className="subsection-heading">
                          <span>Visual effects</span>
                          <h3>VFX Requirements</h3>
                        </div>
                        <div className="resource-grid">
                          {screenplay.vfx_requirements.map((item, index) => (
                            <article className="resource-card" key={`${index}-${item}`}>
                              <p>{item}</p>
                            </article>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="plan-subsection">
                      <div className="subsection-heading">
                        <span>Cast</span>
                        <h3>Characters</h3>
                      </div>
                      <div className="resource-grid">
                        {screenplay.characters.map((character, index) => (
                          <article
                            className="resource-card"
                            key={`${character.name}-${index}`}
                          >
                            <span className="resource-type">
                              {character.name}
                            </span>
                            <p>
                              {character.description ||
                                "No description extracted."}
                            </p>
                          </article>
                        ))}
                      </div>
                    </div>

                    <div className="plan-subsection">
                      <div className="subsection-heading">
                        <span>Structure</span>
                        <h3>Scenes</h3>
                      </div>
                      <div className="resource-grid">
                        {screenplay.scenes.map((scene) => (
                          <article
                            className="resource-card"
                            key={scene.scene_number}
                          >
                            <span className="resource-type">
                              Scene {formatNumber(scene.scene_number)}
                            </span>
                            <p>{scene.heading}</p>
                            <div className="resource-evidence">
                              <span>
                                {[scene.location, scene.time_of_day]
                                  .filter(Boolean)
                                  .join(" · ") || "Location not specified"}
                              </span>
                              <p>
                                {scene.summary || "No summary extracted."}
                              </p>
                            </div>
                          </article>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </section>
            )}

            {isBudgetReady && activeOutput === "budget" && (
              <section className="plan-section" id="budget-analysis">
                <div className="plan-header">
                  <div>
                    <div className="eyebrow">
                      PRELIMINARY COST ESTIMATE
                    </div>
                    <h2>Budget Analysis</h2>
                    <p>
                      A planning-stage budget derived from the screenplay
                      analysis alone — not vendor-quoted pricing.
                    </p>
                  </div>
                </div>

                {isBudgetLoading && (
                  <div className="research-state">
                    Loading the budget analysis...
                  </div>
                )}

                {budgetError && (
                  <div className="error-message large">{budgetError}</div>
                )}

                {budget && (
                  <>
                    <div className="plan-summary">
                      <div className="plan-title-block">
                        <span>Total estimated cost</span>
                        <h3>
                          {budget.currency}{" "}
                          {budget.total_estimated_cost.toLocaleString()}
                        </h3>
                      </div>
                      <div>
                        <span>Shoot days</span>
                        <strong>{budget.shoot_days}</strong>
                      </div>
                      <div>
                        <span>Currency</span>
                        <strong>{budget.currency}</strong>
                      </div>
                    </div>

                    <div className="plan-subsection">
                      <div className="subsection-heading">
                        <span>Cost breakdown</span>
                        <h3>Budget Categories</h3>
                      </div>
                      <div className="budget-adjustments">
                        {budget.categories.map((category, index) => (
                          <article
                            className="budget-card"
                            key={`${category.category}-${index}`}
                          >
                            <h4>{category.category}</h4>
                            <div className="budget-values">
                              <div>
                                <span>Estimated cost</span>
                                <strong>
                                  {budget.currency}{" "}
                                  {category.estimated_cost.toLocaleString()}
                                </strong>
                              </div>
                            </div>
                            <p>{category.assumption}</p>
                          </article>
                        ))}
                      </div>
                    </div>

                    <div className="risk-grid">
                      <article className="risk-card">
                        <h3>Budget Risks</h3>
                        <ul>
                          {budget.budget_risks.length > 0 ? (
                            budget.budget_risks.map((risk, index) => (
                              <li key={`${index}-${risk}`}>{risk}</li>
                            ))
                          ) : (
                            <li>None identified</li>
                          )}
                        </ul>
                      </article>
                      <article className="mitigation-card">
                        <h3>Major Cost Drivers</h3>
                        <ul>
                          {budget.major_cost_drivers.length > 0 ? (
                            budget.major_cost_drivers.map((driver, index) => (
                              <li key={`${index}-${driver}`}>{driver}</li>
                            ))
                          ) : (
                            <li>None identified</li>
                          )}
                        </ul>
                      </article>
                    </div>
                  </>
                )}
              </section>
            )}

            {isResearchReady && activeOutput === "research" && (
              <section
                className="research-section"
                id="production-research"
              >
                <div className="research-header">
                  <div>
                    <div className="eyebrow">
                      REAL-WORLD PRODUCTION INTELLIGENCE
                    </div>
                    <h2>Production Research</h2>
                    <p>
                      Current permits, safety constraints, access
                      requirements and logistics that can affect the
                      shoot.
                    </p>
                  </div>

                  <div className="parallel-badge">
                    <span className="parallel-pulse" />
                    Live research powered by Parallel
                  </div>
                </div>

                {isResearchLoading && (
                  <div className="research-state">
                    Loading sourced production intelligence...
                  </div>
                )}

                {researchError && (
                  <div className="error-message large">
                    {researchError}
                  </div>
                )}

                {research && (
                  <>
                    <div className="research-topic">
                      <span>Research brief</span>
                      <p>{research.research_topic}</p>
                    </div>

                    <div className="findings-list">
                      {research.findings.map((finding, index) => {
                        const sourceUrls = extractSourceUrls(
                          finding.source_url,
                        );

                        return (
                          <article
                            className="finding-card"
                            key={`${finding.topic}-${index}`}
                          >
                            <div className="finding-meta">
                              <span
                                className={`confidence ${finding.confidence.toLowerCase()}`}
                              >
                                {finding.confidence} confidence
                              </span>
                              {finding.requires_local_verification && (
                                <span className="verification-badge">
                                  Local verification required
                                </span>
                              )}
                            </div>

                            <h3>{finding.topic}</h3>
                            <p>{finding.finding}</p>

                            <div className="production-impact">
                              <span>Production impact</span>
                              <p>{finding.production_impact}</p>
                            </div>

                            <div className="research-sources">
                              <span>Sources</span>
                              {sourceUrls.length > 0 ? (
                                <div className="source-links">
                                  {sourceUrls.map((url) => (
                                    <a
                                      href={url}
                                      key={url}
                                      target="_blank"
                                      rel="noreferrer"
                                    >
                                      {sourceLabel(url)}
                                    </a>
                                  ))}
                                </div>
                              ) : (
                                <p>{finding.source_title}</p>
                              )}
                            </div>
                          </article>
                        );
                      })}
                    </div>

                    <div className="recommendations-card">
                      <h3>Production Recommendations</h3>
                      <ol>
                        {research.production_recommendations.map(
                          (recommendation, index) => (
                            <li key={`${index}-${recommendation}`}>
                              {recommendation}
                            </li>
                          ),
                        )}
                      </ol>
                    </div>
                  </>
                )}
              </section>
            )}

            {isPlanReady && activeOutput === "plan" && (
              <section className="plan-section" id="production-plan">
                <div className="plan-header">
                  <div>
                    <div className="eyebrow">
                      ACTIONABLE PRODUCTION STRATEGY
                    </div>
                    <h2>Production Plan</h2>
                    <p>
                      A practical plan synthesized from screenplay
                      requirements, budget constraints and sourced
                      production research.
                    </p>
                  </div>
                </div>

                <div className="decision-lineage">
                  <span>Screenplay Analysis</span>
                  <strong>+</strong>
                  <span>Budget</span>
                  <strong>+</strong>
                  <span>Parallel Production Research</span>
                  <strong className="lineage-arrow">↓</strong>
                  <span className="lineage-result">
                    Actionable Production Plan
                  </span>
                </div>

                {isPlanLoading && (
                  <div className="research-state">
                    Loading the actionable production plan...
                  </div>
                )}

                {planError && (
                  <div className="error-message large">{planError}</div>
                )}

                {productionPlan && (
                  <>
                    <div className="plan-summary">
                      <div className="plan-title-block">
                        <span>Project</span>
                        <h3>{productionPlan.title}</h3>
                      </div>
                      <div>
                        <span>Recommended shoot</span>
                        <strong>
                          {productionPlan.recommended_shoot_days} days
                        </strong>
                      </div>
                      <div>
                        <span>Plan confidence</span>
                        <strong className="plan-confidence">
                          {productionPlan.confidence}
                        </strong>
                      </div>
                    </div>

                    <article className="overall-strategy-card">
                      <span>Overall strategy</span>
                      <p>{productionPlan.overall_strategy}</p>
                    </article>

                    <div className="strategy-grid">
                      {[
                        ["Location Strategy", productionPlan.location_strategy],
                        ["Equipment Strategy", productionPlan.equipment_strategy],
                        ["VFX Strategy", productionPlan.vfx_strategy],
                      ].map(([title, items]) => (
                        <article className="strategy-card" key={title as string}>
                          <h3>{title as string}</h3>
                          <ol>
                            {(items as string[]).map((item, index) => (
                              <li key={`${title}-${index}`}>{item}</li>
                            ))}
                          </ol>
                        </article>
                      ))}
                    </div>

                    <div className="plan-subsection">
                      <div className="subsection-heading">
                        <span>Evidence-backed sourcing</span>
                        <h3>Resource Recommendations</h3>
                      </div>
                      <div className="resource-grid">
                        {productionPlan.resource_recommendations.map(
                          (resource, index) => {
                            const sourceUrls = extractSourceUrls(
                              resource.source_url ?? "",
                            );

                            return (
                              <article
                                className="resource-card"
                                key={`${resource.resource_type}-${index}`}
                              >
                                <span className="resource-type">
                                  {resource.resource_type}
                                </span>
                                <p>{resource.recommendation}</p>
                                {resource.evidence && (
                                  <div className="resource-evidence">
                                    <span>Evidence</span>
                                    <p>{resource.evidence}</p>
                                  </div>
                                )}
                                {resource.estimated_cost && (
                                  <div className="cost-label">
                                    <span>Estimated cost</span>
                                    <strong>{resource.estimated_cost}</strong>
                                  </div>
                                )}
                                {sourceUrls.length > 0 && (
                                  <div className="source-links">
                                    {sourceUrls.map((url) => (
                                      <a
                                        href={url}
                                        key={url}
                                        target="_blank"
                                        rel="noreferrer"
                                      >
                                        {sourceLabel(url)}
                                      </a>
                                    ))}
                                  </div>
                                )}
                              </article>
                            );
                          },
                        )}
                      </div>
                    </div>

                    <div className="plan-subsection">
                      <div className="subsection-heading">
                        <span>Cost decisions</span>
                        <h3>Budget Adjustments</h3>
                      </div>
                      <div className="budget-adjustments">
                        {productionPlan.budget_adjustments.map(
                          (adjustment, index) => (
                            <article
                              className="budget-card"
                              key={`${adjustment.category}-${index}`}
                            >
                              <h4>{adjustment.category}</h4>
                              <div className="budget-values">
                                <div>
                                  <span>Current estimate</span>
                                  <strong>
                                    {adjustment.current_estimate.toLocaleString()}
                                  </strong>
                                </div>
                                <div>
                                  <span>Recommended estimate</span>
                                  <strong>
                                    {adjustment.recommended_estimate.toLocaleString()}
                                  </strong>
                                </div>
                              </div>
                              <p>{adjustment.reason}</p>
                            </article>
                          ),
                        )}
                      </div>
                    </div>

                    <div className="risk-grid">
                      <article className="risk-card">
                        <h3>Production Risks</h3>
                        <ul>
                          {productionPlan.production_risks.map(
                            (risk, index) => (
                              <li key={`${index}-${risk}`}>{risk}</li>
                            ),
                          )}
                        </ul>
                      </article>
                      <article className="mitigation-card">
                        <h3>Mitigation Strategies</h3>
                        <ul>
                          {productionPlan.mitigation_strategies.map(
                            (strategy, index) => (
                              <li key={`${index}-${strategy}`}>{strategy}</li>
                            ),
                          )}
                        </ul>
                      </article>
                    </div>
                  </>
                )}
              </section>
            )}

            {isStoryboardReady && activeOutput === "storyboard" && (
              <section className="storyboard-section" id="storyboard">
                <div className="storyboard-header">
                  <div>
                    <div className="eyebrow">
                      SHOT-BY-SHOT VISUAL EXECUTION
                    </div>
                    <h2>Storyboard</h2>
                    <p>
                      The screenplay translated into a practical camera plan,
                      informed by the approved production strategy.
                    </p>
                  </div>
                  <div className="storyboard-data-badge">
                    Planning data
                  </div>
                </div>

                <div className="production-chain" aria-label="Production workflow">
                  <span>Screenplay</span>
                  <strong>→</strong>
                  <span>AI Analysis</span>
                  <strong>→</strong>
                  <span>Budget</span>
                  <strong>→</strong>
                  <span>Real-world Research</span>
                  <strong>→</strong>
                  <span>Production Plan</span>
                  <strong>→</strong>
                  <span className="chain-current">Storyboard</span>
                  <strong>→</strong>
                  <span>Call Sheet</span>
                  <strong>→</strong>
                  <span>Production Package</span>
                </div>

                {isStoryboardLoading && (
                  <div className="research-state">
                    Loading the storyboard shot plan...
                  </div>
                )}

                {storyboardError && (
                  <div className="error-message large">{storyboardError}</div>
                )}

                {storyboard && (
                  <>
                    <div className="storyboard-summary">
                      <div>
                        <span>Project</span>
                        <h3>{storyboard.title}</h3>
                      </div>
                      <div>
                        <span>Scenes</span>
                        <strong>{storyboard.scenes.length}</strong>
                      </div>
                      <div>
                        <span>Total shots</span>
                        <strong>{storyboard.total_shots}</strong>
                      </div>
                    </div>

                    <div className="storyboard-direction-grid">
                      <article>
                        <span>Visual style</span>
                        <p>{storyboard.visual_style}</p>
                      </article>
                      <article>
                        <span>Cinematography strategy</span>
                        <p>{storyboard.cinematography_strategy}</p>
                      </article>
                    </div>

                    <div className="storyboard-scenes">
                      {storyboard.scenes.map((scene) => (
                        <article
                          className="storyboard-scene"
                          key={scene.scene_number}
                        >
                          <header className="scene-header">
                            <div className="scene-number">
                              Scene {formatNumber(scene.scene_number)}
                            </div>
                            <div>
                              <h3>{scene.scene_heading}</h3>
                              <p>{scene.source_scene_summary}</p>
                            </div>
                            <div className="scene-shot-count">
                              {scene.shots.length} {scene.shots.length === 1 ? "shot" : "shots"}
                            </div>
                          </header>

                          <div className="scene-visual-goal">
                            <span>Visual goal</span>
                            <p>{scene.visual_goal}</p>
                          </div>

                          <div className="storyboard-shot-grid">
                            {scene.shots.map((shot) => {
                              const generatedImageUrl =
                                storyboardImages[
                                  `${scene.scene_number}-${shot.shot_number}`
                                ];

                              return (
                              <article
                                className="storyboard-shot"
                                key={`${scene.scene_number}-${shot.shot_number}`}
                              >
                                <div className="storyboard-frame">
                                  <div className="frame-label">
                                    SC {formatNumber(scene.scene_number)} · SH {formatNumber(shot.shot_number)}
                                  </div>
                                  {generatedImageUrl ? (
                                    <img
                                      src={generatedImageUrl}
                                      alt={`Generated preview for scene ${scene.scene_number}`}
                                    />
                                  ) : (
                                    <div className="frame-content">
                                      <strong>SHOT {formatNumber(shot.shot_number)}</strong>
                                      <span>Planning frame</span>
                                    </div>
                                  )}
                                  <div className="frame-subject">{shot.subject}</div>
                                </div>

                                <div className="shot-card-body">
                                  <div className="shot-heading">
                                    <span className="shot-type">{shot.shot_type}</span>
                                    {shot.vfx_required && (
                                      <span className="vfx-badge">VFX</span>
                                    )}
                                  </div>

                                  <p className="shot-description">
                                    {shot.visual_description}
                                  </p>

                                  <dl className="shot-specs">
                                    <div>
                                      <dt>Camera angle</dt>
                                      <dd>{shot.camera_angle}</dd>
                                    </div>
                                    <div>
                                      <dt>Movement</dt>
                                      <dd>{shot.camera_movement}</dd>
                                    </div>
                                    <div>
                                      <dt>Lighting</dt>
                                      <dd>{shot.lighting}</dd>
                                    </div>
                                    <div>
                                      <dt>Mood</dt>
                                      <dd>{shot.mood}</dd>
                                    </div>
                                  </dl>

                                  <div className="shot-action">
                                    <span>Action</span>
                                    <p>{shot.action}</p>
                                  </div>

                                  {shot.vfx_notes && (
                                    <div className="shot-vfx-notes">
                                      <span>VFX notes</span>
                                      <p>{shot.vfx_notes}</p>
                                    </div>
                                  )}

                                  <details className="shot-details">
                                    <summary>Production references</summary>
                                    <div>
                                      <span>Screenplay evidence</span>
                                      <p>{shot.screenplay_evidence}</p>
                                    </div>
                                    <div>
                                      <span>Image prompt</span>
                                      <p>{shot.image_prompt}</p>
                                    </div>
                                  </details>
                                </div>
                              </article>
                              );
                            })}
                          </div>
                        </article>
                      ))}
                    </div>
                  </>
                )}
              </section>
            )}

            {isCallSheetReady && activeOutput === "call-sheet" && (
              <section className="call-sheet-section" id="call-sheet">
                <div className="call-sheet-header">
                  <div>
                    <div className="eyebrow">
                      SHOOT-DAY OPERATIONS
                    </div>
                    <h2>Production Call Sheet</h2>
                    <p>
                      The operational shoot plan generated from the screenplay,
                      researched constraints, approved production strategy and
                      storyboard requirements.
                    </p>
                  </div>
                  <div className="call-sheet-status-badge">
                    Production document
                  </div>
                </div>

                <div className="production-chain" aria-label="Production workflow">
                  <span>Screenplay</span>
                  <strong>→</strong>
                  <span>AI Analysis</span>
                  <strong>→</strong>
                  <span>Budget</span>
                  <strong>→</strong>
                  <span>Real-world Research</span>
                  <strong>→</strong>
                  <span>Production Plan</span>
                  <strong>→</strong>
                  <span>Storyboard</span>
                  <strong>→</strong>
                  <span className="chain-current">Call Sheet</span>
                </div>

                {isCallSheetLoading && (
                  <div className="research-state">
                    Loading the shoot-day operational document...
                  </div>
                )}

                {callSheetError && (
                  <div className="error-message large">{callSheetError}</div>
                )}

                {callSheet && (
                  <>
                    <div className="call-sheet-title-card">
                      <div className="call-sheet-title-copy">
                        <span>Production</span>
                        <h3>{callSheet.project_title}</h3>
                        <p>{callSheet.logline || "No logline provided."}</p>
                      </div>
                      <div className="call-sheet-document-id">
                        <span>Call Sheet ID</span>
                        <strong>{callSheet.call_sheet_id}</strong>
                      </div>
                      <a
                        className="call-sheet-download"
                        href={`${API_BASE}/api/projects/${project.project_id}/call-sheet/pdf`}
                        download
                      >
                        Download Call Sheet PDF
                      </a>
                    </div>

                    <div className="call-sheet-overview-grid">
                      <article>
                        <span>Production company</span>
                        <strong>{callSheetValue(callSheet.production_company)}</strong>
                      </article>
                      <article>
                        <span>Project manager</span>
                        <strong>{callSheetValue(callSheet.project_manager)}</strong>
                      </article>
                      <article>
                        <span>Genre</span>
                        <strong>{callSheetValue(callSheet.genre)}</strong>
                      </article>
                      <article>
                        <span>Total shoot days</span>
                        <strong>{callSheet.shoot_days_total}</strong>
                      </article>
                    </div>

                    <div className="shoot-days-list">
                      {callSheet.shoot_days.map((day) => (
                        <article className="shoot-day-card" key={day.day_number}>
                          <header className="shoot-day-header">
                            <div className="shoot-day-number">
                              <span>Shoot day</span>
                              <strong>{formatNumber(day.day_number)}</strong>
                            </div>
                            <div>
                              <span className="shoot-day-date">
                                {callSheetDate(day.date)}
                              </span>
                              <h3>{day.location}</h3>
                            </div>
                            <div className="shoot-day-scene-count">
                              <strong>{day.scenes_scheduled.length}</strong>
                              <span>
                                {day.scenes_scheduled.length === 1 ? "scene" : "scenes"}
                              </span>
                            </div>
                          </header>

                          <div className="shoot-day-call-strip">
                            <div>
                              <span>Crew call</span>
                              <strong>{callSheetValue(day.crew_call)}</strong>
                            </div>
                            <div>
                              <span>First shot</span>
                              <strong>{callSheetValue(day.first_shot)}</strong>
                            </div>
                            <div>
                              <span>Lunch</span>
                              <strong>{callSheetValue(day.lunch_break)}</strong>
                            </div>
                            <div>
                              <span>Wrap</span>
                              <strong>{callSheetValue(day.wrap)}</strong>
                            </div>
                          </div>

                          <div className="call-sheet-subsection">
                            <div className="call-sheet-subsection-heading">
                              <span>Scheduled work</span>
                              <h4>Scenes</h4>
                            </div>
                            <div className="call-sheet-scenes">
                              {day.scenes_scheduled.map((scene) => (
                                <article
                                  className="call-sheet-scene"
                                  key={`${day.day_number}-${scene.scene_number}`}
                                >
                                  <header>
                                    <div className="call-sheet-scene-number">
                                      Scene {formatNumber(scene.scene_number)}
                                    </div>
                                    <h5>{scene.heading}</h5>
                                    <span>{callSheetValue(scene.estimated_shooting_time)}</span>
                                  </header>
                                  <p>{scene.summary}</p>
                                  <div className="call-sheet-scene-details">
                                    <div>
                                      <span>Characters</span>
                                      <p>{scene.characters_present.join(", ") || "None listed"}</p>
                                    </div>
                                    <div>
                                      <span>Props</span>
                                      <p>{scene.props.join(", ") || "None listed"}</p>
                                    </div>
                                    <div>
                                      <span>VFX requirements</span>
                                      <p>{scene.vfx_requirements.join("; ") || "None listed"}</p>
                                    </div>
                                  </div>
                                  {scene.notes && (
                                    <div className="call-sheet-scene-note">
                                      <span>Scene notes</span>
                                      <p>{scene.notes}</p>
                                    </div>
                                  )}
                                </article>
                              ))}
                            </div>
                          </div>

                          <div className="day-operations-grid">
                            <section>
                              <h4>Cast on call</h4>
                              <ul>
                                {(day.cast_on_call.length ? day.cast_on_call : ["None listed"]).map(
                                  (item, index) => <li key={`${item}-${index}`}>{item}</li>,
                                )}
                              </ul>
                            </section>
                            <section>
                              <h4>Crew on call</h4>
                              <ul>
                                {(day.crew_on_call.length ? day.crew_on_call : ["None listed"]).map(
                                  (item, index) => <li key={`${item}-${index}`}>{item}</li>,
                                )}
                              </ul>
                            </section>
                            <section>
                              <h4>Required props</h4>
                              <ul>
                                {(day.required_props.length ? day.required_props : ["None listed"]).map(
                                  (item, index) => <li key={`${item}-${index}`}>{item}</li>,
                                )}
                              </ul>
                            </section>
                            <section>
                              <h4>Required equipment</h4>
                              <ul>
                                {(day.required_equipment.length ? day.required_equipment : ["None listed"]).map(
                                  (item, index) => <li key={`${item}-${index}`}>{item}</li>,
                                )}
                              </ul>
                            </section>
                          </div>

                          <div className="day-notes-grid">
                            <section className="production-notes-panel">
                              <h4>Production notes</h4>
                              <ol>
                                {(day.production_notes.length ? day.production_notes : ["None listed"]).map(
                                  (item, index) => <li key={`${index}-${item}`}>{item}</li>,
                                )}
                              </ol>
                            </section>
                            <section className="safety-panel">
                              <h4>Safety &amp; logistics</h4>
                              <ol>
                                {(day.safety_and_logistics.length ? day.safety_and_logistics : ["None listed"]).map(
                                  (item, index) => <li key={`${index}-${item}`}>{item}</li>,
                                )}
                              </ol>
                            </section>
                          </div>
                        </article>
                      ))}
                    </div>

                    <div className="master-people-grid">
                      <section>
                        <div className="call-sheet-subsection-heading">
                          <span>Master list</span>
                          <h4>Cast</h4>
                        </div>
                        <div className="master-list">
                          {callSheet.cast_list.map((cast) => (
                            <div key={cast.character_name}>
                              <strong>{cast.character_name}</strong>
                              <span>{cast.actor_name}</span>
                            </div>
                          ))}
                        </div>
                      </section>
                      <section>
                        <div className="call-sheet-subsection-heading">
                          <span>Master list</span>
                          <h4>Crew</h4>
                        </div>
                        <div className="master-list">
                          {callSheet.crew_list.map((crew) => (
                            <div key={crew.role}>
                              <strong>{crew.role}</strong>
                              <span>{crew.name}</span>
                            </div>
                          ))}
                        </div>
                      </section>
                    </div>
                  </>
                )}
              </section>
            )}

            {isFailed && (
              <div className="error-message large">
                {project.error ||
                  "The production pipeline failed."}
              </div>
            )}
          </section>
        )}
      </main>

      <footer className="footer">
        <span>CinePilot AI</span>
        <span>
          Intelligent production orchestration
        </span>
      </footer>
    </div>
  );
}

export default App;

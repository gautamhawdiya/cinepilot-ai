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

type OutputView = "research" | "plan" | "storyboard";

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

const STAGE_LABELS: Record<string, string> = {
  screenplay_analysis: "Screenplay Analysis",
  budget_analysis: "Budget Analysis",
  production_research: "Production Research",
  production_plan: "Production Plan",
  storyboard: "Storyboard",
  call_sheet: "Call Sheet",
  pdf: "PDF",
};

const STAGE_ORDER = [
  "screenplay_analysis",
  "budget_analysis",
  "production_research",
  "production_plan",
  "storyboard",
  "call_sheet",
  "pdf",
];

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
  const [activeOutput, setActiveOutput] =
    useState<OutputView>("research");

  const fileInputRef = useRef<HTMLInputElement>(null);

  const isRunning = project?.status === "running";
  const isCompleted = project?.status === "completed";
  const isFailed = project?.status === "failed";

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
    if (!project?.project_id || !isCompleted) {
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
  }, [project?.project_id, isCompleted]);

  useEffect(() => {
    if (!project?.project_id || !isCompleted) {
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
  }, [project?.project_id, isCompleted]);

  useEffect(() => {
    if (!project?.project_id || !isCompleted) {
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
  }, [project?.project_id, isCompleted]);

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
    setResearch(null);
    setResearchError(null);
    setIsResearchLoading(false);
    setProductionPlan(null);
    setPlanError(null);
    setIsPlanLoading(false);
    setStoryboard(null);
    setStoryboardError(null);
    setIsStoryboardLoading(false);
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
              {STAGE_ORDER.map((stage, index) => {
                const stageData =
                  project.stages[stage];

                const status =
                  stageData?.status ?? "pending";

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
                        {status === "completed" &&
                          "Completed"}

                        {status === "running" &&
                          "Processing"}

                        {status === "pending" &&
                          "Waiting"}

                        {status === "failed" &&
                          "Failed"}
                      </div>

                      {status === "failed" &&
                        stageData.error && (
                          <div className="stage-error">
                            {stageData.error}
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

            {isCompleted && (
              <nav
                className="output-navigation"
                id="production-outputs"
                aria-label="Production outputs"
              >
                <button
                  className={activeOutput === "research" ? "active" : ""}
                  onClick={() => setActiveOutput("research")}
                  type="button"
                >
                  Research
                </button>
                <button
                  className={activeOutput === "plan" ? "active" : ""}
                  onClick={() => setActiveOutput("plan")}
                  type="button"
                >
                  Production Plan
                </button>
                <button
                  className={activeOutput === "storyboard" ? "active" : ""}
                  onClick={() => setActiveOutput("storyboard")}
                  type="button"
                >
                  Storyboard
                </button>
              </nav>
            )}

            {isCompleted && activeOutput === "research" && (
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

            {isCompleted && activeOutput === "plan" && (
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

            {isCompleted && activeOutput === "storyboard" && (
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
                            {scene.shots.map((shot) => (
                              <article
                                className="storyboard-shot"
                                key={`${scene.scene_number}-${shot.shot_number}`}
                              >
                                <div className="storyboard-frame">
                                  <div className="frame-label">
                                    SC {formatNumber(scene.scene_number)} · SH {formatNumber(shot.shot_number)}
                                  </div>
                                  <div className="frame-content">
                                    <strong>SHOT {formatNumber(shot.shot_number)}</strong>
                                    <span>Planning frame</span>
                                  </div>
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
                            ))}
                          </div>
                        </article>
                      ))}
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

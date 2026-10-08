"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Boxes,
  ChevronRight,
  CircleHelp,
  Database,
  FlaskConical,
  Globe2,
  LayoutDashboard,
  LockKeyhole,
  LogOut,
  Plus,
  Settings2,
  Sparkles,
  Smartphone,
  Terminal,
  Workflow,
} from "lucide-react";
import {
  api,
  Language,
  number,
  Source,
  Dataset,
  Run,
  Model,
  User,
} from "@/lib/api";
import { Action, Badge, Empty, ErrorNotice, Loading, Private } from "./ui";
import { LanguageForm, SettingsView } from "./language";
import { DictionaryView } from "./dictionary";
import { OfflineView } from "./offline";
import {
  DatasetsView,
  TrainingView,
  ModelsView,
  PlaygroundView,
} from "./training";
const sections = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "dictionary", label: "Dictionary", icon: BookOpen },
  { id: "datasets", label: "Datasets", icon: Database },
  { id: "offline", label: "Offline phone", icon: Smartphone },
  { id: "training", label: "Training", icon: Workflow },
  { id: "models", label: "Models", icon: Boxes },
  { id: "playground", label: "Playground", icon: FlaskConical },
  { id: "settings", label: "Settings", icon: Settings2 },
];
export function Workspace({
  languageId,
  section = "home",
}: {
  languageId?: string;
  section?: string;
}) {
  const [user, setUser] = useState<User | null>(null),
    [authReady, setAuthReady] = useState(false),
    [languages, setLanguages] = useState<Language[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const [sources, setSources] = useState<Source[]>([]),
    [datasets, setDatasets] = useState<Dataset[]>([]),
    [runs, setRuns] = useState<Run[]>([]),
    [models, setModels] = useState<Model[]>([]);
  const language = languages.find((l) => l.id === languageId);
  async function refresh() {
    const ls = await api<Language[]>("/languages");
    setLanguages(ls);
    if (languageId) {
      const [s, d, r, m] = await Promise.all([
        api<Source[]>(`/languages/${languageId}/dictionaries`),
        api<Dataset[]>(`/languages/${languageId}/datasets`),
        api<Run[]>(`/languages/${languageId}/training-runs`),
        api<Model[]>(`/languages/${languageId}/models`),
      ]);
      setSources(s);
      setDatasets(d);
      setRuns(r);
      setModels(m);
    }
  }
  useEffect(() => {
    api<User>("/me")
      .then(setUser)
      .catch(() => {})
      .finally(() => setAuthReady(true));
  }, []);
  useEffect(() => {
    if (user) {
      setLoading(true);
      refresh()
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    } /* stable route-scoped load */
  }, [user, languageId]);
  useEffect(() => {
    if (
      !runs.some(
        (r) => !["COMPLETED", "FAILED", "CANCELLED"].includes(r.status),
      )
    )
      return;
    const timer = setInterval(
      () => refresh().catch((e) => setError(e.message)),
      4000,
    );
    return () => clearInterval(timer);
  }, [runs, languageId]);
  if (!authReady)
    return (
      <div className="connect-page">
        <Loading />
      </div>
    );
  if (!user) return <Connect onConnect={setUser} />;
  const canEdit = user.role !== "viewer";
  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <aside className="sidebar">
        <Link className="brand" href="/">
          <span className="brand-icon">
            <Workflow size={21} />
          </span>
          <span>
            LangAI<span className="brand-sub">LANGUAGE WORKSPACES</span>
          </span>
        </Link>
        <div className="workspace-label">
          <span className="avatar">L</span>
          <span>
            My workspace<small>Private infrastructure</small>
          </span>
          <LockKeyhole size={14} />
        </div>
        <Link className={`nav-item ${!languageId ? "active" : ""}`} href="/">
          <Globe2 size={17} />
          All languages<span className="nav-count">{languages.length}</span>
        </Link>
        {language && (
          <>
            <div className="nav-section">{language.name}</div>
            <nav aria-label="Language">
              {sections.map(({ id, label, icon: Icon }) => (
                <Link
                  key={id}
                  href={`/languages/${language.id}/${id}`}
                  className={`nav-item ${section === id ? "active" : ""}`}
                >
                  <Icon size={17} />
                  {label}
                  {id === "dictionary" && (
                    <span className="nav-count">
                      {number(language.entry_count)}
                    </span>
                  )}
                </Link>
              ))}
            </nav>
          </>
        )}
        <div className="sidebar-bottom">
          <div className="local-note">
            <span className="status-dot" />
            <div>
              Your data stays here
              <small>Training runs in your infrastructure.</small>
            </div>
          </div>
          <a
            href="/api/proxy/docs"
            target="_blank"
            rel="noreferrer"
            className="nav-item"
          >
            <Terminal size={16} />
            API reference
          </a>
          <button
            className="nav-item"
            onClick={async () => {
              await fetch("/api/session", { method: "DELETE" });
              setUser(null);
            }}
          >
            <LogOut size={16} />
            Disconnect
          </button>
          <div className="sidebar-version">
            LangAI <span>V1 · Dictionary studio</span>
          </div>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div>
            <span>Workspace</span>
            <ChevronRight size={14} />
            {language ? (
              <>
                <Link href="/">Languages</Link>
                <ChevronRight size={14} />
                <span className="strong">{language.name}</span>
              </>
            ) : (
              <span className="strong">Languages</span>
            )}
          </div>
          <div>
            <Badge tone="success">
              <span className="status-dot" />
              Connected
            </Badge>
            <span className="role">{user.role}</span>
          </div>
        </header>
        <main id="main">
          <ErrorNotice error={error} />
          {loading ? (
            <Loading />
          ) : section === "new" ? (
            <LanguageForm />
          ) : !languageId ? (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">YOUR LANGUAGE STUDIO</div>
                  <h1>Languages</h1>
                  <p>From dictionary to a useful language representation.</p>
                </div>
                {canEdit && (
                  <Link href="/languages/new" className="button">
                    <Plus size={16} />
                    Create language
                  </Link>
                )}
              </div>
              <div className="intro-banner">
                <div className="intro-symbol">
                  <BookOpen size={30} />
                </div>
                <div>
                  <h2>Start with the words. Keep the knowledge connected.</h2>
                  <p>
                    A private place to prepare dictionaries, train models and
                    understand what they learn.
                  </p>
                </div>
                <Private />
              </div>
              {languages.length ? (
                <div className="language-list">
                  <div className="list-heading">
                    <span>Language</span>
                    <span>Dictionary entries</span>
                    <span>Models</span>
                    <span>Access</span>
                  </div>
                  {languages.map((l) => (
                    <Link
                      className="language-row"
                      href={`/languages/${l.id}`}
                      key={l.id}
                    >
                      <div>
                        <span className="language-initial">{l.name[0]}</span>
                        <div>
                          <h3>{l.name}</h3>
                          <p>{l.source_community || "Language workspace"}</p>
                        </div>
                      </div>
                      <span>{number(l.entry_count)}</span>
                      <span>{number(l.model_count)}</span>
                      <span>
                        <Private />
                        <ChevronRight size={17} />
                      </span>
                    </Link>
                  ))}
                </div>
              ) : (
                <Empty
                  title="Every language starts with its own space"
                  description="Create a language, add a dictionary you have permission to use, and review the extracted entries."
                >
                  {canEdit && (
                    <Link href="/languages/new" className="button secondary">
                      Create your first language
                      <ArrowRight size={16} />
                    </Link>
                  )}
                </Empty>
              )}
              <div className="principles">
                <div>
                  <LockKeyhole size={19} />
                  <h3>Private by default</h3>
                  <p>Dictionaries and trained models stay in your workspace.</p>
                </div>
                <div>
                  <Workflow size={19} />
                  <h3>Traceable at every step</h3>
                  <p>Every training sample leads back to its source entry.</p>
                </div>
                <div>
                  <CircleHelp size={19} />
                  <h3>Honest about what it learns</h3>
                  <p>
                    Dictionary knowledge supports search and matching. It does
                    not establish fluency.
                  </p>
                </div>
              </div>
            </>
          ) : !language ? (
            <Empty
              title="Language not found"
              description="This language is not available in your workspace."
            />
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">LANGUAGE WORKSPACE</div>
                  <h1>
                    {section === "overview"
                      ? language.name
                      : sections.find((s) => s.id === section)?.label ||
                        "Overview"}
                  </h1>
                  <p>
                    {
                      (
                        {
                          overview:
                            "Build on your dictionary, one verified step at a time.",
                          dictionary:
                            "Preserve the source. Review the details. Approve what can be learned.",
                          datasets:
                            "Frozen snapshots with every sample linked to its source.",
                          offline:
                            "Export a compact dictionary and use it on your phone without internet.",
                          training:
                            "Train locally. Compare honestly. Keep the full record.",
                          models:
                            "Evaluated models, their lineage and deployment status.",
                          playground:
                            "Explore dictionary knowledge and compare representations.",
                          settings:
                            "Language details, community context and workspace access.",
                        } as Record<string, string>
                      )[section]
                    }
                  </p>
                </div>
                <Private />
              </div>
              {section === "overview" ? (
                <Overview
                  language={language}
                  sources={sources}
                  datasets={datasets}
                  runs={runs}
                  models={models}
                />
              ) : section === "dictionary" ? (
                <DictionaryView
                  language={language}
                  sources={sources}
                  refresh={refresh}
                  canEdit={canEdit}
                />
              ) : section === "datasets" ? (
                <DatasetsView
                  language={language}
                  sources={sources}
                  datasets={datasets}
                  refresh={refresh}
                  canEdit={canEdit}
                />
              ) : section === "offline" ? (
                <OfflineView language={language} sources={sources} />
              ) : section === "training" ? (
                <TrainingView
                  language={language}
                  datasets={datasets}
                  runs={runs}
                  refresh={refresh}
                  canEdit={canEdit}
                />
              ) : section === "models" ? (
                <ModelsView
                  language={language}
                  models={models}
                  refresh={refresh}
                  owner={user.role === "owner"}
                />
              ) : section === "playground" ? (
                <PlaygroundView language={language} models={models} />
              ) : section === "settings" ? (
                <SettingsView
                  language={language}
                  refresh={refresh}
                  user={user}
                />
              ) : (
                <Empty
                  title="Page not found"
                  description="Choose a section from the language navigation."
                />
              )}
            </>
          )}
        </main>
        <footer>
          <span>Dictionary knowledge, with provenance.</span>
          <span>Private by default · Built for language stewardship</span>
        </footer>
      </div>
    </div>
  );
}
function Connect({ onConnect }: { onConnect: (user: User) => void }) {
  const [token, setToken] = useState("");
  return (
    <div className="connect-page">
      <div className="connect-aside">
        <span className="brand">
          <Workflow />
          LangAI
        </span>
        <div>
          <div className="eyebrow">A FOUNDATION FOR LANGUAGE</div>
          <h1>
            Knowledge begins
            <br />
            with a word.
          </h1>
          <p>
            Prepare your dictionary, train a representation, and keep every
            connection to its source.
          </p>
        </div>
        <span className="caption">
          Private infrastructure. Community permissions. Measured results.
        </span>
      </div>
      <div className="connect-form">
        <Private />
        <h2>Connect your workspace</h2>
        <p>Use an API key issued by your deployment owner.</p>
        <form onSubmit={(e) => e.preventDefault()}>
          <label className="field">
            <span>Workspace API key</span>
            <input
              type="password"
              autoComplete="off"
              placeholder="lai_…"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              required
            />
          </label>
          <Action
            disabled={!token}
            onClick={async () => {
              const res = await fetch("/api/session", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token }),
              });
              const data = await res.json();
              if (!res.ok) throw new Error(data.detail);
              setToken("");
              onConnect(data);
            }}
          >
            Connect workspace
            <ArrowRight size={16} />
          </Action>
        </form>
        <p className="caption">
          Your session lasts eight hours. Dictionary content is never sent to
          external AI services.
        </p>
      </div>
    </div>
  );
}
function Overview({
  language,
  sources,
  datasets,
  runs,
  models,
}: {
  language: Language;
  sources: Source[];
  datasets: Dataset[];
  runs: Run[];
  models: Model[];
}) {
  const steps = [
    {
      title: "Add your dictionary",
      text: sources.length
        ? `${sources.length} source file${sources.length === 1 ? "" : "s"} uploaded`
        : "CSV, TSV, XLSX, JSON or delimited TXT",
      done: sources.length > 0,
      to: "dictionary",
    },
    {
      title: "Review & create a dataset",
      text: datasets.length
        ? `${datasets.length} frozen dataset version${datasets.length === 1 ? "" : "s"}`
        : "Inspect normalization and approve eligible entries",
      done: datasets.length > 0,
      to: "datasets",
    },
    {
      title: "Train & evaluate",
      text: models.length
        ? `${models.length} evaluated model${models.length === 1 ? "" : "s"}`
        : runs.length
          ? "Training run in progress"
          : "A multilingual encoder with a measured baseline",
      done: models.length > 0,
      to: "training",
    },
    {
      title: "Deploy when you’re ready",
      text: models.some((m) => m.status === "DEPLOYED")
        ? "Your model is available through the API"
        : "Approve a model and expose its private API",
      done: models.some((m) => m.status === "DEPLOYED"),
      to: "models",
    },
  ];
  return (
    <>
      <div className="summary-line">
        <span>
          <strong>{number(language.entry_count)}</strong>dictionary entries
        </span>
        <span>
          <strong>{datasets.length}</strong>datasets
        </span>
        <span>
          <strong>{models.length}</strong>models
        </span>
        <span>
          <strong>
            {models.filter((m) => m.status === "DEPLOYED").length}
          </strong>
          deployed
        </span>
      </div>
      <div className="section-title">
        <h2>Your path to a model</h2>
        <Badge>Dictionary workflow</Badge>
      </div>
      <div className="workflow-list">
        {steps.map((step, i) => (
          <Link href={`/languages/${language.id}/${step.to}`} key={step.to}>
            <span className={`step-number ${step.done ? "done" : ""}`}>
              {step.done ? "✓" : String(i + 1).padStart(2, "0")}
            </span>
            <div>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </div>
            <ArrowRight size={18} />
          </Link>
        ))}
      </div>
      <div className="two-column context-section">
        <div>
          <h2>Language context</h2>
          <p>
            {language.description ||
              "Add a description and orthography notes in Settings to preserve important context alongside the data."}
          </p>
          <dl>
            <dt>Community / source</dt>
            <dd>{language.source_community || "Not specified"}</dd>
            <dt>Default dialect</dt>
            <dd>{language.default_dialect || "Not specified"}</dd>
            <dt>ISO code</dt>
            <dd>{language.iso_code || "Not specified"}</dd>
          </dl>
        </div>
        <div className="soft-panel">
          <Sparkles size={22} />
          <h3>A representation, not a fluent speaker</h3>
          <p>
            Dictionary data can support lexical retrieval, semantic matching and
            spelling relationships. Grammar, conversation and translation need
            additional language material.
          </p>
          <p className="caption">
            Your dictionary remains private. Training permission is checked
            before a dataset can be used.
          </p>
        </div>
      </div>
    </>
  );
}

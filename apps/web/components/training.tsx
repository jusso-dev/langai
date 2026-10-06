"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  Check,
  ChevronDown,
  Download,
  FlaskConical,
  Play,
  Plus,
  Rocket,
  Search,
} from "lucide-react";
import {
  api,
  Dataset,
  Language,
  Model,
  Run,
  RunEvent,
  Source,
  post,
  short,
  Match,
  Governance,
} from "@/lib/api";
import {
  Action,
  Badge,
  Empty,
  ErrorNotice,
  Field,
  MetricTable,
  Private,
  Status,
} from "./ui";
import { GovernanceFields } from "./dictionary";
export function DatasetsView({
  language,
  sources,
  datasets,
  refresh,
  canEdit,
}: {
  language: Language;
  sources: Source[];
  datasets: Dataset[];
  refresh: () => Promise<void>;
  canEdit: boolean;
}) {
  const [selected, setSelected] = useState<string[]>([]),
    [seed, setSeed] = useState(42),
    [corpus, setCorpus] = useState(""),
    [corpora, setCorpora] = useState<{ id: string; name: string }[]>([]),
    [samples, setSamples] = useState<unknown>(null),
    [showNegatives, setShowNegatives] = useState(false);
  useEffect(() => {
    api<{ id: string; name: string }[]>(
      `/languages/${language.id}/negative-corpora`,
    )
      .then(setCorpora)
      .catch(() => {});
  }, [language.id]);
  const approved = sources.filter((s) => s.status === "APPROVED");
  return (
    <>
      {canEdit && approved.length > 0 && (
        <div className="dataset-builder">
          <div>
            <h2>Create a dataset version</h2>
            <p className="muted">
              Choose the approved sources to include. Each version preserves its
              exact entries, permissions and split manifest.
            </p>
          </div>
          <div className="permissions">
            {approved.map((s) => (
              <label key={s.id}>
                <input
                  type="checkbox"
                  checked={selected.includes(s.id)}
                  onChange={(e) =>
                    setSelected(
                      e.target.checked
                        ? [...selected, s.id]
                        : selected.filter((id) => id !== s.id),
                    )
                  }
                />
                {s.filename}
                <Badge tone="success">Approved</Badge>
              </label>
            ))}
          </div>
          <details className="disclosure">
            <summary>
              Split settings & external negatives
              <ChevronDown size={15} />
            </summary>
            <div className="form-grid">
              <Field label="Deterministic seed">
                <input
                  type="number"
                  min={0}
                  max={2147483647}
                  value={seed}
                  onChange={(e) => setSeed(Number(e.target.value))}
                />
              </Field>
              <Field
                label="Approved negative corpus"
                hint="Required only for language identification."
              >
                <select
                  value={corpus}
                  onChange={(e) => setCorpus(e.target.value)}
                >
                  <option value="">None. Dictionary only.</option>
                  {corpora.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <button
              className="button secondary"
              onClick={() => setShowNegatives(!showNegatives)}
            >
              Add an approved negative corpus
            </button>
            {showNegatives && (
              <NegativesForm
                language={language}
                onCreated={async () => {
                  setCorpora(
                    await api(`/languages/${language.id}/negative-corpora`),
                  );
                  setShowNegatives(false);
                }}
              />
            )}
          </details>
          <Action
            disabled={!selected.length}
            onClick={async () => {
              await post(`/languages/${language.id}/datasets`, {
                source_ids: selected,
                seed,
                negative_corpus_id: corpus || null,
              });
              setSelected([]);
              await refresh();
            }}
          >
            Create dataset
            <ArrowRight size={16} />
          </Action>
        </div>
      )}
      {!datasets.length ? (
        <Empty
          title="A reproducible starting point"
          description="Approve dictionary entries first, then create a frozen dataset. Words, variants and shared definitions stay together across every generated view."
        >
          <Link
            className="button secondary"
            href={`/languages/${language.id}/dictionary`}
          >
            Review dictionary
            <ArrowRight size={16} />
          </Link>
        </Empty>
      ) : (
        datasets.map((d) => (
          <section className="dataset-row" key={d.id}>
            <div className="section-title">
              <div>
                <h2>Dictionary v{d.version}</h2>
                <span className="caption">
                  {d.entry_count.toLocaleString()} entries ·{" "}
                  {d.manifest.group_count} independent groups · Generation{" "}
                  {d.generation_version}
                </span>
              </div>
              <Badge tone="success">Ready to train</Badge>
            </div>
            <div className="split-bar" aria-label="Dataset split">
              {["train", "validation", "test"].map((s) => (
                <div
                  key={s}
                  className={s}
                  style={{ flex: d.manifest.counts[s] }}
                />
              ))}
            </div>
            <div className="split-labels">
              {["train", "validation", "test"].map((s) => (
                <span key={s}>
                  <i className={s} />
                  {s} <strong>{d.manifest.counts[s]}</strong>
                </span>
              ))}
            </div>
            <div className="dataset-footer">
              <span className="caption mono">
                Seed {d.seed} · SHA-256 {d.sha256.slice(0, 16)}…
              </span>
              <div className="button-row">
                <Action
                  secondary
                  onClick={async () =>
                    setSamples(await api(`/datasets/${d.id}/samples`))
                  }
                >
                  Inspect dataset views
                </Action>
                <a
                  className="button secondary"
                  href={`/api/proxy/datasets/${d.id}/export`}
                  download={`dictionary-v${d.version}.json`}
                >
                  <Download size={14} />
                  Export
                </a>
                <Link
                  className="button"
                  href={`/languages/${language.id}/training?dataset=${d.id}`}
                >
                  <Play size={14} />
                  Train model
                </Link>
              </div>
            </div>
          </section>
        ))
      )}
      {samples !== null && (
        <details className="disclosure" open>
          <summary>
            Sample provenance & split manifest
            <ChevronDown size={15} />
          </summary>
          <pre className="json-view">{JSON.stringify(samples, null, 2)}</pre>
        </details>
      )}
      <div className="notice">
        All augmentations are generated after grouping and splitting. Shared
        headwords, spelling variants and identical definitions cannot cross
        split boundaries.
      </div>
    </>
  );
}
function NegativesForm({
  language,
  onCreated,
}: {
  language: Language;
  onCreated: () => Promise<void>;
}) {
  const [name, setName] = useState(""),
    [texts, setTexts] = useState(""),
    [governance, setGovernance] = useState<Governance>({
      owner: "",
      custodian: "",
      source: "",
      licence: "",
      attribution: "",
      training_allowed: false,
      commercial_use_allowed: false,
      redistribution_allowed: false,
    });
  return (
    <div className="negative-form">
      <h3>Approve external negative examples</h3>
      <p className="muted">
        Use real examples from a source you have permission to use. No external
        corpus is downloaded automatically.
      </p>
      <Field label="Corpus name">
        <input value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <Field
        label="Examples, one per line"
        hint="At least 10 distinct examples. Overlapping dictionary words are removed."
      >
        <textarea
          rows={5}
          value={texts}
          onChange={(e) => setTexts(e.target.value)}
        />
      </Field>
      <GovernanceFields value={governance} onChange={setGovernance} />
      <Action
        disabled={!name || !governance.training_allowed}
        onClick={async () => {
          await post(`/languages/${language.id}/negative-corpora`, {
            name,
            texts: texts.split("\n").filter((t) => t.trim()),
            governance,
            approved: true,
          });
          await onCreated();
        }}
      >
        Approve negative corpus
        <Check size={15} />
      </Action>
    </div>
  );
}
export function TrainingView({
  language,
  datasets,
  runs,
  refresh,
  canEdit,
}: {
  language: Language;
  datasets: Dataset[];
  runs: Run[];
  refresh: () => Promise<void>;
  canEdit: boolean;
}) {
  const [dataset, setDataset] = useState(() =>
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("dataset") ||
          datasets[0]?.id ||
          ""
        : datasets[0]?.id || "",
    ),
    [task, setTask] = useState("embeddings"),
    [base, setBase] = useState("auto"),
    [revision, setRevision] = useState("auto"),
    [epochs, setEpochs] = useState(""),
    [batch, setBatch] = useState(""),
    [lr, setLr] = useState(""),
    [device, setDevice] = useState("auto"),
    [seed, setSeed] = useState(42),
    [patience, setPatience] = useState(2),
    [frequency, setFrequency] = useState(1),
    [maxLength, setMaxLength] = useState(128),
    [weightDecay, setWeightDecay] = useState(0.01),
    [margin, setMargin] = useState(0.4),
    [loraRank, setLoraRank] = useState(8),
    [active, setActive] = useState(runs[0]?.id || "");
  const [events, setEvents] = useState<RunEvent[]>([]),
    [streamError, setStreamError] = useState("");
  const run = runs.find((r) => r.id === active) || runs[0];
  useEffect(() => {
    if (!run) return;
    setEvents([]);
    setStreamError("");
    const stream = new EventSource(`/api/proxy/training-runs/${run.id}/stream`);
    stream.onmessage = (e) => {
      const row = JSON.parse(e.data) as RunEvent;
      setEvents((previous) =>
        previous.some((p) => p.id === row.id) ? previous : [...previous, row],
      );
    };
    stream.addEventListener("complete", () => {
      stream.close();
      refresh().catch(() => {});
    });
    stream.onerror = () => {
      setStreamError("Live connection interrupted. Reconnecting…");
    };
    stream.onopen = () => setStreamError("");
    return () => stream.close();
  }, [run?.id]);
  const latest = events.reduce(
    (data, event) => ({ ...data, ...event.data }),
    {} as Record<string, unknown>,
  );
  const complete =
    run && ["COMPLETED", "FAILED", "CANCELLED"].includes(run.status);
  return (
    <>
      {canEdit && datasets.length > 0 && (
        <div className="training-config">
          <div className="section-title">
            <h2>Train a model</h2>
            <Badge>Automatic defaults</Badge>
          </div>
          <div className="form-grid">
            <Field label="Dataset">
              <select
                value={dataset}
                onChange={(e) => setDataset(e.target.value)}
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    Dictionary v{d.version} · {d.entry_count} entries
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Task">
              <select value={task} onChange={(e) => setTask(e.target.value)}>
                <option value="embeddings">Semantic embeddings</option>
                <option value="language-identification">
                  Language identification
                </option>
                <option value="dictionary-adapter">
                  Dictionary adapter · EXPERIMENTAL
                </option>
              </select>
            </Field>
            <Field label="Base model">
              <input
                value={base}
                onChange={(e) => setBase(e.target.value)}
                placeholder="auto"
              />
            </Field>
            <Field label="Training strategy">
              <select disabled>
                <option>
                  Auto ·{" "}
                  {task === "embeddings"
                    ? "Contrastive learning"
                    : task === "language-identification"
                      ? "Character n-gram baselines"
                      : "LoRA adapter"}
                </option>
              </select>
            </Field>
          </div>
          {task === "dictionary-adapter" && (
            <div className="notice warning">
              EXPERIMENTAL. Dictionary recall does not establish conversational
              fluency. Requires deployment-owner opt-in.
            </div>
          )}
          {task === "language-identification" && (
            <div className="notice">
              This dataset must include an explicitly approved negative corpus.
              Logistic regression and SVM baselines will be evaluated.
            </div>
          )}
          <details className="disclosure">
            <summary>
              Advanced settings
              <ChevronDown size={15} />
            </summary>
            <div className="form-grid">
              <Field label="Epochs">
                <input
                  type="number"
                  min={1}
                  max={100}
                  placeholder="Auto"
                  value={epochs}
                  onChange={(e) => setEpochs(e.target.value)}
                />
              </Field>
              <Field label="Batch size">
                <input
                  type="number"
                  min={2}
                  max={512}
                  placeholder="Auto"
                  value={batch}
                  onChange={(e) => setBatch(e.target.value)}
                />
              </Field>
              <Field label="Learning rate">
                <input
                  type="number"
                  step="any"
                  placeholder="Auto"
                  value={lr}
                  onChange={(e) => setLr(e.target.value)}
                />
              </Field>
              <Field label="Device">
                <select
                  value={device}
                  onChange={(e) => setDevice(e.target.value)}
                >
                  <option value="auto">Auto (CPU)</option>
                  <option value="cpu">CPU</option>
                  <option value="cuda">CUDA GPU</option>
                  <option value="mps">Apple MPS</option>
                </select>
              </Field>
              <Field label="Base model revision">
                <input
                  value={revision}
                  onChange={(e) => setRevision(e.target.value)}
                  placeholder="auto resolves a pinned commit"
                />
              </Field>
              <Field label="Random seed">
                <input
                  type="number"
                  value={seed}
                  onChange={(e) => setSeed(Number(e.target.value))}
                />
              </Field>
              <Field label="Early stopping patience">
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={patience}
                  onChange={(e) => setPatience(Number(e.target.value))}
                />
              </Field>
              <Field label="Evaluate every N epochs">
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={frequency}
                  onChange={(e) => setFrequency(Number(e.target.value))}
                />
              </Field>
              <Field label="Maximum token length">
                <input
                  type="number"
                  min={8}
                  max={512}
                  value={maxLength}
                  onChange={(e) => setMaxLength(Number(e.target.value))}
                />
              </Field>
              <Field label="Weight decay">
                <input
                  type="number"
                  step="any"
                  value={weightDecay}
                  onChange={(e) => setWeightDecay(Number(e.target.value))}
                />
              </Field>
              <Field label="Contrastive margin">
                <input
                  type="number"
                  step="any"
                  value={margin}
                  onChange={(e) => setMargin(Number(e.target.value))}
                />
              </Field>
              <Field label="LoRA rank">
                <input
                  type="number"
                  min={2}
                  max={64}
                  value={loraRank}
                  onChange={(e) => setLoraRank(Number(e.target.value))}
                />
              </Field>
            </div>
          </details>
          <Action
            disabled={!dataset}
            onClick={async () => {
              const r = await post<Run>(
                `/languages/${language.id}/training-runs`,
                {
                  dataset_id: dataset,
                  task,
                  base_model: base || "auto",
                  base_model_revision: revision || "auto",
                  random_seed: seed,
                  hyperparameters: {
                    epochs: epochs ? Number(epochs) : null,
                    batch_size: batch ? Number(batch) : null,
                    learning_rate: lr ? Number(lr) : null,
                    device,
                    patience,
                    evaluation_frequency: frequency,
                    max_length: maxLength,
                    weight_decay: weightDecay,
                    margin,
                    lora_rank: loraRank,
                  },
                },
              );
              setActive(r.id);
              await refresh();
            }}
          >
            Start training
            <Play size={15} />
          </Action>
          <p className="caption">
            The baseline is evaluated first. Training never deploys a model
            automatically.
          </p>
        </div>
      )}
      {!datasets.length ? (
        <Empty
          title="A dataset comes first"
          description="Review and approve a dictionary, then create a dataset to enable training."
        >
          <Link
            className="button secondary"
            href={`/languages/${language.id}/datasets`}
          >
            Open datasets
            <ArrowRight size={16} />
          </Link>
        </Empty>
      ) : !run ? (
        <Empty
          title="Ready for your first experiment"
          description="Choose a task above. Auto uses conservative CPU defaults and records the resolved configuration."
        />
      ) : (
        <section className="run-panel">
          <div className="section-title">
            <div>
              <h2>Training {language.name}</h2>
              <span className="caption">
                {run.task.replaceAll("-", " ")} · Run {short(run.id)}
              </span>
            </div>
            <Status value={run.status} />
          </div>
          <label className="field">
            <span>Training run</span>
            <select value={run.id} onChange={(e) => setActive(e.target.value)}>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {new Date(r.created_at).toLocaleString()} · {r.task} ·{" "}
                  {r.status}
                </option>
              ))}
            </select>
          </label>
          <div className="run-model">
            <span className="caption">BASE MODEL</span>
            <strong>{run.base_model}</strong>
            <span className="caption mono">{run.base_model_revision}</span>
          </div>
          {typeof latest.progress === "number" && (
            <>
              <div
                className="progress"
                role="progressbar"
                aria-label="Training progress"
                aria-valuenow={Math.round(latest.progress * 100)}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  style={{ width: `${Math.min(100, latest.progress * 100)}%` }}
                />
              </div>
              <p className="caption">
                {Math.round(latest.progress * 100)}% of scheduled training steps
              </p>
            </>
          )}
          <div className="run-stats">
            {[
              ["Epoch", latest.epoch],
              ["Train loss", latest.train_loss],
              ["Validation loss", latest.validation_loss],
              ["Validation Recall@1", latest.validation_recall_at_1],
              ["Validation Recall@5", latest.validation_recall_at_5],
            ].map(([label, value]) => (
              <div key={String(label)}>
                <span>{String(label)}</span>
                <strong>
                  {typeof value === "number"
                    ? label === "Epoch"
                      ? value
                      : value.toFixed(4)
                    : "—"}
                </strong>
              </div>
            ))}
          </div>
          <ErrorNotice error={run.error || streamError} />
          {canEdit && !complete && (
            <Action
              secondary
              disabled={run.cancel_requested}
              onClick={async () => {
                await post(`/training-runs/${run.id}/cancel`);
                await refresh();
              }}
            >
              {run.cancel_requested
                ? "Cancellation requested"
                : "Cancel training"}
            </Action>
          )}
          <div className="log-heading">
            <h3>Live run log</h3>
            <span className="caption">Worker events only</span>
          </div>
          <div className="run-logs" role="log" aria-live="polite">
            {events.length ? (
              events.map((event) => (
                <div key={event.id}>
                  <time>{new Date(event.created_at).toLocaleTimeString()}</time>
                  <span>{event.message}</span>
                </div>
              ))
            ) : (
              <p>Waiting for worker events…</p>
            )}
          </div>
          {run.status === "COMPLETED" && (
            <>
              <h3 className="evaluation-title">Evaluation results</h3>
              <MetricTable metrics={run.metrics} />
              <Link
                href={`/languages/${language.id}/models`}
                className="button"
              >
                Review registered model
                <ArrowRight size={16} />
              </Link>
            </>
          )}
          <details className="disclosure">
            <summary>
              Recorded training configuration
              <ChevronDown size={15} />
            </summary>
            <pre>{JSON.stringify(run.hyperparameters, null, 2)}</pre>
          </details>
        </section>
      )}
    </>
  );
}
export function ModelsView({
  language,
  models,
  refresh,
  owner,
}: {
  language: Language;
  models: Model[];
  refresh: () => Promise<void>;
  owner: boolean;
}) {
  const [lineage, setLineage] = useState<unknown>(null);
  return (
    <>
      {!models.length ? (
        <Empty
          title="Models with a record of how they learned"
          description="Completed training runs appear here with their dataset, evaluation and artifact lineage."
        >
          <Link
            className="button secondary"
            href={`/languages/${language.id}/training`}
          >
            Train your first model
            <ArrowRight size={16} />
          </Link>
        </Empty>
      ) : (
        models.map((model) => (
          <section className="model-section" key={model.id}>
            <div className="section-title">
              <div>
                <h2>
                  {language.name}{" "}
                  {model.task === "embeddings"
                    ? "Semantic Model"
                    : model.task === "language-identification"
                      ? "Language Classifier"
                      : "Dictionary Adapter"}{" "}
                  v{model.version}
                </h2>
                <p className="caption">
                  {model.base_model} ·{" "}
                  {new Date(model.created_at).toLocaleDateString()}
                </p>
              </div>
              <div className="button-row">
                <Private />
                <Status value={model.status} />
              </div>
            </div>
            {model.experimental && (
              <div className="notice warning">
                EXPERIMENTAL · Dictionary recall only. This model is not
                validated for fluent language use.
              </div>
            )}
            <MetricTable metrics={model.metrics} />
            <div className="model-actions">
              <div className="button-row">
                <Action
                  secondary
                  onClick={async () =>
                    setLineage(await api(`/models/${model.id}/lineage`))
                  }
                >
                  View lineage
                </Action>
                <a
                  className="button secondary"
                  href={`/api/proxy/models/${model.id}/artifact`}
                  download={`model-${model.id}.zip`}
                >
                  <Download size={14} />
                  Artifact
                </a>
                <Link
                  className="button secondary"
                  href={`/languages/${language.id}/playground?model=${model.id}`}
                >
                  <FlaskConical size={15} />
                  Playground
                </Link>
              </div>
              <div className="button-row">
                {owner && model.status === "EVALUATED" && (
                  <Action
                    onClick={async () => {
                      await post(`/models/${model.id}/approve`);
                      await refresh();
                    }}
                  >
                    <Check size={15} />
                    Approve model
                  </Action>
                )}
                {owner &&
                  model.status === "APPROVED" &&
                  !model.experimental && (
                    <Action
                      onClick={async () => {
                        await post(`/models/${model.id}/deploy`);
                        await refresh();
                      }}
                    >
                      <Rocket size={15} />
                      Deploy
                    </Action>
                  )}
                {owner && ["EVALUATED", "APPROVED"].includes(model.status) && (
                  <Action
                    secondary
                    onClick={async () => {
                      await post(`/models/${model.id}/archive`);
                      await refresh();
                    }}
                  >
                    Archive
                  </Action>
                )}
              </div>
            </div>
            {model.status === "DEPLOYED" && (
              <div className="deployment-note">
                <span className="status-dot" />
                <span>Available through the private inference API</span>
                <code>
                  {model.task === "embeddings"
                    ? "POST /v1/search"
                    : "POST /v1/classify-language"}
                </code>
              </div>
            )}
          </section>
        ))
      )}
      {lineage !== null && (
        <details className="disclosure" open>
          <summary>
            Complete model lineage
            <ChevronDown size={15} />
          </summary>
          <div className="lineage-flow">
            Base model → Dictionary → Dataset generation → Training run →
            Artifact → Evaluation → Deployment
          </div>
          <pre className="json-view">{JSON.stringify(lineage, null, 2)}</pre>
        </details>
      )}
    </>
  );
}
export function PlaygroundView({
  language,
  models,
}: {
  language: Language;
  models: Model[];
}) {
  const available = models.filter(
    (m) => m.task !== "dictionary-adapter" && m.status !== "ARCHIVED",
  );
  const [selected, setSelected] = useState(() =>
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("model") ||
          available[0]?.id ||
          ""
        : available[0]?.id || "",
    ),
    [mode, setMode] = useState("meaning-to-word"),
    [query, setQuery] = useState(""),
    [result, setResult] = useState<{
      baseline?: Match[];
      fine_tuned?: Match[];
      classification?: {
        is_language: boolean;
        confidence: number;
        positive_probability: number;
      };
    } | null>(null),
    [lastQuery, setLastQuery] = useState("");
  const model = available.find((m) => m.id === selected) || available[0];
  if (!model)
    return (
      <Empty
        title="Try what your model has learned"
        description="Train an encoder or classifier to compare real model outputs here. Deployment is not required for private testing."
      />
    );
  return (
    <>
      <div className="playground-controls">
        <div className="form-grid">
          <Field label="Model">
            <select
              value={model.id}
              onChange={(e) => {
                setSelected(e.target.value);
                setResult(null);
              }}
            >
              {available.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.task} v{m.version} · {m.status}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Mode">
            <select
              disabled={model.task !== "embeddings"}
              value={model.task !== "embeddings" ? "detection" : mode}
              onChange={(e) => {
                setMode(e.target.value);
                setResult(null);
              }}
            >
              <option value="word-to-meaning">Word → Meaning</option>
              <option value="meaning-to-word">Meaning → Word</option>
              <option value="semantic">Semantic search</option>
              <option value="similar-words">Similar words</option>
              {model.task !== "embeddings" && (
                <option value="detection">Language detection</option>
              )}
            </select>
          </Field>
        </div>
        <div className="query-bar">
          <Search size={20} />
          <label className="sr-only" htmlFor="query">
            Search your dictionary
          </label>
          <input
            id="query"
            value={query}
            maxLength={4000}
            placeholder="Enter a word or meaning…"
            onChange={(e) => setQuery(e.target.value)}
          />
          <Action
            disabled={!query.trim()}
            onClick={async () => {
              const value = await post<typeof result>(
                `/models/${model.id}/playground`,
                { language: language.id, query, mode, limit: 10 },
              );
              setResult(value);
              setLastQuery(query);
            }}
          >
            Run query
            <ArrowRight size={16} />
          </Action>
        </div>
        <p className="caption">
          Embeddings compare by cosine similarity. Scores are not probabilities
          or evidence of fluency.
        </p>
      </div>
      {result ? (
        <>
          <div className="section-title">
            <h2>Results for “{lastQuery}”</h2>
            <Badge>Local inference</Badge>
          </div>
          {result.classification ? (
            <div className="classification">
              <h2>
                {result.classification.is_language ? language.name : "Other"}
              </h2>
              <p>Confidence {result.classification.confidence.toFixed(3)}</p>
              <p className="caption">
                Relative to the approved negative corpus. Not proof of language
                membership.
              </p>
            </div>
          ) : (
            <div className="comparison">
              {(
                [
                  ["baseline", "Original model"],
                  ["fine_tuned", "Fine-tuned model"],
                ] as const
              ).map(([key, label]) => (
                <section key={key}>
                  <div className="comparison-heading">
                    <h3>{label}</h3>
                    <Badge>{key === "baseline" ? "Baseline" : "Trained"}</Badge>
                  </div>
                  {result[key]?.map((match, i) => (
                    <div key={match.entry_id} className="match-row">
                      <span className="match-rank">{i + 1}</span>
                      <div>
                        <strong>{match.headword}</strong>
                        <p>{match.definitions.join("; ")}</p>
                      </div>
                      <span className="score mono">
                        {match.score.toFixed(3)}
                      </span>
                    </div>
                  ))}
                </section>
              ))}
            </div>
          )}
        </>
      ) : (
        <div className="playground-empty">
          <FlaskConical size={34} />
          <h2>A place to ask small, useful questions</h2>
          <p>
            Retrieve a word by its meaning, explore related entries, or compare
            the original encoder with your trained model.
          </p>
        </div>
      )}
      <details className="disclosure">
        <summary>
          Use the deployed API
          <ChevronDown size={15} />
        </summary>
        <p className="caption">
          Approve and deploy a model first. Use a viewer API key from Settings.
        </p>
        <pre>{`curl -X POST http://localhost:8100/v1/search \\\n  -H "Authorization: Bearer $LANGAI_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '${JSON.stringify({ language: language.id, query: query || "water" })}'`}</pre>
      </details>
    </>
  );
}

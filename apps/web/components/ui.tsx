"use client";
import { useState } from "react";
import {
  AlertCircle,
  ArrowUpRight,
  LockKeyhole,
  LoaderCircle,
} from "lucide-react";
export function Badge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function Private() {
  return (
    <Badge>
      <LockKeyhole size={11} />
      Private
    </Badge>
  );
}
export function Status({ value }: { value: string }) {
  return (
    <Badge
      tone={
        ["APPROVED", "DEPLOYED", "COMPLETED"].includes(value)
          ? "success"
          : ["FAILED", "CANCELLED"].includes(value)
            ? "warning"
            : "neutral"
      }
    >
      {value.toLowerCase().replaceAll("_", " ")}
    </Badge>
  );
}
export function ErrorNotice({ error }: { error: string }) {
  return error ? (
    <div className="notice error" role="alert">
      <AlertCircle size={17} />
      <span>{error}</span>
    </div>
  ) : null;
}
export function Action({
  children,
  onClick,
  secondary = false,
  disabled = false,
  className = "",
}: {
  children: React.ReactNode;
  onClick: () => Promise<unknown>;
  secondary?: boolean;
  disabled?: boolean;
  className?: string;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <>
      <button
        className={`${secondary ? "button secondary" : "button"} ${className}`}
        disabled={disabled || busy}
        onClick={async () => {
          setBusy(true);
          setError("");
          try {
            await onClick();
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy && <LoaderCircle className="spin" size={15} />} {children}
      </button>
      <ErrorNotice error={error} />
    </>
  );
}
export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function Empty({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-mark">
        <ArrowUpRight size={25} />
      </div>
      <h2>{title}</h2>
      <p>{description}</p>
      {children}
    </div>
  );
}
export function Loading() {
  return (
    <div
      className="skeleton-group"
      aria-label="Loading workspace"
      aria-busy="true"
    >
      <div />
      <div />
      <div />
    </div>
  );
}
export function MetricTable({
  metrics,
}: {
  metrics: import("@/lib/api").Metrics;
}) {
  const labels: Record<string, string> = {
    recall_at_1: "Recall@1",
    recall_at_5: "Recall@5",
    recall_at_10: "Recall@10",
    mrr: "MRR",
    test_loss: "Test loss",
    perplexity: "Perplexity",
  };
  if (metrics.baselines)
    return (
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Classifier baseline</th>
              <th>Accuracy</th>
              <th>Macro F1</th>
              <th>ROC AUC</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(metrics.baselines).map(([key, m]) => (
              <tr key={key}>
                <td>{key.replaceAll("_", " ")}</td>
                <td>{m.accuracy.toFixed(3)}</td>
                <td>{m.macro_f1.toFixed(3)}</td>
                <td>{m.roc_auc.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  if (!metrics.baseline || !metrics.fine_tuned)
    return (
      <p className="muted">
        Evaluation results will appear after the run completes.
      </p>
    );
  return (
    <>
      {metrics.test_only_encoder && (
        <div className="notice warning">
          Test encoder results. These do not measure a pretrained multilingual
          model.
        </div>
      )}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Held-out test metric</th>
              <th>Base model</th>
              <th>Fine-tuned</th>
              <th>Change</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(labels)
              .filter(([key]) => typeof metrics.baseline?.[key] === "number")
              .map(([key, label]) => {
                const a = metrics.baseline![key] as number,
                  b = metrics.fine_tuned![key] as number,
                  d = b - a;
                return (
                  <tr key={key}>
                    <td>{label}</td>
                    <td className="mono">{a.toFixed(3)}</td>
                    <td className="mono strong">{b.toFixed(3)}</td>
                    <td className="mono">
                      {d > 0 ? "+" : ""}
                      {d.toFixed(3)}
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
      <p className="caption">
        {metrics.experimental
          ? "Held-out response loss and perplexity. This experiment does not measure fluency."
          : `${String(metrics.fine_tuned.query_count || "")} held-out queries · ${String(metrics.fine_tuned.candidate_count || "")} candidate definitions. Small test sets have high uncertainty.`}
      </p>
    </>
  );
}

"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  Check,
  ChevronDown,
  FileText,
  Plus,
  UploadCloud,
} from "lucide-react";
import {
  api,
  Entry,
  Governance,
  Language,
  number,
  post,
  Quality,
  Source,
} from "@/lib/api";
import {
  Action,
  Badge,
  Empty,
  ErrorNotice,
  Field,
  Private,
  Status,
} from "./ui";
const initialGovernance: Governance = {
  owner: "",
  custodian: "",
  source: "",
  licence: "",
  attribution: "",
  training_allowed: false,
  commercial_use_allowed: false,
  redistribution_allowed: false,
};
function includedOnApproval(entry: Entry) {
  return (
    entry.approved ||
    (!entry.issues.length &&
      !(entry.metadata || entry.entry_metadata)?.explicit_review)
  );
}
export function GovernanceFields({
  value,
  onChange,
}: {
  value: Governance;
  onChange: (g: Governance) => void;
}) {
  return (
    <>
      <div className="form-grid">
        {(
          [
            ["owner", "Owner"],
            ["custodian", "Custodian"],
            ["source", "Source / reference"],
            ["licence", "Licence / permission terms"],
          ] as const
        ).map(([key, label]) => (
          <Field label={label} key={key}>
            <input
              required={key !== "custodian"}
              value={value[key]}
              onChange={(e) => onChange({ ...value, [key]: e.target.value })}
            />
          </Field>
        ))}
      </div>
      <Field label="Required attribution">
        <textarea
          rows={2}
          value={value.attribution}
          onChange={(e) => onChange({ ...value, attribution: e.target.value })}
        />
      </Field>
      <div className="permissions">
        <label>
          <input
            type="checkbox"
            checked={value.training_allowed}
            onChange={(e) =>
              onChange({ ...value, training_allowed: e.target.checked })
            }
          />
          <span>
            I have permission to use this dictionary for model training.
          </span>
        </label>
        <label>
          <input
            type="checkbox"
            checked={value.commercial_use_allowed}
            onChange={(e) =>
              onChange({ ...value, commercial_use_allowed: e.target.checked })
            }
          />
          <span>The permission also allows commercial use.</span>
        </label>
        <label>
          <input
            type="checkbox"
            checked={value.redistribution_allowed}
            onChange={(e) =>
              onChange({ ...value, redistribution_allowed: e.target.checked })
            }
          />
          <span>The permission also allows redistribution.</span>
        </label>
      </div>
      <p className="caption">
        Recording these permissions does not publish the dictionary or model.
      </p>
    </>
  );
}
export function DictionaryView({
  language,
  sources,
  refresh,
  canEdit,
}: {
  language: Language;
  sources: Source[];
  refresh: () => Promise<void>;
  canEdit: boolean;
}) {
  const [uploading, setUploading] = useState(false),
    [file, setFile] = useState<File | null>(null),
    [governance, setGovernance] = useState<Governance>(initialGovernance),
    [selected, setSelected] = useState<string | null>(null),
    [uploaded, setUploaded] = useState<Source | null>(null);
  const source =
    sources.find((s) => s.id === selected) || uploaded || sources[0];
  return (
    <>
      <div className="toolbar">
        <span className="muted">
          {sources.length} source file{sources.length === 1 ? "" : "s"} ·
          Originals preserved
        </span>
        {canEdit && (
          <button className="button" onClick={() => setUploading(!uploading)}>
            <Plus size={16} />
            {uploading ? "Close upload" : "Upload dictionary"}
          </button>
        )}
      </div>
      {uploading && (
        <div className="upload-section">
          <h2>Upload a dictionary</h2>
          <p className="muted">
            Choose a file and record who has authority over its use.
          </p>
          <label className="dropzone">
            <UploadCloud size={30} />
            <strong>{file ? file.name : "Choose a dictionary file"}</strong>
            <span>CSV, TSV, XLSX, JSON or delimited TXT · up to 25 MB</span>
            <input
              type="file"
              accept=".csv,.tsv,.xlsx,.json,.txt"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </label>
          <GovernanceFields value={governance} onChange={setGovernance} />
          <Action
            disabled={
              !file ||
              !governance.owner ||
              !governance.source ||
              !governance.licence
            }
            onClick={async () => {
              const data = new FormData();
              data.set("file", file!);
              data.set("governance", JSON.stringify(governance));
              const s = await api<Source>(
                `/languages/${language.id}/dictionaries`,
                { method: "POST", body: data },
              );
              setUploaded(s);
              setSelected(s.id);
              await refresh();
              setUploading(false);
              setFile(null);
            }}
          >
            Upload & map columns
            <ArrowRight size={16} />
          </Action>
        </div>
      )}
      {!source && !uploading ? (
        <Empty
          title="Bring your dictionary into the workspace"
          description="Start with a file you have permission to use. We’ll suggest column mappings and show proposed normalization before importing."
        >
          {canEdit && (
            <button
              className="button secondary"
              onClick={() => setUploading(true)}
            >
              <UploadCloud size={16} />
              Choose a dictionary
            </button>
          )}
        </Empty>
      ) : (
        source && (
          <>
            <div className="source-picker">
              <FileText size={18} />
              <label className="sr-only" htmlFor="source">
                Dictionary source
              </label>
              <select
                id="source"
                value={source.id}
                onChange={(e) => {
                  setSelected(e.target.value);
                  setUploaded(null);
                }}
              >
                {sources.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.filename}
                  </option>
                ))}
              </select>
              <Status value={source.status} />
              <Private />
            </div>
            {source.status === "UPLOADED" ? (
              <Mapping
                key={source.id}
                source={source}
                refresh={refresh}
                canEdit={canEdit}
              />
            ) : (
              <Review
                key={source.id}
                source={source}
                refresh={refresh}
                language={language}
                canEdit={canEdit}
              />
            )}
          </>
        )
      )}
    </>
  );
}
function QualityReport({ quality }: { quality: Quality }) {
  return (
    <>
      <div className="quality-summary">
        <div>
          <span className="quality-score">
            {quality.score}
            <small>/ 100</small>
          </span>
          <span>Import quality</span>
        </div>
        <dl>
          <div>
            <dt>Entries</dt>
            <dd>{number(quality.entries)}</dd>
          </div>
          <div>
            <dt>Unique headwords</dt>
            <dd>{number(quality.unique_headwords)}</dd>
          </div>
          <div>
            <dt>Alternate definitions</dt>
            <dd>{number(quality.alternate_definitions)}</dd>
          </div>
          <div>
            <dt>Need review</dt>
            <dd>{number(quality.needs_review)}</dd>
          </div>
        </dl>
      </div>
      <p className="caption">
        {quality.score_method} {quality.transformations} rows have proposed
        normalization.
      </p>
    </>
  );
}
function Mapping({
  source,
  refresh,
  canEdit,
}: {
  source: Source;
  refresh: () => Promise<void>;
  canEdit: boolean;
}) {
  const [mapping, setMapping] = useState(source.mapping),
    [normalization, setNormalization] = useState({
      unicode_nfc: true,
      trim_whitespace: true,
      collapse_whitespace: true,
    }),
    [preview, setPreview] = useState<{
      quality: Quality;
      entries: Entry[];
    } | null>(null);
  const fields = [
    ["headword", "Indigenous word *"],
    ["definitions", "English meaning *"],
    ["part_of_speech", "Part of speech"],
    ["examples", "Example"],
    ["dialect", "Dialect"],
    ["alternate_spellings", "Spelling variants"],
    ["notes", "Notes"],
    ["source", "Source"],
  ];
  return (
    <div className="mapping-section">
      <div className="section-title">
        <h2>Connect your columns</h2>
        <Badge>Step 1 of 2</Badge>
      </div>
      <p className="muted">
        These mappings are suggestions. Only a headword and meaning are
        required.
      </p>
      <div className="mapping-grid">
        {fields.map(([key, label]) => (
          <Field label={label} key={key}>
            <select
              disabled={!canEdit}
              value={mapping[key] || ""}
              onChange={(e) => {
                const next = { ...mapping };
                if (e.target.value) next[key] = e.target.value;
                else delete next[key];
                setMapping(next);
                setPreview(null);
              }}
            >
              <option value="">Not mapped</option>
              {source.columns.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </Field>
        ))}
      </div>
      <details className="disclosure">
        <summary>
          Normalization settings
          <ChevronDown size={15} />
        </summary>
        <div className="permissions">
          {Object.entries(normalization).map(([key, value]) => (
            <label key={key}>
              <input
                type="checkbox"
                disabled={!canEdit}
                checked={value}
                onChange={(e) => {
                  setNormalization({
                    ...normalization,
                    [key]: e.target.checked,
                  });
                  setPreview(null);
                }}
              />
              {
                (
                  {
                    unicode_nfc: "Normalize Unicode to NFC",
                    trim_whitespace: "Trim surrounding whitespace",
                    collapse_whitespace: "Collapse accidental whitespace",
                  } as Record<string, string>
                )[key]
              }
            </label>
          ))}
        </div>
        <p className="caption">
          Case, diacritics, apostrophes and the original source are preserved.
          No English spellchecking.
        </p>
      </details>
      {canEdit && (
        <Action
          secondary
          disabled={!mapping.headword || !mapping.definitions}
          onClick={async () =>
            setPreview(
              await post(`/dictionaries/${source.id}/preview`, {
                mapping,
                normalization,
              }),
            )
          }
        >
          Preview extraction
        </Action>
      )}
      {preview && (
        <>
          <QualityReport quality={preview.quality} />
          <EntryTable entries={preview.entries.slice(0, 12)} preview />
          <p className="caption">
            Preview shows up to 12 rows. Review all rows after import.
          </p>
          {canEdit && (
            <Action
              onClick={async () => {
                await post(`/dictionaries/${source.id}/import`, {
                  mapping,
                  normalization,
                });
                await refresh();
              }}
            >
              Accept mappings & import
              <ArrowRight size={16} />
            </Action>
          )}
        </>
      )}
    </div>
  );
}
function Review({
  source,
  refresh,
  language,
  canEdit,
}: {
  source: Source;
  refresh: () => Promise<void>;
  language: Language;
  canEdit: boolean;
}) {
  const [rows, setRows] = useState<Entry[]>([]),
    [total, setTotal] = useState(0),
    [offset, setOffset] = useState(0),
    [issue, setIssue] = useState(""),
    [error, setError] = useState(""),
    [q, setQ] = useState("");
  const load = async () => {
    const data = await api<{ items: Entry[]; total: number }>(
      `/dictionaries/${source.id}/entries?offset=${offset}&limit=25&issue=${encodeURIComponent(issue)}&q=${encodeURIComponent(q)}`,
    );
    setRows(data.items);
    setTotal(data.total);
  };
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [source.id, source.status, offset, issue, q]);
  return (
    <>
      <QualityReport quality={source.quality} />
      <div className="review-actions">
        <div>
          {source.status === "APPROVED" ? (
            <>
              <Badge tone="success">
                <Check size={13} />
                Dataset approval recorded
              </Badge>
              <p className="caption">
                Approved sources are frozen. Upload a new version for changes.
              </p>
            </>
          ) : (
            <>
              <h3>Review the extracted entries</h3>
              <p className="caption">
                Clean entries will be approved together. Flagged rows stay
                excluded unless you explicitly include them.
              </p>
            </>
          )}
        </div>
        {canEdit &&
          (source.status === "APPROVED" ? (
            <Link
              className="button"
              href={`/languages/${language.id}/datasets`}
            >
              Create dataset
              <ArrowRight size={16} />
            </Link>
          ) : (
            <Action
              disabled={!source.governance.training_allowed}
              onClick={async () => {
                await post(`/dictionaries/${source.id}/approve`);
                await refresh();
              }}
            >
              Approve eligible entries
              <Check size={16} />
            </Action>
          ))}
      </div>
      {!source.governance.training_allowed && (
        <div className="notice warning">
          Training permission has not been granted for this source. It can be
          reviewed but cannot become a training dataset.
        </div>
      )}
      <div className="table-toolbar">
        <input
          aria-label="Search headwords"
          placeholder="Find a headword…"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOffset(0);
          }}
        />
        <select
          aria-label="Filter issues"
          value={issue}
          onChange={(e) => {
            setIssue(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All entries</option>
          {Object.entries(source.quality.issues).map(([k, v]) => (
            <option key={k} value={k}>
              {k.replaceAll("_", " ")} ({v})
            </option>
          ))}
        </select>
      </div>
      <ErrorNotice error={error} />
      <EntryTable
        entries={rows}
        review={
          canEdit && source.status !== "APPROVED"
            ? async (entry) => {
                await api(`/entries/${entry.id}`, {
                  method: "PATCH",
                  body: JSON.stringify({
                    approved: !includedOnApproval(entry),
                    training_eligible: !includedOnApproval(entry),
                  }),
                });
                await load();
              }
            : undefined
        }
      />
      <div className="pagination">
        <span>
          {total ? offset + 1 : 0}–{Math.min(offset + 25, total)} of{" "}
          {number(total)} entries
        </span>
        <button
          className="button secondary"
          disabled={!offset}
          onClick={() => setOffset(offset - 25)}
        >
          Previous
        </button>
        <button
          className="button secondary"
          disabled={offset + 25 >= total}
          onClick={() => setOffset(offset + 25)}
        >
          Next
        </button>
      </div>
      <details className="disclosure">
        <summary>
          Source provenance
          <ChevronDown size={15} />
        </summary>
        <dl>
          <dt>Owner</dt>
          <dd>{source.governance.owner}</dd>
          <dt>Custodian</dt>
          <dd>{source.governance.custodian || "Not specified"}</dd>
          <dt>Licence</dt>
          <dd>{source.governance.licence}</dd>
          <dt>Attribution</dt>
          <dd>{source.governance.attribution || "Not specified"}</dd>
          <dt>File SHA-256</dt>
          <dd className="mono break-all">{source.sha256}</dd>
        </dl>
        <a
          href={`/api/proxy/dictionaries/${source.id}/original`}
          download={source.filename}
          className="button secondary"
        >
          Download original file
        </a>
      </details>
    </>
  );
}
function EntryTable({
  entries,
  review,
  preview = false,
}: {
  entries: Entry[];
  review?: (entry: Entry) => Promise<void>;
  preview?: boolean;
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Headword</th>
            <th>Definition</th>
            <th>{preview ? "Proposed form" : "Review"}</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id}>
              <td className="word-cell">
                {e.headword || <em>Empty</em>}
                {e.alternate_spellings.length > 0 && (
                  <small>Variants: {e.alternate_spellings.join(", ")}</small>
                )}
              </td>
              <td>{e.definitions.join("; ") || <em>No definition</em>}</td>
              <td>
                {preview ? (
                  <>
                    <span>{e.normalized_headword}</span>
                    {e.headword !== e.normalized_headword && (
                      <Badge tone="warning">Changed</Badge>
                    )}
                  </>
                ) : (
                  <>
                    {e.issues.map((issue) => (
                      <Badge key={issue} tone="warning">
                        {issue.replaceAll("_", " ")}
                      </Badge>
                    ))}
                    {e.approved && <Badge tone="success">Included</Badge>}
                    {!e.issues.length && !e.approved && (
                      <Badge>
                        {includedOnApproval(e) ? "Ready" : "Excluded"}
                      </Badge>
                    )}
                    {review && (
                      <Action
                        secondary
                        disabled={
                          !e.normalized_headword || !e.definitions.length
                        }
                        onClick={() => review(e)}
                      >
                        {includedOnApproval(e) ? "Exclude" : "Include row"}
                      </Action>
                    )}
                  </>
                )}
              </td>
              <td>
                <details>
                  <summary>Original row</summary>
                  <pre>{JSON.stringify(e.original_row, null, 2)}</pre>
                  {(e.metadata || e.entry_metadata)?.transformations?.length ? (
                    <pre>
                      {JSON.stringify(
                        (e.metadata || e.entry_metadata)?.transformations,
                        null,
                        2,
                      )}
                    </pre>
                  ) : null}
                </details>
              </td>
            </tr>
          ))}
          {!entries.length && (
            <tr>
              <td colSpan={4} className="muted">
                No entries match this filter.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

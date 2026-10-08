"use client";
import { useState } from "react";
import { Download, Smartphone } from "lucide-react";
import type { Language, Source } from "@/lib/api";
import { Action, Badge, Empty } from "./ui";

export function OfflineView({
  language,
  sources,
}: {
  language: Language;
  sources: Source[];
}) {
  const approved = sources.filter((source) => source.status === "APPROVED");
  const [selected, setSelected] = useState<string[]>([]);
  const [exported, setExported] = useState("");
  return (
    <>
      <div className="intro-banner">
        <Smartphone size={30} />
        <div>
          <h2>A small dictionary model for your phone</h2>
          <p>
            Map words, alternate spellings and phrases to approved entries.
            Search runs on your phone, including in airplane mode.
          </p>
        </div>
        <Badge>No training needed</Badge>
      </div>
      {approved.length ? (
        <section className="dataset-builder">
          <h2>1. Export your dictionary pack</h2>
          <p className="muted">
            Choose approved sources from {language.name}. Only approved,
            eligible entries are included, with their original meanings and
            permissions.
          </p>
          <div className="permissions">
            {approved.map((source) => (
              <label key={source.id}>
                <input
                  type="checkbox"
                  checked={selected.includes(source.id)}
                  onChange={(event) => {
                    setSelected(
                      event.target.checked
                        ? [...selected, source.id]
                        : selected.filter((id) => id !== source.id),
                    );
                    setExported("");
                  }}
                />
                {source.filename}
              </label>
            ))}
          </div>
          <p className="caption">
            This creates a private copy for your device. Source permissions
            still apply. Signing out of the workspace does not delete a pack
            already saved on a phone.
          </p>
          <Action
            disabled={!selected.length}
            onClick={async () => {
              setExported("");
              const response = await fetch(
                `/api/proxy/languages/${language.id}/offline-export`,
                {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ source_ids: selected }),
                },
              );
              if (!response.ok) {
                const data = await response.json();
                throw new Error(
                  typeof data.detail === "string"
                    ? data.detail
                    : "Dictionary export failed.",
                );
              }
              const blob = await response.blob();
              const url = URL.createObjectURL(blob);
              const link = document.createElement("a");
              link.href = url;
              link.download = `dictionary-${language.id}.langai.json`;
              document.body.append(link);
              link.click();
              link.remove();
              setTimeout(() => URL.revokeObjectURL(url), 60_000);
              setExported(
                `Pack prepared (${(blob.size / 1024).toFixed(1)} KB). Save the download to Files, then import it in the offline app.`,
              );
            }}
          >
            <Download size={16} />
            Export phone dictionary
          </Action>
          {exported && <p role="status">{exported}</p>}
        </section>
      ) : (
        <Empty
          title="Approve a dictionary first"
          description="Review and approve your source entries in Dictionary, then return here. You can export even a single entry; no training split is required."
        />
      )}
      <section className="dataset-row">
        <h2>2. Install and import on iPhone</h2>
        <p>
          Open the offline app in Safari over HTTPS. Tap Share → Add to Home
          Screen. Open it from the Home Screen while online, import your pack
          from Files, and wait for “Ready for offline use”.
        </p>
        <a
          className="button"
          href="/offline/index.html"
          target="_blank"
          rel="noreferrer"
        >
          <Smartphone size={16} />
          Open offline dictionary
        </a>
        <p className="caption">
          Keep the export as a backup. Phone storage can be cleared by the
          browser or device. Use “Remove from phone” in the offline app to
          delete its saved dictionary.
        </p>
      </section>
      <section className="dataset-row">
        <h2>Exact entries first. Suggestions when needed.</h2>
        <p>
          The matcher preserves diacritics and apostrophes, searches in both
          directions, and shows all meanings when a phrase is ambiguous.
          Approximate spelling and phrase matches are labelled as suggestions.
        </p>
        <p className="muted">
          It returns your dictionary’s words and meanings. Unseen translations
          and paraphrases with no shared wording need additional approved
          entries or a separately evaluated semantic model.
        </p>
      </section>
    </>
  );
}

"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, KeyRound, Plus } from "lucide-react";
import { api, Language, post, User } from "@/lib/api";
import { Action, Badge, ErrorNotice, Field, Private } from "./ui";
const blank = {
  name: "",
  alternate_names: [] as string[],
  iso_code: null as string | null,
  description: "",
  default_dialect: "",
  orthography_notes: "",
  source_community: "",
  governance_notes: "",
};
export function LanguageForm({
  language,
  onSaved,
  disabled = false,
}: {
  language?: Language;
  onSaved?: () => Promise<void>;
  disabled?: boolean;
}) {
  const [form, setForm] = useState(
      language
        ? (Object.fromEntries(
            Object.keys(blank).map((k) => [k, language[k as keyof Language]]),
          ) as typeof blank)
        : blank,
    ),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const router = useRouter();
  const set = (key: string, value: unknown) =>
    setForm({ ...form, [key]: value });
  return (
    <>
      <div className="section-title">
        <div>
          {!language && (
            <>
              <div className="eyebrow">NEW LANGUAGE</div>
              <h1>Create a language</h1>
              <p className="muted">
                An isolated workspace for the dictionary and everything you
                build from it.
              </p>
            </>
          )}
        </div>
        <Private />
      </div>
      <form
        className="editor-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            const value = await api<Language>(
              language ? `/languages/${language.id}` : "/languages",
              {
                method: language ? "PATCH" : "POST",
                body: JSON.stringify(form),
              },
            );
            if (onSaved) await onSaved();
            else router.push(`/languages/${value.id}`);
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <fieldset disabled={busy || disabled}>
          <div className="form-grid">
            <Field label="Language name">
              <input
                required
                maxLength={150}
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
                placeholder="e.g. Muruwari"
              />
            </Field>
            <Field label="Alternate names" hint="Separate names with commas.">
              <input
                value={form.alternate_names.join(",")}
                onChange={(e) =>
                  set(
                    "alternate_names",
                    e.target.value ? e.target.value.split(",") : [],
                  )
                }
              />
            </Field>
            <Field
              label="ISO code"
              hint="Optional. A language does not need an ISO code."
            >
              <input
                maxLength={20}
                value={form.iso_code || ""}
                onChange={(e) => set("iso_code", e.target.value || null)}
              />
            </Field>
            <Field label="Default dialect">
              <input
                value={form.default_dialect}
                onChange={(e) => set("default_dialect", e.target.value)}
              />
            </Field>
          </div>
          <Field label="Description">
            <textarea
              rows={3}
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
            />
          </Field>
          <Field label="Source / community">
            <input
              value={form.source_community}
              onChange={(e) => set("source_community", e.target.value)}
            />
          </Field>
          <Field
            label="Orthography notes"
            hint="Record details such as apostrophes, diacritics, case and spelling conventions."
          >
            <textarea
              rows={3}
              value={form.orthography_notes}
              onChange={(e) => set("orthography_notes", e.target.value)}
            />
          </Field>
          <Field
            label="Governance notes"
            hint="Who should be involved in decisions about this language’s data and models?"
          >
            <textarea
              rows={3}
              value={form.governance_notes}
              onChange={(e) => set("governance_notes", e.target.value)}
            />
          </Field>
          <ErrorNotice error={error} />
          <div className="form-actions">
            <button className="button" type="submit">
              {busy
                ? "Saving…"
                : language
                  ? "Save language details"
                  : "Create language"}
              <ArrowRight size={16} />
            </button>
            <span className="caption">
              Dictionaries and models are private by default.
            </span>
          </div>
        </fieldset>
      </form>
    </>
  );
}
export function SettingsView({
  language,
  refresh,
  user,
}: {
  language: Language;
  refresh: () => Promise<void>;
  user: User;
}) {
  const [name, setName] = useState(""),
    [role, setRole] = useState("viewer"),
    [token, setToken] = useState(""),
    [keys, setKeys] = useState<
      { id: string; name: string; role: string; active: boolean }[]
    >([]);
  return (
    <>
      <LanguageForm
        language={language}
        onSaved={refresh}
        disabled={user.role === "viewer"}
      />
      {user.role === "owner" && (
        <section className="settings-access">
          <div className="section-title">
            <h2>
              <KeyRound size={19} />
              Workspace API keys
            </h2>
            <Badge>Owner controls</Badge>
          </div>
          <p className="muted">
            Keys grant access to all languages in this workspace. Create viewer
            keys for inference clients.
          </p>
          <div className="form-grid">
            <Field label="Key name">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Dictionary search service"
              />
            </Field>
            <Field label="Role">
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="viewer">Viewer: read & query</option>
                <option value="editor">Editor: import & train</option>
                <option value="owner">
                  Owner: approve, deploy & manage keys
                </option>
              </select>
            </Field>
          </div>
          <Action
            disabled={!name}
            onClick={async () => {
              const key = await post<{ token: string }>("/keys", {
                name,
                role,
              });
              setToken(key.token);
              setName("");
              setKeys(await api("/keys"));
            }}
          >
            <Plus size={16} />
            Create API key
          </Action>
          {token && (
            <div className="soft-panel">
              <p>Copy this key now. It is only shown once.</p>
              <code className="break-all">{token}</code>
              <button className="button secondary" onClick={() => setToken("")}>
                Dismiss key
              </button>
            </div>
          )}
          <Action secondary onClick={async () => setKeys(await api("/keys"))}>
            Load existing keys
          </Action>
          {keys.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {keys.map((k) => (
                    <tr key={k.id}>
                      <td>{k.name}</td>
                      <td>{k.role}</td>
                      <td>{k.active ? "Active" : "Revoked"}</td>
                      <td>
                        {k.active && k.id !== user.id && (
                          <Action
                            secondary
                            onClick={async () => {
                              await api(`/keys/${k.id}`, { method: "DELETE" });
                              setKeys(await api("/keys"));
                            }}
                          >
                            Revoke
                          </Action>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </>
  );
}

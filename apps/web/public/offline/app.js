import { MAX_BYTES } from "./matcher.mjs";
const $ = (id) => document.getElementById(id);
let worker,
  serial = 0,
  saved = null,
  shellReady = false,
  busy = false;
const pending = new Map();
function resetWorker() {
  worker?.terminate();
  for (const task of pending.values())
    task.reject(new Error("Dictionary changed."));
  pending.clear();
  worker = new Worker("./worker.js", { type: "module" });
  worker.onmessage = ({ data }) => {
    const task = pending.get(data.id);
    pending.delete(data.id);
    if (data.error) task?.reject(new Error(data.error));
    else task?.resolve(data);
  };
  worker.onerror = () => {
    for (const task of pending.values())
      task.reject(
        new Error(
          "Dictionary worker failed. Reopen the app and try a smaller pack.",
        ),
      );
    pending.clear();
  };
}
function request(data) {
  return new Promise((resolve, reject) => {
    const id = ++serial;
    pending.set(id, { resolve, reject });
    worker.postMessage({ ...data, id });
  });
}
function database(action, value) {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open("langai-offline", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("packs");
    open.onerror = () => reject(open.error);
    open.onblocked = () =>
      reject(new Error("Close other dictionary windows and retry."));
    open.onsuccess = () => {
      const db = open.result;
      const transaction = db.transaction(
        "packs",
        action === "get" ? "readonly" : "readwrite",
      );
      const store = transaction.objectStore("packs");
      const op =
        action === "get"
          ? store.get("current")
          : action === "put"
            ? store.put(value, "current")
            : store.delete("current");
      transaction.oncomplete = () => {
        db.close();
        resolve(op.result);
      };
      transaction.onabort = transaction.onerror = () => {
        db.close();
        reject(transaction.error || new Error("Device storage unavailable."));
      };
    };
  });
}
function status() {
  $("availability").textContent = shellReady
    ? saved
      ? "Ready for offline use · Dictionary saved on this device"
      : "Offline app ready · Import a dictionary to start"
    : "Offline access is not ready. Use HTTPS, stay online and reopen this page.";
}
function error(message = "") {
  $("error").textContent = message;
  $("error").hidden = !message;
}
function lock(value) {
  busy = value;
  for (const id of ["pack", "remove", "search", "direction", "query"])
    $(id).disabled = value;
}
function paragraph(parent, text, className = "") {
  const element = document.createElement("p");
  element.textContent = text;
  element.className = className;
  parent.append(element);
}
function show(pack) {
  saved = pack;
  $("dictionary").hidden = !pack;
  $("results").replaceChildren();
  $("sources").replaceChildren();
  $("result-status").textContent = "";
  $("query").value = "";
  if (pack) {
    $("language").textContent = pack.language.name;
    $("details").textContent =
      `${pack.count.toLocaleString()} entries · Pack ${pack.sha256.slice(0, 12)} · Lexical matcher v1`;
    for (const source of pack.sources) {
      const g = source.governance;
      paragraph(
        $("sources"),
        `${source.filename} · Owner: ${g.owner} · ${g.licence}`,
      );
      paragraph(
        $("sources"),
        `Source: ${g.source}${g.custodian ? ` · Custodian: ${g.custodian}` : ""}`,
        "small",
      );
      if (g.attribution) paragraph($("sources"), g.attribution, "small");
      paragraph(
        $("sources"),
        `Redistribution: ${g.redistribution_allowed ? "allowed under source terms" : "not permitted"}. Commercial use: ${g.commercial_use_allowed ? "allowed under source terms" : "not permitted"}.`,
        "small",
      );
    }
  }
  status();
}
$("pack").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file || busy) return;
  lock(true);
  error();
  try {
    if (file.size > MAX_BYTES)
      throw new Error("Choose a dictionary pack smaller than 32 MiB.");
    const text = await file.text();
    const { pack } = await request({ type: "load", text });
    await database("put", text);
    show(pack);
    // Persistence is a request, not a guarantee; the UI always recommends a backup.
    navigator.storage?.persist?.().catch(() => {});
  } catch (e) {
    error(e.message);
    // Loading/storage failure must never leave an unsaved replacement active.
    resetWorker();
    try {
      const previous = await database("get");
      show(
        previous
          ? (await request({ type: "load", text: previous })).pack
          : null,
      );
    } catch {
      show(null);
    }
  } finally {
    event.target.value = "";
    lock(false);
  }
});
$("remove").addEventListener("click", async () => {
  if (busy) return;
  lock(true);
  error();
  try {
    await database("delete");
    resetWorker();
    show(null);
  } catch (e) {
    error(e.message);
  } finally {
    lock(false);
  }
});
$("lookup").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  lock(true);
  error();
  $("results").replaceChildren();
  $("result-status").textContent = "Searching on this device…";
  try {
    const { result } = await request({
      type: "search",
      query: $("query").value,
      direction: $("direction").value,
    });
    const labels = {
      empty: "Enter a word or phrase.",
      exact: "Exact dictionary match",
      ambiguous: "Multiple exact matches — choose the intended entry.",
      suggestions: "Possible matches — review these suggestions.",
      "no-match": "No dictionary match. Try another spelling or phrase.",
    };
    $("result-status").textContent =
      labels[result.kind] +
      (result.total > result.matches.length
        ? ` Showing ${result.matches.length} of ${result.total}; narrow your search for more.`
        : "");
    for (const match of result.matches) {
      const article = document.createElement("article");
      article.className = "match";
      const title = document.createElement("h3");
      title.textContent = match.entry.headword;
      article.append(title);
      for (const definition of match.entry.definitions)
        paragraph(article, definition);
      paragraph(
        article,
        `${match.kind === "exact" ? "Exact match" : "Suggestion"} · Matched ${match.direction === "word-to-meaning" ? "word / variant" : "meaning"}: ${match.matched}`,
        "badge",
      );
      if (match.entry.alternate_spellings.length)
        paragraph(
          article,
          `Also: ${match.entry.alternate_spellings.join("; ")}`,
          "small",
        );
      const source = saved.sources.find((s) => s.id === match.entry.source_id);
      paragraph(
        article,
        [match.entry.part_of_speech, match.entry.dialect, source?.filename]
          .filter(Boolean)
          .join(" · "),
        "small",
      );
      $("results").append(article);
    }
  } catch (e) {
    error(e.message);
    $("result-status").textContent = "Search failed.";
  } finally {
    lock(false);
  }
});
async function start() {
  lock(true);
  try {
    resetWorker();
    const text = await database("get");
    if (text) show((await request({ type: "load", text })).pack);
  } catch (e) {
    error(
      `Saved dictionary could not be loaded: ${e.message}. Import your backup to retry.`,
    );
  } finally {
    lock(false);
  }
  try {
    if (!isSecureContext || !("serviceWorker" in navigator))
      throw new Error("HTTPS is required for offline installation.");
    const registration = await navigator.serviceWorker.register("./sw.js", {
      scope: "./",
      updateViaCache: "none",
    });
    // An active worker has completed the atomic cache install. Bound failure reporting.
    await Promise.race([
      navigator.serviceWorker.ready,
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error("Offline setup timed out.")), 20000),
      ),
    ]);
    shellReady = Boolean(registration.active);
  } catch (e) {
    error(`Offline setup failed: ${e.message}`);
  }
  status();
}
start();

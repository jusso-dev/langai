// Portable lexical decision model. All results point to supplied dictionary entries.
export const MAX_BYTES = 32 * 1024 * 1024;
const normalize = (text) =>
  text.normalize("NFC").trim().replace(/\s+/gu, " ").toLowerCase();
const tokens = (text) =>
  new Set(text.match(/[\p{L}\p{M}\p{N}]+(?:['’][\p{L}\p{M}\p{N}]+)*/gu) || []);
const grams = (text) => {
  const chars = Array.from(text);
  return new Set(
    chars.slice(0, -2).map((_, i) => chars.slice(i, i + 3).join("")),
  );
};
const dice = (a, b) => {
  let overlap = 0;
  for (const value of a) if (b.has(value)) overlap++;
  return a.size + b.size ? (2 * overlap) / (a.size + b.size) : 0;
};
const fail = () => {
  throw new Error(
    "Invalid or unsupported dictionary pack. Export a new pack from LangAI.",
  );
};
const string = (value, max = 10000) =>
  typeof value === "string" && value.length <= max;
const strings = (value) =>
  Array.isArray(value) && value.length <= 1000 && value.every((v) => string(v));
export async function readPack(text) {
  if (new TextEncoder().encode(text).byteLength > MAX_BYTES) fail();
  const envelope = JSON.parse(text);
  if (
    envelope?.format !== "langai-offline-v1" ||
    !string(envelope.payload, MAX_BYTES) ||
    !/^[a-f0-9]{64}$/.test(envelope.sha256)
  )
    fail();
  const bytes = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(envelope.payload),
  );
  const hash = Array.from(new Uint8Array(bytes), (b) =>
    b.toString(16).padStart(2, "0"),
  ).join("");
  if (hash !== envelope.sha256)
    throw new Error(
      "Dictionary integrity check failed. Download the pack again.",
    );
  const pack = JSON.parse(envelope.payload);
  if (
    pack?.engine !== "langai-lexical-v1" ||
    !string(pack.language?.id, 100) ||
    !string(pack.language?.name, 150) ||
    !Array.isArray(pack.entries) ||
    !pack.entries.length ||
    pack.entries.length > 100000 ||
    !Array.isArray(pack.sources) ||
    !pack.sources.length ||
    pack.sources.length > 100
  )
    fail();
  const sources = new Set();
  for (const source of pack.sources) {
    if (
      !string(source?.id, 100) ||
      sources.has(source.id) ||
      !string(source.filename) ||
      !/^[a-f0-9]{64}$/.test(source.sha256) ||
      !source.governance
    )
      fail();
    for (const field of [
      "owner",
      "source",
      "licence",
      "custodian",
      "attribution",
    ])
      if (!string(source.governance[field])) fail();
    for (const field of [
      "training_allowed",
      "commercial_use_allowed",
      "redistribution_allowed",
    ])
      if (typeof source.governance[field] !== "boolean") fail();
    sources.add(source.id);
  }
  const ids = new Set();
  let indexedCharacters = 0;
  for (const entry of pack.entries) {
    if (
      !entry ||
      !string(entry.id, 100) ||
      ids.has(entry.id) ||
      !sources.has(entry.source_id) ||
      !string(entry.headword) ||
      !normalize(entry.headword) ||
      !strings(entry.definitions) ||
      !entry.definitions.length ||
      entry.definitions.some((d) => !normalize(d)) ||
      !strings(entry.alternate_spellings) ||
      !string(entry.part_of_speech) ||
      !string(entry.dialect)
    )
      fail();
    for (const text of [
      entry.headword,
      ...entry.alternate_spellings,
      ...entry.definitions,
    ]) {
      indexedCharacters += Math.min(Array.from(text).length, 256);
      if (indexedCharacters > 2000000)
        throw new Error(
          "Dictionary is too large for phone search. Export fewer sources.",
        );
    }
    ids.add(entry.id);
  }
  return { ...pack, sha256: hash };
}

export function buildMatcher(pack) {
  const exact = new Map(),
    postings = new Map(),
    fields = [];
  const add = (map, key, index) => {
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(index);
  };
  pack.entries.forEach((entry, entryIndex) => {
    for (const [direction, values] of [
      ["word-to-meaning", [entry.headword, ...entry.alternate_spellings]],
      ["meaning-to-word", entry.definitions],
    ]) {
      for (const text of new Set(values.map(normalize))) {
        if (!text) continue;
        const index = fields.length;
        // Long entries remain exact-searchable; bound the approximate index per field.
        const bounded = Array.from(text).slice(0, 256).join("");
        const field = {
          entryIndex,
          direction,
          text,
          tokens: tokens(bounded),
          grams: grams(bounded),
        };
        fields.push(field);
        add(exact, text, index);
        for (const token of field.tokens) add(postings, `t:${token}`, index);
        for (const gram of field.grams) add(postings, `g:${gram}`, index);
      }
    }
  });
  return (query, direction = "both", limit = 20) => {
    if (!["both", "word-to-meaning", "meaning-to-word"].includes(direction))
      throw new Error("Unknown direction");
    query = normalize(query);
    if (Array.from(query).length > 256)
      throw new Error("Use a phrase of at most 256 characters.");
    if (!query) return { kind: "empty", total: 0, matches: [] };
    const allowed = (field) =>
      direction === "both" || field.direction === direction;
    const exactFields = (exact.get(query) || [])
      .map((i) => fields[i])
      .filter(allowed);
    const matches = new Map();
    const put = (field, score, kind) => {
      const previous = matches.get(field.entryIndex);
      if (!previous || score > previous.score)
        matches.set(field.entryIndex, {
          entry: pack.entries[field.entryIndex],
          score,
          kind,
          matched: field.text,
          direction: field.direction,
        });
    };
    for (const field of exactFields) put(field, 1, "exact");
    if (!matches.size) {
      const queryTokens = tokens(query),
        queryGrams = grams(query),
        candidates = new Set();
      for (const token of queryTokens)
        for (const i of postings.get(`t:${token}`) || []) candidates.add(i);
      for (const gram of queryGrams)
        for (const i of postings.get(`g:${gram}`) || []) candidates.add(i);
      for (const index of candidates) {
        const field = fields[index];
        if (!allowed(field)) continue;
        const wordScore = dice(queryTokens, field.tokens),
          charScore = dice(queryGrams, field.grams);
        // Similar spellings / overlapping phrases are suggestions, never automatic mappings.
        const score = Math.max(wordScore, charScore * 0.9);
        if (
          (wordScore >= 0.6 || (query.length >= 4 && charScore >= 0.75)) &&
          score >= 0.6
        )
          put(field, score, "suggestion");
      }
    }
    const ranked = [...matches.values()].sort(
      (a, b) =>
        b.score - a.score ||
        (a.entry.id < b.entry.id ? -1 : a.entry.id > b.entry.id ? 1 : 0),
    );
    return {
      kind: exactFields.length
        ? ranked.length > 1
          ? "ambiguous"
          : "exact"
        : ranked.length
          ? "suggestions"
          : "no-match",
      total: ranked.length,
      matches: ranked.slice(0, limit),
    };
  };
}

import { readPack, buildMatcher } from "./matcher.mjs";
let search;
self.onmessage = async ({ data }) => {
  try {
    if (data.type === "load") {
      const pack = await readPack(data.text);
      const candidate = buildMatcher(pack);
      search = candidate;
      self.postMessage({
        id: data.id,
        pack: {
          language: pack.language,
          sources: pack.sources,
          sha256: pack.sha256,
          count: pack.entries.length,
        },
      });
    } else if (data.type === "search") {
      if (!search) throw new Error("Import a dictionary first.");
      self.postMessage({
        id: data.id,
        result: search(data.query, data.direction),
      });
    }
  } catch (error) {
    self.postMessage({
      id: data.id,
      error: error.message || "Unable to read this dictionary.",
    });
  }
};

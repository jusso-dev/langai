import { NextRequest } from "next/server";
export function sameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  if (process.env.LANGAI_WEB_ORIGIN)
    return origin === process.env.LANGAI_WEB_ORIGIN;
  try {
    const parsed = new URL(origin);
    // Next may bind on 0.0.0.0 internally; compare the browser's actual Host header.
    return (
      ["http:", "https:"].includes(parsed.protocol) &&
      parsed.host === request.headers.get("host")
    );
  } catch {
    return false;
  }
}

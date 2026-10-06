import { sameOrigin } from "@/lib/origin";
import { boundedBody, PayloadTooLarge } from "@/lib/body";
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  if (!["GET", "HEAD"].includes(request.method) && !sameOrigin(request))
    return NextResponse.json({ detail: "Invalid origin" }, { status: 403 });
  const token = (await cookies()).get("langai_session")?.value;
  if (!token)
    return NextResponse.json(
      { detail: "Connect your workspace to continue" },
      { status: 401 },
    );
  const { path } = await context.params;
  const url = `${process.env.LANGAI_API_URL || "http://127.0.0.1:8100"}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  if (request.headers.get("content-type"))
    headers["Content-Type"] = request.headers.get("content-type")!;
  try {
    const response = await fetch(url, {
      method: request.method,
      headers,
      cache: "no-store",
      body: ["GET", "HEAD"].includes(request.method)
        ? undefined
        : await boundedBody(request, 26 * 1024 * 1024),
      signal: request.signal,
    });
    if (response.ok && path.join("/") === "openapi.json") {
      const schema = await response.json();
      schema.servers = [{ url: "/api/proxy" }];
      return NextResponse.json(schema, {
        headers: { "Cache-Control": "no-store" },
      });
    }
    if (response.ok && path.join("/") === "docs") {
      const html = (await response.text()).replace(
        "url: '/openapi.json'",
        "url: '/api/proxy/openapi.json'",
      );
      return new Response(html, {
        headers: { "Content-Type": "text/html", "Cache-Control": "no-store" },
      });
    }
    return new Response(response.body, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("content-type") || "application/json",
        "Cache-Control": "no-store",
        "X-Accel-Buffering": "no",
        ...(response.headers.get("content-disposition")
          ? {
              "Content-Disposition": response.headers.get(
                "content-disposition",
              )!,
            }
          : {}),
      },
    });
  } catch (error) {
    if (error instanceof PayloadTooLarge)
      return NextResponse.json(
        { detail: "Request exceeds the upload limit" },
        { status: 413 },
      );
    return NextResponse.json(
      { detail: "The API is unavailable. Check the API service and retry." },
      { status: 503 },
    );
  }
}
export { proxy as GET, proxy as POST, proxy as PATCH, proxy as DELETE };

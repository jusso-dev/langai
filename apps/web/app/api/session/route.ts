import { sameOrigin } from "@/lib/origin";
import { boundedBody, PayloadTooLarge } from "@/lib/body";
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
const base = process.env.LANGAI_API_URL || "http://127.0.0.1:8100";
export async function POST(request: NextRequest) {
  if (!sameOrigin(request))
    return NextResponse.json({ detail: "Invalid origin" }, { status: 403 });
  let token: unknown;
  try {
    ({ token } = JSON.parse(
      new TextDecoder().decode(await boundedBody(request, 2048)),
    ));
  } catch (error) {
    return NextResponse.json(
      { detail: "Provide a valid API key payload" },
      { status: error instanceof PayloadTooLarge ? 413 : 400 },
    );
  }
  if (typeof token !== "string" || token.length > 512)
    return NextResponse.json({ detail: "API key required" }, { status: 400 });
  try {
    const upstream = await fetch(`${base}/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    });
    if (!upstream.ok)
      return NextResponse.json(
        { detail: "This API key was not accepted" },
        { status: 401 },
      );
    (await cookies()).set("langai_session", token, {
      httpOnly: true,
      secure: process.env.LANGAI_COOKIE_SECURE === "true",
      sameSite: "strict",
      path: "/",
      maxAge: 28800,
    });
    return NextResponse.json(await upstream.json());
  } catch {
    return NextResponse.json(
      {
        detail: "The API is unavailable. Start the API service and try again.",
      },
      { status: 503 },
    );
  }
}
export async function DELETE(request: NextRequest) {
  if (!sameOrigin(request))
    return NextResponse.json({ detail: "Invalid origin" }, { status: 403 });
  (await cookies()).delete("langai_session");
  return NextResponse.json({ ok: true });
}

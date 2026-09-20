import { auth } from "@/lib/auth";
import { headers } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

/**
 * POST /api/datasets/upload
 *
 * Browser-facing BFF (Backend-for-Frontend) proxy that:
 *   1. Verifies the Better Auth session via cookie
 *   2. Reconstructs the multipart FormData
 *   3. Forwards it to the FastAPI stat-engine with auth headers injected
 *   4. Returns the FastAPI response to the browser
 */
export async function POST(req: NextRequest) {
  // ── 1. Verify session ───────────────────────────────────────────
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  if (!session?.user?.id) {
    return NextResponse.json(
      { error: "Unauthenticated" },
      { status: 401 }
    );
  }

  const userId = session.user.id;

  // ── 2. Read incoming FormData (single read, no arrayBuffer copy) ─
  let formData: FormData;
  try {
    formData = await req.formData();
  } catch {
    return NextResponse.json(
      { error: "Invalid multipart request" },
      { status: 400 }
    );
  }

  // ── 3. Reconstruct FormData for downstream fetch ────────────────
  const downstreamForm = new FormData();

  const file = formData.get("file");
  const projectId = formData.get("project_id");
  const name = formData.get("name");

  if (!file || !(file instanceof Blob)) {
    return NextResponse.json(
      { error: "Missing file" },
      { status: 400 }
    );
  }

  if (!projectId || typeof projectId !== "string") {
    return NextResponse.json(
      { error: "Missing project_id" },
      { status: 400 }
    );
  }

  downstreamForm.append("file", file);
  downstreamForm.append("project_id", projectId);
  if (name && typeof name === "string") {
    downstreamForm.append("name", name);
  }

  // ── 4. Forward to FastAPI ───────────────────────────────────────
  const statEngineUrl =
    process.env.STAT_ENGINE_URL || "http://127.0.0.1:8000";
  const internalSecret =
    process.env.STAT_ENGINE_INTERNAL_SECRET || "";

  let upstream: Response;
  try {
    upstream = await fetch(
      `${statEngineUrl}/api/v1/datasets/upload`,
      {
        method: "POST",
        headers: {
          "X-Internal-Secret": internalSecret,
          "X-User-Id": userId,
        },
        body: downstreamForm,
      }
    );
  } catch (err) {
    console.error("Failed to reach stat-engine:", err);
    return NextResponse.json(
      { error: "Stat-engine unavailable" },
      { status: 502 }
    );
  }

  // ── 5. Forward the response as-is ───────────────────────────────
  const body = await upstream.text();
  return new NextResponse(body, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") || "application/json",
    },
  });
}

import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { cookieName, expectedToken } from "../../../lib/auth";

export async function POST(request) {
  const pin = process.env.CHECKIN_PIN || "4163";
  const form = await request.formData();
  const entered = String(form.get("pin") || "");
  const next = String(form.get("next") || "/");
  const safeNext = next.startsWith("/") ? next : "/";
  if (!pin || entered !== pin) {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", safeNext);
    url.searchParams.set("error", "1");
    return NextResponse.redirect(url, 303);
  }
  const jar = await cookies();
  jar.set(cookieName(), expectedToken(), {
    httpOnly: true,
    secure: process.env.VERCEL === "1",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 12,
  });
  return NextResponse.redirect(new URL(safeNext, request.url), 303);
}

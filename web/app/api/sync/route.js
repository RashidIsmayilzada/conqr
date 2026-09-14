import { NextResponse } from "next/server";
import { saveCsv } from "../../../lib/store";

export async function POST(request) {
  const secret = process.env.CHECKIN_SYNC_SECRET || "";
  const header = request.headers.get("authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (!secret || token !== secret) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const csv = await request.text();
  if (!csv.includes("qr_code")) {
    return NextResponse.json({ error: "invalid csv" }, { status: 400 });
  }
  await saveCsv(csv);
  return NextResponse.json({ ok: true });
}

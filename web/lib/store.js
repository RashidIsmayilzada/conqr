import fs from "fs";
import path from "path";

const TMP = "/tmp/conqr-guests.csv";
const KEY = "conqr_guests";

function bundledPath() {
  return path.join(process.cwd(), "data", "guests.csv");
}

async function kvGet() {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) {
    return null;
  }
  const res = await fetch(`${url}/get/${KEY}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) {
    return null;
  }
  const data = await res.json();
  return data.result || null;
}

async function kvSet(csv) {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) {
    return false;
  }
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(["SET", KEY, csv]),
  });
  return res.ok;
}

export async function loadCsv() {
  const fromKv = await kvGet();
  if (fromKv) {
    return fromKv;
  }
  if (fs.existsSync(TMP)) {
    return fs.readFileSync(TMP, "utf8");
  }
  const bundled = bundledPath();
  if (fs.existsSync(bundled)) {
    return fs.readFileSync(bundled, "utf8");
  }
  return "qr_code,buyer_email,full_name,payment,table,baby_kid,emailed,checked_in,checked_in_at\n";
}

export async function saveCsv(csv) {
  await kvSet(csv);
  try {
    fs.writeFileSync(TMP, csv);
  } catch {
    // serverless may not allow writes outside /tmp
  }
}

function parseLine(line) {
  const out = [];
  let current = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') {
      quoted = !quoted;
    } else if (ch === "," && !quoted) {
      out.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  out.push(current);
  return out;
}

export function parseGuests(csv) {
  const lines = csv.split(/\r?\n/).filter((line) => line.trim());
  if (!lines.length) {
    return [];
  }
  const headers = parseLine(lines[0]).map((h) => h.trim());
  return lines.slice(1).map((line) => {
    const cols = parseLine(line);
    const row = {};
    headers.forEach((header, idx) => {
      row[header] = (cols[idx] || "").trim();
    });
    return row;
  });
}

export function toCsv(guests) {
  const headers = [
    "qr_code",
    "buyer_email",
    "full_name",
    "payment",
    "table",
    "baby_kid",
    "emailed",
    "checked_in",
    "checked_in_at",
  ];
  const lines = [headers.join(",")];
  for (const guest of guests) {
    lines.push(headers.map((h) => guest[h] || "").join(","));
  }
  return lines.join("\n") + "\n";
}

export async function findAndCheckIn(code) {
  const csv = await loadCsv();
  const guests = parseGuests(csv);
  if (!code) {
    return { status: "not_found", guest: null };
  }
  const guest = guests.find((row) => row.qr_code === code);
  if (!guest) {
    return { status: "not_found", guest: null };
  }
  if (guest.checked_in === "yes") {
    return { status: "already", guest };
  }
  guest.checked_in = "yes";
  guest.checked_in_at = new Date().toISOString().replace("T", " ").slice(0, 19) + " UTC";
  await saveCsv(toCsv(guests));
  notifySheetCheckin(guest);
  return { status: "ok", guest };
}

async function notifySheetCheckin(guest) {
  const url = process.env.SHEET_CHECKIN_URL;
  const secret = process.env.SHEET_CHECKIN_SECRET;
  if (!url || !secret) {
    return;
  }
  try {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        secret,
        email: guest.buyer_email || "",
        full_name: guest.full_name || "",
        checked_in_at: guest.checked_in_at || "",
      }),
    });
  } catch (error) {
    console.error("[!] Could not update the Google Sheet check-in status:", error);
  }
}

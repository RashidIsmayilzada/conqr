import { createHmac } from "crypto";
import { cookies } from "next/headers";

const COOKIE = "conqr_ok";

export function expectedToken() {
  const pin = process.env.CHECKIN_PIN || "4163";
  return createHmac("sha256", pin).update("conqr-checkin").digest("hex");
}

export async function isAuthed() {
  const token = expectedToken();
  if (!token) {
    return false;
  }
  const jar = await cookies();
  return jar.get(COOKIE)?.value === token;
}

export function cookieName() {
  return COOKIE;
}

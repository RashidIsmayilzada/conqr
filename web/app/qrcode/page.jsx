import { redirect } from "next/navigation";
import { isAuthed } from "../../lib/auth";
import { findAndCheckIn } from "../../lib/store";

export const dynamic = "force-dynamic";

function Card({ status, guest }) {
  const banner =
    status === "ok"
      ? { bg: "#16a34a", text: "Checked in" }
      : status === "already"
        ? { bg: "#d97706", text: "Already checked in", color: "#111" }
        : { bg: "#dc2626", text: "Ticket not found" };
  const unpaid = guest && guest.payment !== "paid";
  const paymentLabel = guest
    ? guest.payment === "paid"
      ? "paid"
      : "pay at restaurant"
    : "";

  return (
    <main style={{ padding: 20 }}>
      <div
        style={{
          padding: 16,
          fontSize: "1.6rem",
          fontWeight: 700,
          borderRadius: 8,
          marginBottom: 16,
          background: banner.bg,
          color: banner.color || "#fff",
        }}
      >
        {banner.text}
      </div>
      {unpaid ? (
        <div
          style={{
            background: "#ea580c",
            padding: 14,
            fontSize: "1.4rem",
            fontWeight: 800,
            borderRadius: 8,
            marginBottom: 16,
          }}
        >
          PAY AT RESTAURANT
        </div>
      ) : null}
      {guest ? (
        <>
          <div style={{ fontSize: "2.2rem", fontWeight: 800, margin: "12px 0 20px" }}>
            {guest.full_name}
          </div>
          <Row label="Table" value={guest.table} />
          <Row label="Payment" value={paymentLabel} />
          <Row label="Baby / kid" value={guest.baby_kid === "yes" ? "yes" : "no"} />
          <Row label="Buyer email" value={guest.buyer_email} />
          <Row label="Checked in at" value={guest.checked_in_at || ""} />
        </>
      ) : null}
    </main>
  );
}

function Row({ label, value }) {
  return (
    <div style={{ fontSize: "1.25rem", margin: "10px 0", lineHeight: 1.4 }}>
      <span
        style={{
          display: "block",
          fontSize: "0.8rem",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          color: "#a3a3a3",
        }}
      >
        {label}
      </span>
      {value}
    </div>
  );
}

export default async function QrcodePage({ searchParams }) {
  const params = await searchParams;
  const q = (params.q || "").trim();
  if (!(await isAuthed())) {
    redirect(`/login?next=${encodeURIComponent(`/qrcode?q=${q}`)}`);
  }
  const result = await findAndCheckIn(q);
  return <Card status={result.status} guest={result.guest} />;
}

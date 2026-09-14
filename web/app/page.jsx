import { redirect } from "next/navigation";
import { isAuthed } from "../lib/auth";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  if (!(await isAuthed())) {
    redirect("/login?next=/");
  }
  return (
    <main style={{ padding: 24 }}>
      <h1 style={{ fontSize: "1.8rem" }}>Scanner ready</h1>
      <p style={{ fontSize: "1.15rem", lineHeight: 1.5, color: "#d4d4d4" }}>
        Scan a guest QR code with this phone. Guest name, table, payment, and
        baby/kid details will show on the next screen and stay there.
      </p>
    </main>
  );
}

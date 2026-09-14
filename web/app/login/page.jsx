export default async function LoginPage({ searchParams }) {
  const params = await searchParams;
  const next = params.next || "/";
  const error = params.error;

  return (
    <main style={{ padding: 24, maxWidth: 420 }}>
      <h1 style={{ fontSize: "1.8rem" }}>Staff access</h1>
      <p style={{ color: "#d4d4d4", lineHeight: 1.5 }}>
        Enter the check-in PIN. Guests do not need this — only the phone that
        scans tickets at the door.
      </p>
      {error ? (
        <p style={{ color: "#f87171", fontWeight: 700 }}>Wrong PIN</p>
      ) : null}
      <form action="/api/login" method="post">
        <input type="hidden" name="next" value={next} />
        <input
          type="password"
          name="pin"
          inputMode="numeric"
          autoFocus
          placeholder="PIN"
          style={{
            width: "100%",
            fontSize: "1.4rem",
            padding: 14,
            borderRadius: 8,
            border: 0,
            margin: "16px 0",
            boxSizing: "border-box",
          }}
        />
        <button
          type="submit"
          style={{
            width: "100%",
            fontSize: "1.2rem",
            fontWeight: 700,
            padding: 14,
            borderRadius: 8,
            border: 0,
            background: "#16a34a",
            color: "#fff",
          }}
        >
          Unlock
        </button>
      </form>
    </main>
  );
}

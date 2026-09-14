export const metadata = {
  title: "Hemrelik check-in",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          fontFamily:
            "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
          background: "#111",
          color: "#fff",
        }}
      >
        {children}
      </body>
    </html>
  );
}

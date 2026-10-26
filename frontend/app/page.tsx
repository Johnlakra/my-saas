export default function Home() {
  return (
    <main style={{ maxWidth: 640, margin: "80px auto", padding: "0 16px" }}>
      <h1>{process.env.NEXT_PUBLIC_APP_NAME ?? "My SaaS"}</h1>
      <p>Walking skeleton is live. Agents will build the product from here.</p>
    </main>
  );
}

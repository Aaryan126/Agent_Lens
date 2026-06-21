const timelineItems = [
  "Session started",
  "Tool call captured",
  "Policy evaluated",
  "Risk classified",
  "Gate decision recorded",
];

export default function Home() {
  return (
    <main className="min-h-screen bg-neutral-50 text-neutral-950">
      <section className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-6 py-10">
        <div>
          <p className="text-sm font-medium uppercase tracking-wide text-emerald-700">
            AgentLens Ledger
          </p>
          <h1 className="mt-2 text-4xl font-semibold">Session replay for agent decisions</h1>
          <p className="mt-3 max-w-2xl text-base text-neutral-600">
            This shell will render trace events, policy matches, risk evidence, human approvals,
            drift flags, and trust metrics as the backend API stabilizes.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {timelineItems.map((item, index) => (
            <article key={item} className="rounded-lg border border-neutral-200 bg-white p-5">
              <p className="text-sm text-neutral-500">Step {index + 1}</p>
              <h2 className="mt-2 text-xl font-medium">{item}</h2>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}


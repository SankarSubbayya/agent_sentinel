export function Footer() {
  return (
    <footer className="mx-auto mt-12 w-full max-w-[1400px] border-t border-border/60 px-6 py-4">
      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-muted-foreground/80">
        <div className="flex items-center gap-3">
          <span className="mono">sentinel · governance plane</span>
          <span className="hidden md:inline">·</span>
          <span className="hidden md:inline">
            built on Gemini 2.5 Flash + Pro · Cached Content for full-policy
            long-context reasoning
          </span>
        </div>
        <div className="flex items-center gap-3 mono">
          <span>MIT</span>
          <span>·</span>
          <a
            href="https://github.com/SankarSubbayya/agent_sentinel"
            className="hover:text-foreground"
            target="_blank"
            rel="noreferrer"
          >
            github
          </a>
        </div>
      </div>
    </footer>
  );
}

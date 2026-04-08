import { useEffect, useState } from "react";

const REPO_URL = "https://github.com/gaelgael5/mcp-manager";

interface Stats {
  total_services: number;
  total_skills: number;
  total_skill_sources: number;
  by_source: Record<string, number>;
}

export default function LandingPage() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    fetch("/api/v1/stats")
      .then((r) => r.json())
      .then(setStats)
      .catch(() => {});
  }, []);

  const sourceCount = stats ? Object.keys(stats.by_source).length : 5;

  return (
    <div style={{ minHeight: "100vh", background: "#fafafa", color: "#111" }}>
      {/* Hero */}
      <header style={{ padding: "64px 24px 48px", textAlign: "center", borderBottom: "1px solid #e5e7eb" }}>
        <p style={{ fontSize: 12, color: "#6b7280", textTransform: "uppercase", letterSpacing: 2, marginBottom: 8 }}>
          Open Source
        </p>
        <h1 style={{ fontSize: 36, fontWeight: 800, margin: "0 0 12px" }}>MCP Manager</h1>
        <p style={{ fontSize: 16, color: "#6b7280", maxWidth: 480, margin: "0 auto 28px", lineHeight: 1.6 }}>
          A unified registry of {stats ? stats.total_services.toLocaleString() : "18,000+"} MCP servers.
          <br />
          Aggregate, search, and install from {sourceCount} sources.
        </p>

        <div
          style={{
            background: "#111",
            color: "#4ade80",
            fontFamily: "monospace",
            fontSize: 13,
            padding: "14px 20px",
            borderRadius: 8,
            display: "inline-block",
            textAlign: "left",
            lineHeight: 1.8,
            position: "relative",
          }}
        >
          <span style={{ color: "#6b7280" }}>$</span> git clone {REPO_URL}
          <br />
          <span style={{ color: "#6b7280" }}>$</span> cd mcp-manager && ./build.sh && ./launch.sh
        </div>

        <div style={{ marginTop: 24, display: "flex", gap: 12, justifyContent: "center" }}>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: "#111",
              fontSize: 13,
              fontWeight: 600,
              border: "1px solid #d1d5db",
              padding: "8px 20px",
              borderRadius: 6,
              textDecoration: "none",
              background: "#fff",
            }}
          >
            ★ GitHub
          </a>
          <a
            href="#install"
            style={{
              color: "#fff",
              background: "#111",
              fontSize: 13,
              fontWeight: 600,
              padding: "8px 20px",
              borderRadius: 6,
              textDecoration: "none",
            }}
          >
            Get Started ↓
          </a>
        </div>
      </header>

      {/* Highlights */}
      <section
        style={{
          display: "flex",
          borderBottom: "1px solid #e5e7eb",
          textAlign: "center",
        }}
      >
        {[
          { value: stats ? stats.total_services.toLocaleString() : "—", label: "MCP Servers" },
          { value: stats ? String(sourceCount) : "—", label: "Sources" },
          { value: stats ? String(stats.total_skill_sources) : "—", label: "Skill Sources" },
          { value: stats ? String(stats.total_skills) : "—", label: "Skills" },
          { value: "RAG", label: "Semantic Search" },
        ].map((item, i, arr) => (
          <div
            key={item.label}
            style={{
              flex: 1,
              padding: "28px 16px",
              borderRight: i < arr.length - 1 ? "1px solid #e5e7eb" : "none",
            }}
          >
            <div style={{ fontSize: 24, fontWeight: 800 }}>{item.value}</div>
            <div style={{ fontSize: 12, color: "#6b7280", marginTop: 4 }}>{item.label}</div>
          </div>
        ))}
      </section>

      {/* Installation */}
      <section id="install" style={{ padding: "48px 24px", maxWidth: 900, margin: "0 auto" }}>
        <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 24 }}>Installation</h2>
        <div style={{ display: "flex", gap: 16 }}>
          {[
            {
              step: "1",
              title: "Clone",
              cmd: `git clone ${REPO_URL}\ncd mcp-manager`,
            },
            {
              step: "2",
              title: "Configure",
              cmd: "cp .env.example .env\n# Edit .env with your settings",
            },
            {
              step: "3",
              title: "Build & Launch",
              cmd: "./build.sh\n./launch.sh",
            },
          ].map((s) => (
            <div
              key={s.step}
              style={{
                flex: 1,
                background: "#fff",
                border: "1px solid #e5e7eb",
                borderRadius: 8,
                padding: 20,
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  color: "#6b7280",
                  textTransform: "uppercase",
                  letterSpacing: 1,
                  marginBottom: 8,
                }}
              >
                Step {s.step} — {s.title}
              </div>
              <pre
                style={{
                  fontFamily: "monospace",
                  fontSize: 12,
                  color: "#111",
                  background: "#f9fafb",
                  padding: 12,
                  borderRadius: 6,
                  margin: 0,
                  whiteSpace: "pre-wrap",
                  lineHeight: 1.6,
                }}
              >
                {s.cmd}
              </pre>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer
        style={{
          padding: "32px 24px",
          textAlign: "center",
          borderTop: "1px solid #e5e7eb",
          color: "#6b7280",
          fontSize: 13,
        }}
      >
        <p style={{ margin: "0 0 6px" }}>Built with FastAPI + PostgreSQL + React</p>
        <a
          href={REPO_URL}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: "#3b82f6", textDecoration: "none" }}
        >
          github.com/gaelgael5/mcp-manager
        </a>
      </footer>
    </div>
  );
}

import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

const steps = [
  { title: "1. Ingestion", desc: "Shallow-clones any public repo via GitPython, walks it for Python/JS/TS files, skips node_modules, .git, and build artifacts." },
  { title: "2. AST Chunking", desc: "Parses each file with tree-sitter and extracts function/class/method-level chunks — not fixed-size text splits — each with exact file and line-range metadata." },
  { title: "3. Call Graph", desc: "Extracts every function call inside each chunk, resolves raw names to actual chunk IDs (same-file first, then repo-wide for unambiguous names), and builds a directed graph with NetworkX." },
  { title: "4. Embedding", desc: "Each chunk is embedded locally with sentence-transformers (free, no API key) and stored in a persistent ChromaDB vector index." },
  { title: "5. Agent Loop", desc: "On a question: vector-retrieve top-k chunks, check the call graph for missing dependencies of what was retrieved, pull those in too, repeat up to 2 hops, then generate a cited answer." },
  { title: "6. Eval Loop", desc: "The answer is scored for faithfulness by an LLM judge, and a deterministic check confirms every citation actually exists in the retrieved context. Low scores trigger one automatic retry with wider retrieval." },
];

export default function HowItWorks() {
  return (
    <div className="how-page" style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      <div className="bg-glow" />
      <h1>How it works</h1>
      <p className="hero-sub">A walk through the full pipeline, end to end.</p>

      <div className="steps-list">
        {steps.map((s, i) => (
          <div className="step-row" key={i}>
            <div className="step-num">{i + 1}</div>
            <div>
              <h3>{s.title.replace(/^\d+\.\s*/, "")}</h3>
              <p>{s.desc}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="cta-section">
        <Link to="/app" className="btn-primary btn-lg">Try it live <ArrowRight size={16} /></Link>
      </div>
    </div>
  );
}
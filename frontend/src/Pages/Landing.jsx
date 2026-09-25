import { Link } from "react-router-dom";
import { Network, GitBranch, Sparkles, ArrowRight, Zap } from "lucide-react";

export default function Landing() {
  return (
    <div className="landing">
      <div className="bg-glow" />
      <section className="hero">
        <div className="hero-badge"><Zap size={13} /> Graph-aware agentic RAG</div>
        <h1>Ask any codebase<br /><span className="gradient-text">how it actually works</span></h1>
        <p className="hero-sub">
          Not top-k vector search. An agent that traces function calls across files
          through a real dependency graph, retrieves what plain RAG misses, and
          checks its own answers before showing them to you.
        </p>
        <div className="hero-cta">
          <Link to="/app" className="btn-primary btn-lg">Try it live <ArrowRight size={16} /></Link>
          <Link to="/how-it-works" className="btn-ghost btn-lg">How it works</Link>
        </div>
      </section>

      <section className="feature-section">
        <h2>Why this isn't just another RAG chatbot</h2>
        <div className="feature-grid">
          <div className="feature-card">
            <Network size={22} className="feature-icon" />
            <h4>AST-aware chunking</h4>
            <p>Parses real function/class boundaries with tree-sitter — every chunk is a complete, semantically meaningful unit, not an arbitrary text slice.</p>
          </div>
          <div className="feature-card">
            <GitBranch size={22} className="feature-icon" />
            <h4>Graph-aware retrieval</h4>
            <p>Builds a real call graph from parsed function calls. The agent traverses it, iteratively pulling in dependencies plain vector search misses.</p>
          </div>
          <div className="feature-card">
            <Sparkles size={22} className="feature-icon" />
            <h4>Self-checking answers</h4>
            <p>Every answer is scored for faithfulness by an LLM judge, plus a deterministic check that every citation actually exists in retrieved context.</p>
          </div>
        </div>
      </section>

      <section className="cta-section">
        <h2>See the difference yourself</h2>
        <p>Index any public GitHub repo and compare agentic retrieval against plain baseline RAG, side by side.</p>
        <Link to="/app" className="btn-primary btn-lg">Launch the app <ArrowRight size={16} /></Link>
      </section>
    </div>
  );
}
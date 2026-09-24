import { useState, useRef, useEffect } from "react";
import axios from "axios";
import { Search, GitBranch, Loader2, ChevronDown, CheckCircle2, Sparkles, FileCode2, Network } from "lucide-react";
import "./App.css";

const API_BASE = "http://localhost:8000";

function ScoreRing({ label, value }) {
  const pct = value == null ? 0 : Math.round(value * 100);
  const color = pct >= 70 ? "#4ade80" : pct >= 40 ? "#facc15" : "#f87171";
  return (
    <div className="score-ring">
      <svg width="46" height="46" viewBox="0 0 46 46">
        <circle cx="23" cy="23" r="19" fill="none" stroke="#232838" strokeWidth="4" />
        <circle
          cx="23" cy="23" r="19" fill="none" stroke={color} strokeWidth="4"
          strokeDasharray={`${(pct / 100) * 119.4} 119.4`}
          strokeLinecap="round" transform="rotate(-90 23 23)"
        />
      </svg>
      <div className="score-ring-text">
        <span style={{ color }}>{pct}</span>
      </div>
      <span className="score-ring-label">{label}</span>
    </div>
  );
}

function TraceTimeline({ trace }) {
  return (
    <div className="timeline">
      {trace.map((step, i) => {
        const isExpansion = step.step?.startsWith("graph_expansion");
        const isEval = step.step === "eval";
        const isRetry = step.step === "retry_triggered";
        return (
          <div className="timeline-item" key={i}>
            <div className={`timeline-dot ${isEval ? "dot-eval" : isRetry ? "dot-retry" : "dot-default"}`} />
            <div className="timeline-content">
              <div className="timeline-title">
                {step.step === "initial_retrieval" && <><Search size={13} /> Initial vector retrieval</>}
                {isExpansion && <><Network size={13} /> Call-graph expansion — hop {step.step.split("_").pop()}</>}
                {isEval && <><Sparkles size={13} /> Faithfulness check</>}
                {isRetry && <>Retry triggered — widening retrieval</>}
              </div>
              {step.found && (
                <div className="timeline-chunks">{step.found.length} chunks retrieved by embedding similarity</div>
              )}
              {step.added && (
                <div className="timeline-chunks">
                  {step.added.length === 0
                    ? "No new dependencies found — expansion complete"
                    : `+${step.added.length} chunks pulled in via function-call graph`}
                </div>
              )}
              {isEval && (
                <div className="timeline-chunks">{step.reason}</div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AnswerCard({ item }) {
  const [showTrace, setShowTrace] = useState(false);
  return (
    <div className="answer-card">
      <div className="answer-question">
        <FileCode2 size={15} />
        <span>{item.question}</span>
      </div>

      <p className="answer-text">{item.answer}</p>

      <div className="answer-footer">
        {item.eval && (
          <div className="scores">
            <ScoreRing label="Faithfulness" value={item.eval.faithfulness} />
            <ScoreRing label="Relevance" value={item.eval.relevance} />
          </div>
        )}
        <div className="chunk-pills">
          {item.chunks_used?.slice(0, 6).map((id) => (
            <span className="pill" key={id} title={id}>{id.split("::")[1] || id}</span>
          ))}
          {item.chunks_used?.length > 6 && <span className="pill pill-more">+{item.chunks_used.length - 6} more</span>}
        </div>
      </div>

      <button className="trace-toggle" onClick={() => setShowTrace(!showTrace)}>
        <ChevronDown size={14} className={showTrace ? "rotated" : ""} />
        {showTrace ? "Hide" : "Show"} agent reasoning trace
      </button>

      {showTrace && <TraceTimeline trace={item.trace} />}
    </div>
  );
}

function App() {
  const [repoUrl, setRepoUrl] = useState("https://github.com/pallets/flask.git");
  const [question, setQuestion] = useState("");
  const [indexed, setIndexed] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [chunkCount, setChunkCount] = useState(null);
  const [querying, setQuerying] = useState(false);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history]);

  const handleIndex = async () => {
    setIndexing(true);
    setError("");
    setHistory([]);
    try {
      const res = await axios.post(`${API_BASE}/index`, { repo_url: repoUrl });
      setIndexed(true);
      setChunkCount(res.data.chunk_count);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to index repo");
    } finally {
      setIndexing(false);
    }
  };

  const handleAsk = async () => {
    if (!question.trim()) return;
    const q = question;
    setQuestion("");
    setQuerying(true);
    setError("");
    try {
      const res = await axios.post(`${API_BASE}/query`, { repo_url: repoUrl, question: q });
      setHistory((h) => [...h, { question: q, ...res.data }]);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to get answer");
    } finally {
      setQuerying(false);
    }
  };

  return (
    <div className="app">
      <div className="bg-glow" />

      <header className="header">
        <div className="header-badge"><GitBranch size={14} /> Agentic Codebase RAG</div>
        <h1>Ask any codebase <span className="gradient-text">how it actually works</span></h1>
        <p className="subtitle">
          Not top-k vector search — an agent that traces function calls across files via a
          dependency graph before answering, with a self-checking faithfulness eval.
        </p>
      </header>

      <div className="panel index-panel">
        <div className="row">
          <input
            value={repoUrl}
            onChange={(e) => { setRepoUrl(e.target.value); setIndexed(false); }}
            placeholder="https://github.com/owner/repo.git"
          />
          <button className="btn-primary" onClick={handleIndex} disabled={indexing}>
            {indexing ? <><Loader2 size={15} className="spin" /> Indexing...</> : indexed ? "Re-index" : "Index Repo"}
          </button>
        </div>
        {indexed && (
          <div className="status-ok"><CheckCircle2 size={14} /> Indexed {chunkCount} functions/classes — ready for questions</div>
        )}
      </div>

      {error && <div className="error">{error}</div>}

      <div className="chat-history">
        {history.map((item, i) => <AnswerCard item={item} key={i} />)}
        <div ref={bottomRef} />
      </div>

      <div className="panel ask-panel">
        <div className="row">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={indexed ? "How does session cookie signing work?" : "Index a repo first..."}
            disabled={!indexed}
            onKeyDown={(e) => e.key === "Enter" && handleAsk()}
          />
          <button className="btn-primary" onClick={handleAsk} disabled={!indexed || querying}>
            {querying ? <Loader2 size={15} className="spin" /> : "Ask"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
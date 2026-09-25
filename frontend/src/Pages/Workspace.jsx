import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useState, useRef, useEffect } from "react";
import axios from "axios";
import { Search, GitBranch, Loader2, ChevronDown, CheckCircle2, Sparkles, FileCode2, Network } from "lucide-react";
import "../App.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

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

function MarkdownAnswer({ text }) {
  return (
    <ReactMarkdown
      components={{
        code({ inline, className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || "");
          return !inline ? (
            <SyntaxHighlighter style={oneDark} language={match?.[1] || "python"} customStyle={{ borderRadius: 8, fontSize: 12.5, margin: "10px 0" }} {...props}>
              {String(children).replace(/\n$/, "")}
            </SyntaxHighlighter>
          ) : (
            <code className="inline-code" {...props}>{children}</code>
          );
        },
      }}
    >
      {text}
    </ReactMarkdown>
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

      <div className="answer-text"><MarkdownAnswer text={item.answer} /></div>

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

function CompareCard({ item }) {
  const { agentic, baseline } = item.compare;
  return (
    <div className="answer-card">
      <div className="answer-question">
        <FileCode2 size={15} />
        <span>{item.question}</span>
      </div>

      <div className="compare-grid">
        <div className="compare-col">
          <div className="compare-label baseline-label">Baseline RAG</div>
          <p className="answer-text small">{baseline.answer}</p>
          <div className="compare-stats">
            <span>{baseline.chunks_used.length} chunks</span>
            <span>{baseline.stats.llm_calls} LLM call</span>
            <span>{baseline.stats.tokens_used} tokens</span>
            <span>{baseline.stats.latency_seconds}s</span>
          </div>
        </div>
        <div className="compare-col">
          <div className="compare-label agentic-label">Agentic (graph-aware)</div>
          <p className="answer-text small">{agentic.answer}</p>
          <div className="compare-stats">
            <span>{agentic.chunks_used.length} chunks</span>
            <span>{agentic.stats.llm_calls} LLM calls</span>
            <span>{agentic.stats.tokens_used} tokens</span>
            <span>{agentic.stats.latency_seconds}s</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ onPick }) {
  const examples = [
    { name: "Flask", url: "https://github.com/pallets/flask.git" },
    { name: "Requests", url: "https://github.com/psf/requests.git" },
    { name: "Httpie", url: "https://github.com/httpie/cli.git" },
  ];
  return (
    <div className="empty-state">
      <div className="feature-grid">
        <div className="feature-card">
          <Network size={20} className="feature-icon" />
          <h4>AST-aware chunking</h4>
          <p>Parses real function/class boundaries with tree-sitter — not naive text splitting.</p>
        </div>
        <div className="feature-card">
          <GitBranch size={20} className="feature-icon" />
          <h4>Graph-aware retrieval</h4>
          <p>Follows function calls across files, not just top-k similarity.</p>
        </div>
        <div className="feature-card">
          <Sparkles size={20} className="feature-icon" />
          <h4>Self-checking answers</h4>
          <p>Every answer is scored for faithfulness and citation accuracy.</p>
        </div>
      </div>
      <p className="try-label">Try it on a real repo:</p>
      <div className="example-chips">
        {examples.map((ex) => (
          <button className="chip" key={ex.name} onClick={() => onPick(ex.url)}>{ex.name}</button>
        ))}
      </div>
    </div>
  );
}

function Workspace() {
  const [repoUrl, setRepoUrl] = useState("https://github.com/pallets/flask.git");
  const [question, setQuestion] = useState("");
  const [indexed, setIndexed] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [indexStats, setIndexStats] = useState(null);
  const [querying, setQuerying] = useState(false);
  const [history, setHistory] = useState([]);
  const [compareMode, setCompareMode] = useState(false);
  const [error, setError] = useState("");
  const [indexStage, setIndexStage] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history]);

  const handleIndex = async () => {
    setIndexing(true);
    const stages = ["Cloning repository...", "Parsing AST (functions, classes, methods)...", "Building call graph...", "Embedding chunks..."];
    let stageIdx = 0;
    setIndexStage(stages[0]);
    const stageTimer = setInterval(() => {
      stageIdx = Math.min(stageIdx + 1, stages.length - 1);
      setIndexStage(stages[stageIdx]);
    }, 4000);
    setError("");
    setHistory([]);
    try {
      const res = await axios.post(`${API_BASE}/index`, { repo_url: repoUrl });
      setIndexed(true);
      setIndexStats(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to index repo");
    } finally {
      clearInterval(stageTimer);
      setIndexing(false);
      setIndexStage("");
    }
  };

  const handleAsk = async () => {
    if (!question.trim()) return;
    const q = question;
    setQuestion("");
    setQuerying(true);
    setError("");
    try {
      if (compareMode) {
        const res = await axios.post(`${API_BASE}/query_compare`, { repo_url: repoUrl, question: q });
        setHistory((h) => [...h, { question: q, compare: res.data }]);
      } else {
        const res = await axios.post(`${API_BASE}/query`, { repo_url: repoUrl, question: q });
        setHistory((h) => [...h, { question: q, ...res.data }]);
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to get answer");
    } finally {
      setQuerying(false);
    }
  };

  return (
    <div className="app">

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
        {indexing && <div className="index-stage"><Loader2 size={13} className="spin" /> {indexStage}</div>}
        {indexed && indexStats && (
          <div className="index-stats">
            <div className="status-ok"><CheckCircle2 size={14} /> Ready for questions</div>
            <div className="stat-row">
              <div className="stat-box"><span className="stat-num">{indexStats.file_count}</span><span className="stat-label">files</span></div>
              <div className="stat-box"><span className="stat-num">{indexStats.chunk_count}</span><span className="stat-label">functions/classes</span></div>
              <div className="stat-box"><span className="stat-num">{indexStats.graph_edges}</span><span className="stat-label">call-graph edges</span></div>
              <div className="stat-box">
                <span className="stat-num">{Object.keys(indexStats.languages || {}).length}</span>
                <span className="stat-label">{Object.keys(indexStats.languages || {}).join(", ")}</span>
              </div>
            </div>
          </div>
        )}
        {indexed && indexStats && (
          <div className="index-stats">
            <div className="status-ok"><CheckCircle2 size={14} /> Ready for questions</div>
            <div className="stat-row">
              <div className="stat-box"><span className="stat-num">{indexStats.file_count}</span><span className="stat-label">files</span></div>
              <div className="stat-box"><span className="stat-num">{indexStats.chunk_count}</span><span className="stat-label">functions/classes</span></div>
              <div className="stat-box"><span className="stat-num">{indexStats.graph_edges}</span><span className="stat-label">call-graph edges</span></div>
              <div className="stat-box">
                <span className="stat-num">{Object.keys(indexStats.languages || {}).length}</span>
                <span className="stat-label">{Object.keys(indexStats.languages || {}).join(", ")}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {error && <div className="error">{error}</div>}
      {!indexed && history.length === 0 && <EmptyState onPick={(url) => setRepoUrl(url)} />}

      <div className="chat-history">
        {history.map((item, i) => item.compare ? <CompareCard item={item} key={i} /> : <AnswerCard item={item} key={i} />)}
        <div ref={bottomRef} />
      </div>

      <div className="panel ask-panel">
        <label className="switch-row">
          <span className="switch">
            <input type="checkbox" checked={compareMode} onChange={(e) => setCompareMode(e.target.checked)} />
            <span className="switch-track"><span className="switch-thumb" /></span>
          </span>
          <span className="switch-text">Compare agentic vs. baseline RAG</span>
        </label>
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

export default Workspace;
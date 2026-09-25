import { Link, useLocation } from "react-router-dom";
import { GitBranch } from "lucide-react";

export default function Navbar() {
  const { pathname } = useLocation();
  return (
    <nav className="navbar">
      <Link to="/" className="nav-brand">
        <GitBranch size={18} /> Agentic Codebase RAG
      </Link>
      <div className="nav-links">
        <Link to="/" className={pathname === "/" ? "active" : ""}>Home</Link>
        <Link to="/how-it-works" className={pathname === "/how-it-works" ? "active" : ""}>How it works</Link>
        <Link to="/app" className={pathname === "/app" ? "active" : ""}>Launch App</Link>
        <a href="https://github.com" target="_blank" rel="noreferrer" className="nav-github">GitHub</a>
      </div>
    </nav>
  );
}
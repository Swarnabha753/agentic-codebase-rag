import { BrowserRouter, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Landing from "./pages/Landing";
import HowItWorks from "./pages/HowItWorks";
import Workspace from "./pages/Workspace";
import "./App.css";

function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/how-it-works" element={<HowItWorks />} />
        <Route path="/app" element={<div className="app"><Workspace /></div>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
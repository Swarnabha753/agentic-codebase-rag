import { BrowserRouter, Routes, Route } from "react-router-dom";
import Navbar from "./Components/Navbar";
import Landing from "./Pages/Landing";
import HowItWorks from "./Pages/HowItWorks";
import Workspace from "./Pages/Workspace";
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
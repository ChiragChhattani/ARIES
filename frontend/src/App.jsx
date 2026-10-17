import { BrowserRouter as Router, Routes, Route, Link, useLocation } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import LiveInterview from "./pages/LiveInterview";
import ReportView from "./pages/ReportView";

function NavigationBar() {
  const location = useLocation();
  const isDashboard = location.pathname === "/";

  return (
    <header className="sticky top-0 z-40 bg-[#0B0F19]/80 backdrop-blur-xl border-b border-slate-800/80 px-6 py-3.5 shadow-lg shadow-black/20">
      <div className="max-w-6xl mx-auto flex justify-between items-center">
        <Link to="/" className="flex items-center space-x-3 group">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-violet-600 via-indigo-500 to-cyan-400 p-[1px] shadow-md shadow-violet-500/20 group-hover:shadow-violet-500/40 transition-shadow">
            <div className="w-full h-full bg-[#0B0F19] rounded-[7px] flex items-center justify-center font-black text-transparent bg-clip-text bg-gradient-to-tr from-violet-400 to-cyan-300 text-sm">
              A
            </div>
          </div>
          <div>
            <span className="text-xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-300 bg-clip-text text-transparent">
              ARIES
            </span>
            <span className="hidden sm:inline-block text-xs font-medium text-slate-400 ml-2.5 px-2 py-0.5 rounded-full bg-slate-800/60 border border-slate-700/50">
              AI Interview Platform
            </span>
          </div>
        </Link>
        <nav className="flex items-center space-x-3">
          <Link
            to="/"
            className={`px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all ${
              isDashboard
                ? "bg-violet-500/10 text-violet-300 border border-violet-500/30 shadow-sm"
                : "text-slate-400 hover:text-white hover:bg-slate-800/50"
            }`}
          >
            Dashboard
          </Link>
          <div className="h-4 w-[1px] bg-slate-800 hidden sm:block"></div>
          <span className="hidden sm:flex items-center gap-1.5 text-xs text-slate-400 bg-slate-900/60 px-2.5 py-1 rounded-md border border-slate-800">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            System Live
          </span>
        </nav>
      </div>
    </header>
  );
}

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-[#080B11] text-slate-100 flex flex-col relative overflow-x-hidden">
        {/* Subtle background ambient glow gradients */}
        <div className="fixed top-0 left-1/4 w-96 h-96 bg-violet-600/10 rounded-full blur-3xl pointer-events-none -z-10"></div>
        <div className="fixed bottom-0 right-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none -z-10"></div>

        <NavigationBar />

        {/* Main Content Area */}
        <main className="flex-1 w-full max-w-6xl mx-auto p-4 sm:p-6 md:p-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/interview/:id" element={<LiveInterview />} />
            <Route path="/report/:id" element={<ReportView />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;

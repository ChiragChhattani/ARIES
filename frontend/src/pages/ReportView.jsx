import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getInterview } from "../services/api";

export default function ReportView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [session, setSession] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await getInterview(id);
        setSession(data);
      } catch (e) {
        console.error(e);
      }
    }
    load();
  }, [id]);

  if (!session) {
    return (
      <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-violet-500 border-t-transparent animate-spin mb-3"></div>
        <p className="text-sm">Loading comprehensive evaluation report...</p>
      </div>
    );
  }
  
  if (session.status !== "REPORT_READY" || !session.evaluation_report) {
    return (
      <div className="p-16 text-center max-w-md mx-auto bg-[#0E131F] border border-slate-800 rounded-2xl">
        <h2 className="text-xl font-bold text-white mb-2">Report Not Ready</h2>
        <p className="text-slate-400 text-xs mb-6">
          The evaluation report for this interview session has not been generated yet.
        </p>
        <button 
          onClick={() => navigate(`/interview/${id}`)} 
          className="bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white px-5 py-2.5 rounded-xl font-semibold text-xs transition"
        >
          Return to Interview Room
        </button>
      </div>
    );
  }

  const report = {
    ...session.evaluation_report,
    proctoring_events: session.proctoring_events || [],
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto pb-12 animate-fade-in">
      {/* Header */}
      <div className="bg-[#0E131F] p-8 rounded-2xl shadow-xl border border-slate-800 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-80 bg-violet-600/10 rounded-full blur-3xl pointer-events-none"></div>
        <div className="flex justify-between items-start flex-wrap gap-6 relative z-10">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-violet-400 bg-violet-950/40 border border-violet-800/40 px-2.5 py-0.5 rounded-full">
                Assessment Complete
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              {session.job_title || (session.job_description && session.job_description.title) || "Candidate Evaluation"}
            </h1>
            <div className="flex items-center gap-2 mt-3 flex-wrap">
              {session.job_description?.field && (
                <span className="bg-violet-500/15 text-violet-300 border border-violet-500/30 text-xs px-2.5 py-1 rounded-md font-medium capitalize">
                  {session.job_description.field.replace(/_/g, " ")}
                </span>
              )}
              {session.job_description?.experience_level && (
                <span className="bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 text-xs px-2.5 py-1 rounded-md font-medium capitalize">
                  Level: {session.job_description.experience_level}
                </span>
              )}
              {session.job_description?.difficulty && (
                <span className="bg-slate-800 text-slate-300 border border-slate-700 text-xs px-2.5 py-1 rounded-md font-medium capitalize">
                  {session.job_description.difficulty} Difficulty
                </span>
              )}
            </div>
          </div>
          
          <div className="flex flex-col sm:items-end">
            <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1">Session ID</span>
            <span className="font-mono text-xs bg-[#080B11] border border-slate-800 text-slate-300 px-3 py-1.5 rounded-lg">
              {id.split("-")[0]}
            </span>
            <span className="text-[11px] text-slate-400 mt-2 font-mono">
              Evaluated on {new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
            </span>
          </div>
        </div>
      </div>

      {/* Competencies */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <span>Competency Rubric Scores</span>
            <span className="text-xs font-mono bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full border border-slate-700/60">
              {report.competency_evaluations?.length || 0}
            </span>
          </h2>
          <span className="text-xs text-slate-400">Scale: 1 (Poor) to 5 (Exemplary)</span>
        </div>

        <div className="grid gap-4">
          {report.competency_evaluations.map((comp, idx) => (
            <div key={idx} className="bg-[#0E131F] p-6 rounded-2xl shadow-xl border border-slate-800/90 hover:border-slate-700 transition">
              <div className="flex justify-between items-center mb-3">
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <span className="text-violet-400 font-mono text-xs">#{idx + 1}</span>
                  <span>{comp.competency_name}</span>
                </h3>
                <div className="flex items-center space-x-2">
                  <span className="text-xs text-slate-400 uppercase tracking-wider font-medium">Score</span>
                  <span className={`font-bold flex items-center justify-center rounded-xl px-3 py-1 ${
                    typeof comp.score === 'string' || comp.score === 'Not Assessed'
                      ? 'bg-slate-800 text-slate-300 border border-slate-700 text-xs font-semibold'
                      : comp.score >= 4
                      ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/40 text-base min-w-[2.5rem] h-9'
                      : comp.score >= 3
                      ? 'bg-amber-500/15 text-amber-300 border border-amber-500/40 text-base min-w-[2.5rem] h-9'
                      : 'bg-rose-500/15 text-rose-300 border border-rose-500/40 text-base min-w-[2.5rem] h-9'
                  }`}>
                    {comp.score === "Not Assessed" ? "Not Assessed" : comp.score}
                  </span>
                </div>
              </div>
              
              <p className="text-slate-300 leading-relaxed text-sm mb-4">{comp.rationale}</p>
              
              <div className="bg-[#080B11] p-4 rounded-xl border border-slate-800/90 mb-3">
                <div className="text-[11px] font-bold text-cyan-400 tracking-wider uppercase mb-2">Evidence Excerpt from Transcript</div>
                {comp.evidence_excerpts && comp.evidence_excerpts.length > 0 ? (
                  <ul className="list-disc list-inside space-y-1.5 text-xs text-slate-300">
                    {comp.evidence_excerpts.map((ev, i) => (
                      <li key={i} className="leading-relaxed">
                        <span className="text-slate-200 italic font-mono">"{ev}"</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-slate-400 italic">No direct technical evidence provided in candidate answers.</p>
                )}
              </div>
              
              {comp.missing_evidence && comp.missing_evidence !== "None" && (
                <div className="text-xs text-amber-300 bg-amber-950/20 p-3.5 rounded-xl border border-amber-900/40 flex items-start gap-2">
                  <span className="font-bold text-amber-400 uppercase tracking-wider text-[10px] whitespace-nowrap mt-0.5">Missing Evidence:</span>
                  <span>{comp.missing_evidence}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Summary (Strengths & Improvements) */}
      <div className="grid md:grid-cols-2 gap-5">
        <div className="bg-[#0E131F] p-6 rounded-2xl border border-emerald-900/30 shadow-xl relative overflow-hidden">
          <div className="flex items-center gap-2 mb-4">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
            <h3 className="text-emerald-400 font-bold text-base">Demonstrated Strengths</h3>
          </div>
          {report.strengths && report.strengths.length > 0 ? (
            <ul className="space-y-2.5">
              {report.strengths.map((s, i) => (
                <li key={i} className="flex items-start text-slate-300 text-xs leading-relaxed">
                  <span className="mr-2 text-emerald-400 font-bold">•</span> 
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-emerald-300/70 italic leading-relaxed">
              No technical strengths demonstrated in the transcript due to brief responses.
            </p>
          )}
        </div>
        
        <div className="bg-[#0E131F] p-6 rounded-2xl border border-amber-900/30 shadow-xl relative overflow-hidden">
          <div className="flex items-center gap-2 mb-4">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400"></span>
            <h3 className="text-amber-400 font-bold text-base">Areas for Improvement</h3>
          </div>
          {report.areas_for_improvement && report.areas_for_improvement.length > 0 ? (
            <ul className="space-y-2.5">
              {report.areas_for_improvement.map((a, i) => (
                <li key={i} className="flex items-start text-slate-300 text-xs leading-relaxed">
                  <span className="mr-2 text-amber-400 font-bold">•</span> 
                  <span>{a}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-amber-300/70 italic leading-relaxed">
              Candidate provided brief or affirmative answers; encourage providing detailed technical examples and structured problem-solving walkthroughs.
            </p>
          )}
        </div>
      </div>

      {/* Human Reviewer Notes */}
      <div className="bg-[#0E131F] p-6 rounded-2xl border border-violet-900/30 shadow-xl">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-base">🎯</span>
          <h3 className="text-violet-300 font-bold text-base">Recommended Follow-Ups for Human Interviewer</h3>
        </div>
        <p className="text-slate-400 mb-4 text-xs">
          Specific probing questions for the hiring manager or technical lead to explore in the subsequent round:
        </p>
        {report.questions_for_human_reviewer && report.questions_for_human_reviewer.length > 0 ? (
          <ul className="space-y-2.5">
            {report.questions_for_human_reviewer.map((q, i) => (
              <li key={i} className="flex items-start text-slate-200 text-xs leading-relaxed bg-[#080B11] p-3 rounded-xl border border-slate-800">
                <span className="mr-2 text-violet-400 font-bold">?</span> 
                <span>{q}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-slate-400 italic">
            Conduct a structured follow-up session asking the candidate to walk through specific projects and code samples for each unassessed competency.
          </p>
        )}
      </div>
      
      {/* Proctoring Log (for human reviewer) */}
      {report.proctoring_events?.length > 0 && (
        <div className="bg-[#0E131F] p-6 rounded-2xl border border-slate-800 shadow-xl mb-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-white font-bold text-base flex items-center gap-2">
              <span>🛡️ Automated Proctoring Event Log</span>
              <span className="text-xs font-mono bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full border border-slate-700/60">
                {report.proctoring_events.length}
              </span>
            </h3>
            <span className="text-[11px] text-amber-400 font-medium">Informational only — No auto-rejection</span>
          </div>
          <p className="text-slate-400 text-xs mb-4">
            The following events were captured during the candidate's interview session for human review:
          </p>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {report.proctoring_events.map((ev, i) => (
              <div key={i} className="flex items-start text-xs space-x-3 bg-[#080B11] p-2.5 rounded-xl border border-slate-800/80">
                <span className="font-mono text-slate-500 text-[11px] whitespace-nowrap mt-0.5">
                  {new Date(ev.timestamp).toLocaleTimeString()}
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-semibold whitespace-nowrap ${
                  ev.event_type === "tab_switch" ? "bg-orange-950/40 text-orange-300 border border-orange-800/40" :
                  ev.event_type === "window_blur" ? "bg-amber-950/40 text-amber-300 border border-amber-800/40" :
                  ev.event_type === "copy_paste_attempt" ? "bg-purple-950/40 text-purple-300 border border-purple-800/40" :
                  "bg-rose-950/40 text-rose-300 border border-rose-800/40"
                }`}>
                  {ev.event_type.replace(/_/g, " ")}
                </span>
                {ev.details && <span className="text-slate-400 leading-relaxed">{ev.details}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="text-center py-6 text-xs text-slate-400">
        AI-generated evaluation report intended to support human decision making. Do not use as a sole hiring criterion.
      </div>
    </div>
  );
}

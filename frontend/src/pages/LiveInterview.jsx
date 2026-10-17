import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getInterview, startInterview, evaluateInterview, logProctoringEvent } from "../services/api";
import { InterviewSocket } from "../services/socket";

// ─────────────────────────────────────────────────────────────────────────────
// Error mapper
// ─────────────────────────────────────────────────────────────────────────────
function mapErrorToMessage(err) {
  if (!err) return null;
  if (!err.status) return { type: "error", text: "Unable to connect to the interview server. Please check that the backend is running." };
  switch (err.code) {
    case "AI_NOT_CONFIGURED": return { type: "error", text: "The AI service is not configured. Please ask the administrator to set up the API key on the server." };
    case "AI_TIMEOUT": return { type: "warning", text: "The AI is taking too long to respond. Please try again." };
    case "AI_RATE_LIMIT": return { type: "warning", text: "Too many requests to the AI service. Please wait a moment and try again." };
    case "SESSION_NOT_FOUND": return { type: "error", text: "This interview session is invalid or has expired." };
    case "INVALID_STATE": return { type: "warning", text: err.message || "This action cannot be performed in the current interview state." };
    default: return { type: "error", text: "The interview could not be started. Please refresh and try again." };
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Toast component for non-blocking warnings (Dark Theme)
// ─────────────────────────────────────────────────────────────────────────────
function Toast({ message, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 5000);
    return () => clearTimeout(t);
  }, [onClose]);
  return (
    <div className="fixed top-5 right-5 z-50 max-w-sm bg-[#0E131F]/95 backdrop-blur-md border border-amber-500/40 text-amber-200 px-4 py-3 rounded-xl shadow-2xl shadow-black/80 flex items-start space-x-3 animate-fade-in">
      <span className="text-amber-400 font-bold text-lg">⚠</span>
      <span className="text-xs flex-1 leading-relaxed text-amber-200">{message}</span>
      <button onClick={onClose} className="text-amber-400 hover:text-amber-300 font-bold text-base leading-none">×</button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Webcam permission screen shown before interview starts (Dark Theme)
// ─────────────────────────────────────────────────────────────────────────────
function CameraSetup({ onReady, onSkip }) {
  const videoRef = useRef(null);
  const [status, setStatus] = useState("idle"); // idle | requesting | granted | denied
  const streamRef = useRef(null);

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => {
          try { t.stop(); } catch {}
        });
        streamRef.current = null;
      }
    };
  }, []);

  async function requestCamera() {
    setStatus("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      setStatus("granted");
    } catch {
      setStatus("denied");
    }
  }

  function proceed() {
    const s = streamRef.current;
    streamRef.current = null; // Transfer ownership to parent without stopping tracks on unmount
    onReady(s);
  }

  function handleSkip() {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => {
        try { t.stop(); } catch {}
      });
      streamRef.current = null;
    }
    onSkip();
  }

  return (
    <div className="h-full flex flex-col items-center justify-center space-y-6 px-6 py-12">
      <div className="bg-[#0E131F] border border-slate-800 rounded-2xl p-6 max-w-lg text-sm text-slate-300 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-32 h-32 bg-violet-600/10 rounded-full blur-2xl pointer-events-none"></div>
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xl">📷</span>
          <h3 className="font-bold text-base text-white">Automated Proctoring Notice</h3>
        </div>
        <p className="text-slate-400 leading-relaxed">
          ARIES uses automated proctoring signals to ensure fair assessment standards for all candidates:
        </p>
        <ul className="list-disc list-inside mt-3 space-y-1.5 text-slate-300 text-xs">
          <li>Camera presence is checked periodically using lightweight on-device detection.</li>
          <li>Tab switching, window blur, and copy-paste shortcuts are logged.</li>
          <li>All proctoring flags are strictly informational for human reviewers — <strong className="text-white">candidates are never auto-rejected</strong>.</li>
        </ul>
      </div>

      {status !== "granted" && (
        <button 
          onClick={requestCamera} 
          disabled={status === "requesting"}
          className="bg-gradient-to-r from-violet-600 via-indigo-600 to-cyan-600 hover:from-violet-500 hover:to-cyan-500 text-white px-7 py-3 rounded-xl font-semibold shadow-lg shadow-violet-600/30 disabled:opacity-50 transition-all flex items-center gap-2"
        >
          <span>{status === "requesting" ? "Requesting Camera Access..." : "Enable Camera & Continue"}</span>
        </button>
      )}

      {status === "denied" && (
        <div className="text-rose-400 text-xs bg-rose-950/30 border border-rose-900/50 px-4 py-2.5 rounded-xl">
          Camera access was declined. You can still proceed without camera proctoring.
        </div>
      )}

      {status === "granted" && (
        <div className="space-y-4 flex flex-col items-center animate-fade-in">
          <div className="relative rounded-xl overflow-hidden border-2 border-emerald-500/60 shadow-xl shadow-emerald-950/30">
            <video ref={videoRef} autoPlay muted playsInline className="w-56 h-40 rounded-xl object-cover" />
            <div className="absolute bottom-2 left-2 bg-emerald-500/20 backdrop-blur-md border border-emerald-500/40 text-emerald-300 text-[11px] font-semibold px-2 py-0.5 rounded-full flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>Camera Stream Ready</span>
            </div>
          </div>
          <button 
            onClick={proceed} 
            className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white px-8 py-3 rounded-xl font-semibold shadow-lg shadow-emerald-600/30 transition-all"
          >
            Enter Interview Room
          </button>
        </div>
      )}

      <button onClick={handleSkip} className="text-xs text-slate-500 hover:text-slate-300 underline transition">
        Skip camera setup and proceed
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main LiveInterview component (Dark SaaS Redesign)
// ─────────────────────────────────────────────────────────────────────────────
export default function LiveInterview() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [session, setSession] = useState(null);
  const [transcript, setTranscript] = useState([]);
  const [input, setInput] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [socket, setSocket] = useState(null);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);
  const [proctoringLog, setProctoringLog] = useState([]);
  const [showLog, setShowLog] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraStream, setCameraStream] = useState(null);
  const [cameraStatus, setCameraStatus] = useState("initializing"); // initializing | active | no_face | multiple_faces | unavailable | disconnected
  const [cameraMinimized, setCameraMinimized] = useState(false);
  const [faceApiLoaded, setFaceApiLoaded] = useState(false);

  const bottomRef = useRef(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const faceCheckRef = useRef(null);
  const socketRef = useRef(null);
  const sessionIdRef = useRef(id);
  sessionIdRef.current = id;
  const lastCopyPasteLogRef = useRef(0);

  // ── Record a proctoring event locally and send to backend ────────────────
  const recordEvent = useCallback(async (eventType, details = "") => {
    const entry = { event_type: eventType, timestamp: new Date().toISOString(), details };
    setProctoringLog(prev => [...prev, entry]);
    try {
      await logProctoringEvent(sessionIdRef.current, eventType, details);
    } catch {
      // fire-and-forget; don't let logging crash the interview
    }
  }, []);

  // ── Load face-api.js models lazily (only when camera is active) ──────────
  useEffect(() => {
    if (!cameraStream) return;
    let cancelled = false;
    async function loadFaceApi() {
      try {
        const faceapi = await import("@vladmandic/face-api");
        await faceapi.nets.tinyFaceDetector.loadFromUri("/models");
        if (!cancelled) setFaceApiLoaded(true);
      } catch (e) {
        console.warn("face-api models could not be loaded:", e);
        if (!cancelled) setCameraStatus("unavailable");
      }
    }
    loadFaceApi();
    return () => { cancelled = true; };
  }, [cameraStream]);

  // ── Attach camera stream to video element and track stream health ────────
  useEffect(() => {
    if (!cameraStream) return;

    if (videoRef.current) {
      videoRef.current.srcObject = cameraStream;
      videoRef.current.play().catch(() => {});
    }

    const videoTrack = cameraStream.getVideoTracks()[0];
    if (videoTrack) {
      const handleEnded = () => {
        setCameraStatus("disconnected");
        recordEvent("camera_disconnected", "Camera stream ended unexpectedly");
      };
      const handleMute = () => {
        setCameraStatus("unavailable");
      };
      const handleUnmute = () => {
        setCameraStatus("active");
      };

      videoTrack.addEventListener("ended", handleEnded);
      videoTrack.addEventListener("mute", handleMute);
      videoTrack.addEventListener("unmute", handleUnmute);

      return () => {
        videoTrack.removeEventListener("ended", handleEnded);
        videoTrack.removeEventListener("mute", handleMute);
        videoTrack.removeEventListener("unmute", handleUnmute);
      };
    }
  }, [cameraStream, recordEvent]);

  // ── Stop webcam tracks and clean up intervals/timers ─────────────────────
  const stopCamera = useCallback(() => {
    if (cameraStream) {
      cameraStream.getTracks().forEach(track => {
        try { track.stop(); } catch {}
      });
      setCameraStream(null);
    }
    if (faceCheckRef.current) {
      clearInterval(faceCheckRef.current);
      faceCheckRef.current = null;
    }
    setCameraStatus("inactive");
  }, [cameraStream]);

  // Clean up camera hardware when interview completes, terminates, or transitions away
  useEffect(() => {
    if (session?.status && session.status !== "IN_PROGRESS" && session.status !== "CONFIGURED" && session.status !== "CREATED") {
      stopCamera();
    }
  }, [session?.status, stopCamera]);

  // Clean up on component unmount
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, [stopCamera]);

  // ── Periodic face detection with frame-readiness check & debounce ─────────
  useEffect(() => {
    if (!cameraStream || !faceApiLoaded || session?.status !== "IN_PROGRESS") return;

    let consecutiveMisses = 0;
    let consecutiveMultiples = 0;
    let lastMissLogTime = 0;
    let lastMultipleLogTime = 0;
    const COOLDOWN_MS = 30000;
    let isChecking = false;

    async function checkFaces() {
      if (isChecking) return;
      const video = videoRef.current;
      if (!video) return;

      if (video.paused || video.ended) {
        try { await video.play(); } catch {}
        return;
      }
      if (video.readyState < 2 || video.videoWidth === 0 || video.videoHeight === 0) {
        return;
      }

      isChecking = true;
      try {
        const faceapi = (await import("@vladmandic/face-api")).default || await import("@vladmandic/face-api");
        const detections = await faceapi.detectAllFaces(
          video,
          new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.4 })
        );

        const now = Date.now();
        if (detections.length === 0) {
          consecutiveMisses++;
          consecutiveMultiples = 0;
          setCameraStatus("no_face");

          if (consecutiveMisses >= 3 && now - lastMissLogTime > COOLDOWN_MS) {
            lastMissLogTime = now;
            setToast("⚠ Face not detected. Please make sure your camera is centered and well lit.");
            recordEvent("face_missing", "0 faces detected across 3 consecutive checks (~21s)");
          }
        } else if (detections.length > 1) {
          consecutiveMultiples++;
          consecutiveMisses = 0;
          setCameraStatus("multiple_faces");

          if (consecutiveMultiples >= 2 && now - lastMultipleLogTime > COOLDOWN_MS) {
            lastMultipleLogTime = now;
            setToast("⚠ Multiple faces detected in camera frame.");
            recordEvent("multiple_faces", `${detections.length} faces detected across multiple checks`);
          }
        } else {
          consecutiveMisses = 0;
          consecutiveMultiples = 0;
          setCameraStatus("active");
        }
      } catch (err) {
        console.warn("Face detection check error:", err);
      } finally {
        isChecking = false;
      }
    }

    faceCheckRef.current = setInterval(checkFaces, 7000);
    const warmupTimeout = setTimeout(checkFaces, 2000);

    return () => {
      clearInterval(faceCheckRef.current);
      clearTimeout(warmupTimeout);
    };
  }, [cameraStream, faceApiLoaded, recordEvent, session?.status]);

  // ── Tab switch & window blur detection with deduplication & debouncing ───
  useEffect(() => {
    if (session?.status !== "IN_PROGRESS") return;
    let blurTimeout = null;
    let lastTabSwitchTime = 0;
    let lastBlurTime = 0;
    const COOLDOWN_MS = 8000;

    function handleVisibility() {
      const now = Date.now();
      if (document.hidden) {
        if (blurTimeout) {
          clearTimeout(blurTimeout);
          blurTimeout = null;
        }
        if (now - lastTabSwitchTime > COOLDOWN_MS) {
          lastTabSwitchTime = now;
          setToast("⚠ Please keep the interview tab active.");
          recordEvent(
            "tab_switch",
            "document.visibilityState became hidden (tab switched or browser minimized)"
          );
        }
      }
    }

    function handleBlur() {
      if (blurTimeout) clearTimeout(blurTimeout);
      blurTimeout = setTimeout(() => {
        const now = Date.now();
        if (document.hidden) return;

        if (now - lastBlurTime > COOLDOWN_MS) {
          lastBlurTime = now;
          setToast("⚠ Window lost focus. Please click back into the interview.");
          recordEvent(
            "window_blur",
            "Window lost focus while interview page remained visible"
          );
        }
      }, 350);
    }

    function handleFocus() {
      if (blurTimeout) {
        clearTimeout(blurTimeout);
        blurTimeout = null;
      }
    }

    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("blur", handleBlur);
    window.addEventListener("focus", handleFocus);

    return () => {
      if (blurTimeout) clearTimeout(blurTimeout);
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("blur", handleBlur);
      window.removeEventListener("focus", handleFocus);
    };
  }, [recordEvent, session?.status]);

  // ── Load session and connect WebSocket ───────────────────────────────────
  useEffect(() => {
    let ws = null;
    async function init() {
      try {
        const data = await getInterview(id);
        setSession(data);
        setTranscript(data.transcript || []);
        ws = new InterviewSocket(id, (eventType, payload) => {
          if (eventType === "question_generated") {
            setTranscript(prev => [...prev, { speaker: "interviewer", content: payload.question }]);
            setIsProcessing(false);
          } else if (eventType === "interview_completed") {
            setTranscript(prev => [...prev, { speaker: "interviewer", content: payload.conclusion }]);
            setIsProcessing(false);
            setSession(prev => ({ ...prev, status: "COMPLETED" }));
          } else if (eventType === "processing_started") {
            setIsProcessing(true);
          } else if (eventType === "status_updated") {
            setSession(prev => ({ ...prev, status: payload.status }));
            if (payload.status === "REPORT_READY") navigate(`/report/${id}`);
          }
        });
        ws.connect();
        socketRef.current = ws;
        setSocket(ws);
      } catch (e) {
        console.error("Failed to load session", e);
      }
    }
    init();
    return () => { if (ws) ws.disconnect(); };
  }, [id, navigate]);

  // ── Auto-scroll ──────────────────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript, isProcessing]);

  // ── Copy-paste & context-menu blocking (with spam throttle) ─────────────
  function blockCopyPaste(e) {
    e.preventDefault();
    setToast("⚠ Copy/paste is disabled during the interview.");
    const now = Date.now();
    if (now - lastCopyPasteLogRef.current > 4000) {
      lastCopyPasteLogRef.current = now;
      recordEvent("copy_paste_attempt", `${e.type} event blocked on answer field`);
    }
  }

  // ── Handlers ─────────────────────────────────────────────────────────────
  async function handleCameraReady(stream) {
    setCameraStream(stream);
    setCameraReady(true);
    await doStartInterview();
  }

  async function handleSkipCamera() {
    setCameraReady(true);
    await doStartInterview();
  }

  async function doStartInterview() {
    setIsProcessing(true);
    setError(null);
    try {
      await startInterview(id);
    } catch (e) {
      setError(mapErrorToMessage(e));
      setIsProcessing(false);
    }
  }

  async function handleEvaluate() {
    setIsProcessing(true);
    try {
      await evaluateInterview(id);
    } catch {
      alert("Error generating evaluation");
      setIsProcessing(false);
    }
  }

  function submitAnswer(e) {
    e.preventDefault();
    if (!input.trim() || isProcessing) return;
    setTranscript(prev => [...prev, { speaker: "candidate", content: input }]);
    socket.submitAnswer(input);
    setInput("");
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────────────
  if (!session) {
    return (
      <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-violet-500 border-t-transparent animate-spin mb-3"></div>
        <p className="text-sm">Connecting to session room...</p>
      </div>
    );
  }

  const isConfigured = session.status === "CONFIGURED" || session.status === "CREATED";
  const isCompleted = session.status === "COMPLETED";

  return (
    <>
      <canvas ref={canvasRef} style={{ display: "none" }} />

      {/* Toast notifications */}
      {toast && <Toast message={toast} onClose={() => setToast(null)} />}

      <div className="relative flex flex-col h-[85vh] bg-[#0E131F] rounded-2xl shadow-2xl border border-slate-800/90 overflow-hidden">
        {/* Floating Live Camera Preview & Proctoring Status */}
        {cameraStream && (
          <div className="absolute top-20 right-6 z-30 bg-[#0E131F]/95 backdrop-blur-md rounded-xl p-2.5 shadow-2xl border border-slate-700/80 flex flex-col items-center transition-all">
            <div className="flex items-center justify-between w-full mb-1.5 px-0.5 gap-2">
              <div className="flex items-center gap-1.5 text-xs font-semibold">
                <span className={`w-2 h-2 rounded-full ${
                  cameraStatus === "active" ? "bg-emerald-400 shadow-sm shadow-emerald-400" :
                  cameraStatus === "no_face" ? "bg-amber-400 animate-pulse" :
                  cameraStatus === "multiple_faces" ? "bg-purple-400 animate-pulse" :
                  cameraStatus === "initializing" ? "bg-cyan-400 animate-pulse" :
                  "bg-rose-500"
                }`} />
                <span className="text-slate-300 text-[11px] font-medium">
                  {cameraStatus === "active" ? "Camera Active" :
                   cameraStatus === "no_face" ? "No face in frame" :
                   cameraStatus === "multiple_faces" ? "Multiple faces" :
                   cameraStatus === "initializing" ? "Checking video..." :
                   cameraStatus === "disconnected" ? "Camera disconnected" :
                   "Camera unavailable"}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setCameraMinimized(v => !v)}
                className="text-slate-400 hover:text-white text-xs px-1 rounded transition"
                title={cameraMinimized ? "Expand preview" : "Minimize preview"}
              >
                {cameraMinimized ? "▢" : "—"}
              </button>
            </div>
            
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className={`rounded-lg object-cover border border-slate-700/80 transition-all ${
                cameraMinimized ? "w-0 h-0 opacity-0 pointer-events-none" : "w-36 h-28"
              }`}
            />
          </div>
        )}

        {/* Header */}
        <div className="bg-[#0B0F19] px-6 py-4 border-b border-slate-800 flex justify-between items-center">
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h2 className="font-bold text-base text-white">
                {session.job_title || session.job_description?.title || "Technical Interview"}
              </h2>
              {session.job_description?.field && (
                <span className="text-[11px] font-medium bg-violet-500/15 text-violet-300 border border-violet-500/30 px-2 py-0.5 rounded capitalize">
                  {session.job_description.field.replace(/_/g, " ")}
                </span>
              )}
            </div>
            <p className="text-slate-400 text-xs mt-1 font-mono">
              Limit: {session.settings?.max_questions} questions max
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            {proctoringLog.length > 0 && (
              <button
                onClick={() => setShowLog(v => !v)}
                className="text-xs bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 px-2.5 py-1 rounded-lg font-medium transition flex items-center gap-1.5"
                title="Toggle proctoring event log"
              >
                <span>🔍 {proctoringLog.length} event{proctoringLog.length > 1 ? "s" : ""}</span>
              </button>
            )}
            <span className={`text-xs px-3 py-1 rounded-full font-medium tracking-wide uppercase ${
              session.status === 'COMPLETED' ? 'bg-blue-500/15 text-blue-300 border border-blue-500/30' :
              session.status === 'IN_PROGRESS' ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 animate-pulse' :
              'bg-slate-800 text-slate-300 border border-slate-700'
            }`}>
              {session.status.replace("_", " ")}
            </span>
          </div>
        </div>

        {/* Proctoring Log Panel (collapsible) */}
        {showLog && (
          <div className="bg-[#080B11] border-b border-slate-800 px-6 py-3.5 max-h-44 overflow-y-auto">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[11px] font-bold text-amber-400 tracking-wider uppercase">Proctoring Event Timeline</p>
              <span className="text-[10px] text-slate-500">Informational only</span>
            </div>
            {proctoringLog.map((ev, i) => (
              <div key={i} className="text-xs text-slate-300 mb-1 flex items-baseline gap-2">
                <span className="font-mono text-slate-500 text-[11px]">{new Date(ev.timestamp).toLocaleTimeString()}</span>
                <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold ${
                  ev.event_type === "tab_switch" ? "bg-orange-950/40 text-orange-300 border border-orange-800/40" :
                  ev.event_type === "window_blur" ? "bg-amber-950/40 text-amber-300 border border-amber-800/40" :
                  ev.event_type === "copy_paste_attempt" ? "bg-purple-950/40 text-purple-300 border border-purple-800/40" :
                  "bg-rose-950/40 text-rose-300 border border-rose-800/40"
                }`}>
                  {ev.event_type.replace(/_/g, " ")}
                </span>
                {ev.details && <span className="text-slate-400 text-xs">({ev.details})</span>}
              </div>
            ))}
          </div>
        )}

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto p-6 bg-[#080B11] space-y-5">
          {/* Pre-start: camera setup */}
          {isConfigured && !cameraReady && (
            <CameraSetup onReady={handleCameraReady} onSkip={handleSkipCamera} />
          )}

          {/* Pre-start: error display after camera setup */}
          {isConfigured && cameraReady && (
            <div className="h-full flex flex-col items-center justify-center text-slate-400">
              {error && (
                <div className={`mx-4 mb-4 p-4 rounded-xl border flex items-start space-x-3 max-w-md ${
                  error.type === "warning" ? "bg-amber-950/30 border-amber-900/50 text-amber-300" : "bg-rose-950/30 border-rose-900/50 text-rose-300"
                }`}>
                  <div className="flex-1">
                    <p className="font-semibold text-xs tracking-wider uppercase">{error.type === "warning" ? "Warning" : "Error"}</p>
                    <p className="text-sm mt-1">{error.text}</p>
                  </div>
                  <button onClick={() => setError(null)} className="text-slate-400 hover:text-white text-lg leading-none">&times;</button>
                </div>
              )}
              {isProcessing && (
                <div className="flex flex-col items-center gap-3 text-violet-400">
                  <div className="w-8 h-8 rounded-full border-2 border-violet-500 border-t-transparent animate-spin"></div>
                  <p className="text-sm font-medium animate-pulse">Initializing interview session & generating opening question…</p>
                </div>
              )}
            </div>
          )}

          {/* Transcript messages */}
          {transcript.map((msg, i) => (
            <div key={i} className={`flex ${msg.speaker === "candidate" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] rounded-2xl px-5 py-4 ${
                msg.speaker === "candidate"
                  ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-br-sm shadow-xl shadow-violet-950/30"
                  : "bg-[#0E131F] border border-slate-800/90 text-slate-100 rounded-bl-sm shadow-md"
              }`}>
                <div className={`text-xs mb-1.5 font-semibold flex items-center gap-1.5 ${
                  msg.speaker === "candidate" ? "text-violet-200" : "text-cyan-400"
                }`}>
                  {msg.speaker === "candidate" ? "You (Candidate)" : "AI Interviewer"}
                </div>
                <div className="leading-relaxed whitespace-pre-wrap text-sm">{msg.content}</div>
              </div>
            </div>
          ))}

          {/* Typing indicator */}
          {isProcessing && session.status !== "EVALUATING" && session.status !== "CONFIGURED" && session.status !== "CREATED" && (
            <div className="flex justify-start">
              <div className="bg-[#0E131F] border border-slate-800 rounded-2xl rounded-bl-sm px-5 py-3.5 shadow-md flex items-center space-x-2 text-violet-400">
                <span className="w-2 h-2 rounded-full bg-violet-400 animate-bounce"></span>
                <span className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: "0.2s" }}></span>
                <span className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: "0.4s" }}></span>
              </div>
            </div>
          )}

          {/* Post-interview banner */}
          {isCompleted && !isProcessing && (
            <div className="text-center py-8 bg-[#0E131F]/60 border border-slate-800 rounded-2xl max-w-md mx-auto my-4 p-6 shadow-xl">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto mb-3 text-emerald-400 text-lg">
                ✓
              </div>
              <h3 className="text-base font-bold text-white mb-1">Interview Concluded</h3>
              <p className="text-slate-400 text-xs mb-5">
                The interview dialogue is complete. Click below to trigger the multi-agent competency evaluation.
              </p>
              <button 
                onClick={handleEvaluate} 
                className="bg-gradient-to-r from-emerald-600 via-teal-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white px-7 py-3 rounded-xl font-semibold text-sm shadow-lg shadow-emerald-600/30 transition-all"
              >
                Generate Evaluation Report
              </button>
            </div>
          )}

          {session.status === "EVALUATING" && (
            <div className="text-center py-10 text-cyan-400 font-medium flex flex-col items-center gap-3">
              <div className="w-8 h-8 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin"></div>
              <p className="text-sm animate-pulse">Evaluating dialogue transcript against role rubric and scoring competencies…</p>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Answer input (copy/paste/cut/contextmenu blocked) */}
        {session.status === "IN_PROGRESS" && (
          <form onSubmit={submitAnswer} className="p-4 bg-[#0E131F] border-t border-slate-800 flex space-x-3">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onCopy={blockCopyPaste}
              onCut={blockCopyPaste}
              onPaste={blockCopyPaste}
              onContextMenu={e => e.preventDefault()}
              disabled={isProcessing}
              placeholder="Type your answer here…"
              className="flex-1 bg-[#080B11] border border-slate-700/80 rounded-xl px-4 py-3 text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 disabled:opacity-50 transition"
            />
            <button
              type="submit"
              disabled={isProcessing || !input.trim()}
              className="bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white px-7 py-3 rounded-xl font-semibold text-sm shadow-lg shadow-violet-600/30 transition-all disabled:opacity-50"
            >
              Send
            </button>
          </form>
        )}
      </div>
    </>
  );
}

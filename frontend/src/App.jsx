import { useCallback, useEffect, useRef, useState } from "react";

// ─── Config ──────────────────────────────────────────────
const API_BASE = import.meta.env.VITE_API_BASE || "";
const API_TIMEOUT_MS = 120000;

async function api(path, options = {}, timeoutMs = API_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...options.headers },
      signal: controller.signal,
      ...options,
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      const detail = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
      throw new Error(detail || "Erro na requisição");
    }
    return resp;
  } finally {
    clearTimeout(timeoutId);
  }
}

// ─── Document Types ──────────────────────────────────────
const DOC_TYPES = [
  { id: "peticao_inicial", label: "Petição Inicial", icon: "📄" },
  { id: "contestacao", label: "Contestação", icon: "⚔️" },
  { id: "recurso_ordinario", label: "Recurso Ordinário", icon: "📤" },
  { id: "agravo", label: "Agravo de Instrumento", icon: "🔒" },
  { id: "mandado_seguranca", label: "Mandado de Segurança", icon: "🛡️" },
  { id: "reclamacao_trabalhista", label: "Reclamação Trabalhista", icon: "👷" },
  { id: "acordo", label: "Acordo Extrajudicial", icon: "🤝" },
  { id: "contrarrazoes", label: "Contrarrazões", icon: "📋" },
  { id: "embargos", label: "Embargos de Declaração", icon: "❓" },
  { id: "outro", label: "Outro documento", icon: "📝" },
];

function normalizeText(value) {
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function detectDocumentType(message) {
  const normalized = normalizeText(message);
  for (const docType of DOC_TYPES) {
    if (normalized.includes(normalizeText(docType.label))) return docType;
  }
  if (normalized.includes("peticao") || normalized.includes("petição")) return DOC_TYPES[0];
  return null;
}

// ─── Severity & Category colors ──────────────────────────
const SEV = { ALTA: "#ef4444", MEDIA: "#eab308", BAIXA: "#3b82f6" };
const CAT_COLOR = { FUNDAMENTACAO: "#a78bfa", ESTRATEGIA: "#f472b6", PROVAS: "#38bdf8", PEDIDOS: "#34d399", FATOS: "#fb923c" };

// ─── Question Form (modal-style) ─────────────────────────
function QuestionForm({ questions, onSubmit, roundNumber }) {
  const safeQ = Array.isArray(questions) ? questions : [];
  const [answers, setAnswers] = useState({});
  const [customs, setCustoms] = useState({});

  const normalize = (opt) => {
    if (typeof opt === "string") return { id: opt, label: opt };
    if (opt && typeof opt === "object") return { id: opt.id ?? opt.label ?? "opt", label: opt.label ?? opt.text ?? "Opção", desc: opt.desc || "" };
    return { id: String(opt), label: String(opt) };
  };

  const set = (id, val) => setAnswers(prev => ({ ...prev, [id]: val }));
  const answeredCount = Object.keys(answers).filter(k => {
    const v = answers[k];
    return v && (typeof v === "string" ? v.trim() : v.length > 0);
  }).length;

  return (
    <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, padding: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h4 style={{ fontSize: 14, fontWeight: 700, color: "#d4bbff", margin: 0 }}>Perguntas - Rodada {roundNumber}</h4>
        <span style={{ fontSize: 11, color: "rgba(255,255,255,0.4)" }}>{answeredCount}/{safeQ.length} respondidas - campos vazios virarão [placeholders]</span>
      </div>
      {safeQ.map((q) => {
        const opts = Array.isArray(q.options) ? q.options.map(normalize) : [];
        return (
          <div key={q.id} style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 13, color: "rgba(255,255,255,0.7)", display: "block", marginBottom: 6 }}>{q.text}</label>
            {q.type === "choice" && opts.length > 0 ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {opts.map(o => (
                  <button key={o.id} onClick={() => set(q.id, o.id === "other" ? "" : o.label)}
                    style={{ padding: "6px 14px", borderRadius: 20, fontSize: 12, cursor: "pointer", border: answers[q.id] === o.label ? "1px solid #a78bfa" : "1px solid rgba(255,255,255,0.1)", background: answers[q.id] === o.label ? "rgba(167,139,250,0.15)" : "rgba(255,255,255,0.03)", color: answers[q.id] === o.label ? "#d4bbff" : "rgba(255,255,255,0.5)" }}>
                    {o.label}
                  </button>
                ))}
                {answers[q.id] === "" && <input autoFocus placeholder="Especifique..." value={customs[q.id] || ""} onChange={e => { setCustoms(p => ({ ...p, [q.id]: e.target.value })); set(q.id, e.target.value); }} style={{ flex: 1, minWidth: 150, padding: "6px 12px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.1)", background: "rgba(255,255,255,0.03)", color: "#fff", fontSize: 12, outline: "none" }} />}
              </div>
            ) : (
              <textarea value={answers[q.id] || ""} onChange={e => set(q.id, e.target.value)} placeholder="Digite sua resposta..." rows={2} style={{ width: "100%", padding: "8px 12px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)", color: "#fff", fontSize: 12.5, resize: "vertical", outline: "none", fontFamily: "inherit" }} />
            )}
          </div>
        );
      })}
      <button onClick={() => { const final = {}; safeQ.forEach(q => { if (answers[q.id]) final[q.text || q.id] = answers[q.id]; }); if (Object.keys(final).length > 0) onSubmit(final); }}
        disabled={answeredCount < 1}
        style={{ width: "100%", padding: "10px", borderRadius: 8, fontWeight: 700, fontSize: 13, cursor: answeredCount < 1 ? "not-allowed" : "pointer", background: answeredCount >= 1 ? "var(--accent)" : "rgba(255,255,255,0.05)", border: "none", color: answeredCount >= 1 ? "#fff" : "rgba(255,255,255,0.3)" }}>
        Enviar respostas
      </button>
    </div>
  );
}

// ─── Main App ────────────────────────────────────────────
export default function JurisGenApp() {
  const [sessionId, setSessionId] = useState(null);
  const [stage, setStage] = useState("select_type"); // select_type | questions | outline | generating | document
  const [docType, setDocType] = useState("");
  const [questions, setQuestions] = useState([]);
  const [answerRound, setAnswerRound] = useState(1);
  const [allAnswers, setAllAnswers] = useState({});
  const [outline, setOutline] = useState(null);
  const [sections, setSections] = useState([]);
  const [currentSection, setCurrentSection] = useState(-1);
  const [sectionProgress, setSectionProgress] = useState({});
  const [researchLog, setResearchLog] = useState([]);
  const [loading, setLoading] = useState(false);
  const [writingTime, setWritingTime] = useState(0);
  const [input, setInput] = useState("");
  const [chatMessages, setChatMessages] = useState([]);
  const [leftPanelOpen, setLeftPanelOpen] = useState(true);
  const [adversarial, setAdversarial] = useState(null);
  const [advTab, setAdvTab] = useState("doc");
  const [advLoading, setAdvLoading] = useState(false);
  const [etapas, setEtapas] = useState(0);
  const docRef = useRef(null);
  const timerRef = useRef(null);

  // Init session
  useEffect(() => {
    (async () => {
      try {
        const resp = await api("/api/sessions", { method: "POST", body: JSON.stringify({}) });
        const data = await resp.json();
        setSessionId(data.id);
      } catch {}
    })();
  }, []);

  // Writing timer
  useEffect(() => {
    if (stage === "generating") {
      setWritingTime(0);
      timerRef.current = setInterval(() => setWritingTime(t => t + 1), 1000);
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [stage]);

  // Scroll to current section
  useEffect(() => {
    if (currentSection >= 0) {
      const el = document.getElementById(`section-${currentSection}`);
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [currentSection]);

  // ── Handlers ──
  const handleSelectType = async (type, customText = "") => {
    const label = type?.label || customText || docType;
    setDocType(label);
    setLoading(true);
    setEtapas(1);
    try {
      const resp = await api("/api/pipeline/set-type", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, doc_type: label, context: customText || label }),
      });
      const data = await resp.json();
      setQuestions(data.questions || []);
      setStage("questions");
      setEtapas(2);
    } catch (e) {
      setChatMessages(prev => [...prev, { role: "system", text: `Erro: ${e.message}` }]);
    }
    setLoading(false);
  };

  const handleQuestionSubmit = async (roundAnswers) => {
    const merged = { ...allAnswers, ...roundAnswers };
    setAllAnswers(merged);
    setLoading(true);
    setEtapas(3);
    try {
      const resp = await api("/api/pipeline/answer", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, answers: roundAnswers }),
      });
      const data = await resp.json();
      if (data.action === "more_questions") {
        setQuestions(data.questions || []);
        setAnswerRound(r => r + 1);
      } else {
        setOutline(data.outline);
        setStage("outline");
        setEtapas(4);
      }
    } catch (e) {
      setChatMessages(prev => [...prev, { role: "system", text: `Erro: ${e.message}` }]);
    }
    setLoading(false);
  };

  const handleGenerate = async () => {
    setStage("generating");
    setSections([]);
    setResearchLog([]);
    setCurrentSection(-1);
    setEtapas(5);

    try {
      const resp = await fetch(`${API_BASE}/api/pipeline/generate-document/${sessionId}`, { method: "POST" });
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const event = JSON.parse(line);
            if (event.type === "research") {
              setResearchLog(prev => [...prev, event.data]);
              if (event.data.status === "searching") {
                // Mark section as searching
              }
            } else if (event.type === "section") {
              setSections(prev => {
                const next = [...prev, event.data];
                setCurrentSection(next.length - 1);
                setSectionProgress(p => ({ ...p, [event.data.section_title]: "done" }));
                return next;
              });
            } else if (event.type === "done") {
              setEtapas(6);
            }
          } catch {}
        }
      }
      setStage("document");
      setEtapas(7);
    } catch (e) {
      setChatMessages(prev => [...prev, { role: "system", text: `Erro: ${e.message}` }]);
      setStage("outline");
    }
  };

  const handleChat = async () => {
    if (!input.trim() || !sessionId) return;
    const msg = input.trim();
    setInput("");
    setChatMessages(prev => [...prev, { role: "user", text: msg }]);
    try {
      const resp = await api("/api/chat", { method: "POST", body: JSON.stringify({ session_id: sessionId, message: msg }) });
      const data = await resp.json();
      setChatMessages(prev => [...prev, { role: "assistant", text: data.response }]);
    } catch (e) {
      setChatMessages(prev => [...prev, { role: "system", text: e.message }]);
    }
  };

  const handleAdversarial = async () => {
    if (!sessionId || sections.length === 0) return;
    setAdvLoading(true);
    setAdversarial(null);
    setEtapas(8);

    const documentText = sections.filter(s => !s.is_sources).map(s => `${s.section_title}\n\n${s.content}`).join("\n\n");

    try {
      const resp = await fetch(`${API_BASE}/api/pipeline/adversarial-analysis/${sessionId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, document_text: documentText }),
      });
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let cls = null, vulns = [], advDoc = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const ev = JSON.parse(line);
            if (ev.type === "classification") cls = ev.data;
            else if (ev.type === "vulnerabilities") vulns = ev.data.vulnerabilities || [];
            else if (ev.type === "adversarial_document") advDoc = ev.data;
          } catch {}
        }
      }
      setAdversarial({ classification: cls, vulnerabilities: vulns, adversarialDoc: advDoc });
    } catch {}
    setAdvLoading(false);
  };

  const copyDocument = () => {
    const text = sections.filter(s => !s.is_sources).map(s => `${s.section_title}\n\n${s.content}`).join("\n\n" + "─".repeat(50) + "\n\n");
    navigator.clipboard.writeText(text);
  };

  const outlineSections = outline?.sections || [];

  // ── RENDER ──

  // Stage: Select document type
  if (stage === "select_type") {
    return (
      <div style={{ height: "100vh", background: "#0a0a0f", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ maxWidth: 600, width: "100%", padding: 32 }}>
          <h1 style={{ fontSize: 28, fontWeight: 800, color: "#fff", textAlign: "center", marginBottom: 8 }}>JurisGen AI</h1>
          <p style={{ color: "rgba(255,255,255,0.4)", textAlign: "center", fontSize: 14, marginBottom: 32 }}>Gerador inteligente de documentos juridicos</p>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 24 }}>
            {DOC_TYPES.map(dt => (
              <button key={dt.id} onClick={() => handleSelectType(dt)}
                style={{ padding: "16px 12px", background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, cursor: "pointer", textAlign: "center", transition: "all 0.15s" }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(167,139,250,0.4)"; e.currentTarget.style.background = "rgba(167,139,250,0.06)"; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)"; e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}>
                <div style={{ fontSize: 24, marginBottom: 6 }}>{dt.icon}</div>
                <div style={{ fontSize: 12, color: "#fff", fontWeight: 600 }}>{dt.label}</div>
              </button>
            ))}
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <input value={docType} onChange={e => setDocType(e.target.value)} placeholder="Ou descreva o documento desejado..." onKeyDown={e => e.key === "Enter" && docType.trim() && handleSelectType(null, docType)}
              style={{ flex: 1, padding: "12px 16px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)", color: "#fff", fontSize: 13, outline: "none" }} />
            <button onClick={() => docType.trim() && handleSelectType(null, docType)} disabled={!docType.trim() || loading}
              style={{ padding: "12px 20px", borderRadius: 10, background: "var(--accent)", border: "none", color: "#fff", fontWeight: 700, cursor: "pointer", fontSize: 13 }}>
              {loading ? "..." : "Criar"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Stage: Questions
  if (stage === "questions") {
    return (
      <div style={{ height: "100vh", background: "#0a0a0f", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ maxWidth: 640, width: "100%", padding: 32 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
            <span style={{ fontSize: 24 }}>📋</span>
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: "#fff", margin: 0 }}>{docType}</h2>
              <p style={{ fontSize: 12, color: "rgba(255,255,255,0.4)", margin: 0 }}>Responda as perguntas para gerar seu documento</p>
            </div>
          </div>
          {loading ? (
            <div style={{ textAlign: "center", padding: 40, color: "rgba(255,255,255,0.4)" }}>Processando...</div>
          ) : (
            <QuestionForm questions={questions} onSubmit={handleQuestionSubmit} roundNumber={answerRound} />
          )}
        </div>
      </div>
    );
  }

  // Stage: Outline approval
  if (stage === "outline" && outline) {
    const secs = outline.sections || [];
    const args = outline.key_arguments || [];
    const argColors = ["#a78bfa", "#34d399", "#38bdf8", "#f472b6", "#fbbf24", "#fb923c"];
    return (
      <div style={{ height: "100vh", background: "#0a0a0f", display: "flex", alignItems: "center", justifyContent: "center", overflowY: "auto" }}>
        <div style={{ maxWidth: 700, width: "100%", padding: 32 }}>
          <h2 style={{ fontSize: 18, fontWeight: 800, color: "#fff", marginBottom: 4, letterSpacing: 0.3 }}>{outline.title}</h2>
          <p style={{ color: "rgba(255,255,255,0.4)", fontSize: 13, marginBottom: 20, fontStyle: "italic" }}>{outline.subtitle}</p>

          <div style={{ display: "flex", gap: 10, marginBottom: 18 }}>
            <span style={{ background: "rgba(167,139,250,0.08)", color: "#a78bfa", padding: "5px 14px", borderRadius: 20, fontSize: 12, fontWeight: 600, border: "1px solid rgba(167,139,250,0.15)" }}>~{outline.estimated_pages} paginas</span>
            <span style={{ background: "rgba(167,139,250,0.08)", color: "#a78bfa", padding: "5px 14px", borderRadius: 20, fontSize: 12, fontWeight: 600, border: "1px solid rgba(167,139,250,0.15)" }}>{secs.length} secoes</span>
          </div>

          {args.map((a, i) => (
            <div key={i} style={{ padding: "8px 14px", marginBottom: 6, background: `${argColors[i % argColors.length]}08`, border: `1px solid ${argColors[i % argColors.length]}22`, borderLeft: `3px solid ${argColors[i % argColors.length]}`, borderRadius: 6, color: argColors[i % argColors.length], fontSize: 12.5, lineHeight: 1.4 }}>+ {a}</div>
          ))}

          <div style={{ marginTop: 20 }}>
            {secs.map((s, i) => (
              <div key={i} style={{ display: "flex", gap: 12, padding: "12px 0", borderBottom: i < secs.length - 1 ? "1px solid rgba(255,255,255,0.04)" : "none" }}>
                <div style={{ width: 26, height: 26, borderRadius: "50%", background: "var(--accent)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, flexShrink: 0 }}>{i + 1}</div>
                <div>
                  <h5 style={{ fontSize: 13, fontWeight: 700, color: "#fff", margin: "0 0 3px" }}>{s.title}</h5>
                  <p style={{ fontSize: 12, color: "rgba(255,255,255,0.4)", margin: "0 0 6px", lineHeight: 1.4 }}>{s.description}</p>
                  {s.legal_basis?.length > 0 && (
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                      {s.legal_basis.map((l, j) => (
                        <span key={j} style={{ fontSize: 10, padding: "2px 7px", borderRadius: 4, background: "rgba(251,191,36,0.06)", color: "#fbbf24", border: "1px solid rgba(251,191,36,0.12)" }}>{l}</span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 24, paddingTop: 16, borderTop: "1px solid rgba(255,255,255,0.06)" }}>
            <button onClick={() => { setStage("questions"); setAnswerRound(1); }} style={{ padding: "10px 20px", borderRadius: 8, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.5)", cursor: "pointer", fontSize: 13 }}>Voltar</button>
            <button onClick={handleGenerate} style={{ padding: "10px 24px", borderRadius: 8, background: "var(--accent)", border: "none", color: "#fff", fontWeight: 700, cursor: "pointer", fontSize: 13, boxShadow: "0 2px 8px rgba(124,58,237,0.3)" }}>Aprovar e gerar documento</button>
          </div>
        </div>
      </div>
    );
  }

  // Stage: Generating / Document view (Minuta IA layout)
  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#0a0a0f", color: "#fff" }}>

      {/* ── Top Bar ── */}
      <div style={{ height: 52, background: "rgba(255,255,255,0.02)", borderBottom: "1px solid rgba(255,255,255,0.06)", display: "flex", alignItems: "center", padding: "0 16px", gap: 12, flexShrink: 0 }}>
        <button onClick={() => { setStage("select_type"); setSections([]); setOutline(null); setAdversarial(null); }} style={{ background: "none", border: "none", color: "rgba(255,255,255,0.5)", cursor: "pointer", fontSize: 18, padding: 4 }}>×</button>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#fff" }}>{outline?.title || docType}</div>
          {stage === "generating" && <span style={{ fontSize: 11, color: "#22c55e" }}>Salvando...</span>}
          {stage === "document" && <span style={{ fontSize: 11, color: "#22c55e" }}>Documento pronto</span>}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 12, color: "rgba(255,255,255,0.4)", background: "rgba(255,255,255,0.05)", padding: "3px 10px", borderRadius: 6 }}>Etapas {etapas}</span>
          {/* Toolbar icons */}
          <button onClick={copyDocument} title="Copiar" style={{ background: "none", border: "none", color: "rgba(255,255,255,0.4)", cursor: "pointer", fontSize: 16, padding: 4 }}>📋</button>
          {stage === "document" && !adversarial && (
            <button onClick={handleAdversarial} disabled={advLoading} title="Analise Adversarial" style={{ padding: "5px 12px", borderRadius: 6, background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.25)", color: "#ef4444", cursor: "pointer", fontSize: 11, fontWeight: 600 }}>
              {advLoading ? "Analisando..." : "Adversarial"}
            </button>
          )}
        </div>
      </div>

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* ── Left Panel: Roteiro + Respostas ── */}
        <div style={{ width: leftPanelOpen ? 300 : 0, transition: "width 0.2s", overflow: "hidden", borderRight: "1px solid rgba(255,255,255,0.06)", background: "rgba(255,255,255,0.01)", flexShrink: 0, display: "flex", flexDirection: "column" }}>
          <div style={{ padding: 16, overflowY: "auto", flex: 1 }}>

            {/* Roteiro */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <h3 style={{ fontSize: 13, fontWeight: 700, color: "#fff", margin: 0 }}>Roteiro</h3>
                <span style={{ fontSize: 11, color: "rgba(255,255,255,0.4)" }}>{sections.length}/{outlineSections.length}</span>
              </div>
              {outlineSections.map((s, i) => {
                const done = sectionProgress[s.title] === "done";
                const active = stage === "generating" && i === currentSection + 1;
                return (
                  <div key={i} style={{ display: "flex", gap: 8, padding: "6px 0", alignItems: "center", cursor: done ? "pointer" : "default", opacity: done ? 1 : 0.5 }}
                    onClick={() => { if (done) { const el = document.getElementById(`section-${i}`); el?.scrollIntoView({ behavior: "smooth" }); } }}>
                    <div style={{ width: 18, height: 18, borderRadius: "50%", border: done ? "none" : "1.5px solid rgba(255,255,255,0.2)", background: done ? "#22c55e" : active ? "rgba(167,139,250,0.3)" : "transparent", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, color: "#fff", flexShrink: 0 }}>
                      {done ? "✓" : ""}
                    </div>
                    <span style={{ fontSize: 12, color: done ? "#fff" : "rgba(255,255,255,0.5)", lineHeight: 1.3 }}>{s.title}</span>
                  </div>
                );
              })}
            </div>

            {/* Respostas fornecidas */}
            {Object.keys(allAnswers).length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
                  <div style={{ width: 16, height: 16, borderRadius: "50%", background: "#22c55e", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 9, color: "#fff" }}>✓</div>
                  <h3 style={{ fontSize: 13, fontWeight: 700, color: "#fff", margin: 0 }}>Respostas fornecidas</h3>
                  <span style={{ fontSize: 11, color: "rgba(255,255,255,0.4)" }}>{Object.keys(allAnswers).length} respostas</span>
                </div>
                {Object.entries(allAnswers).map(([q, a], i) => (
                  <div key={i} style={{ marginBottom: 10, padding: "8px 10px", background: "rgba(255,255,255,0.02)", borderRadius: 6, border: "1px solid rgba(255,255,255,0.04)" }}>
                    <div style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", marginBottom: 3 }}>{q}</div>
                    <div style={{ fontSize: 12, color: "#22c55e", fontWeight: 500 }}>{a}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Research log */}
            {researchLog.length > 0 && (
              <div>
                <h3 style={{ fontSize: 13, fontWeight: 700, color: "#fff", margin: "0 0 10px" }}>Pesquisas</h3>
                {researchLog.filter(r => r.status === "done" && r.total > 0).map((r, i) => (
                  <div key={i} style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ color: "#22c55e" }}>✓</span>
                    <span>{r.total} fontes - {r.section}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Center: Document ── */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

          {/* Document status bar */}
          {stage === "generating" && (
            <div style={{ padding: "8px 20px", background: "rgba(34,197,94,0.05)", borderBottom: "1px solid rgba(34,197,94,0.1)", display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#22c55e", animation: "pulse 1.5s infinite" }} />
              <span style={{ fontSize: 12, color: "#22c55e", fontWeight: 600 }}>Escrevendo ({writingTime}s)</span>
              <span style={{ fontSize: 12, color: "rgba(255,255,255,0.4)" }}>
                {currentSection >= 0 && outlineSections[currentSection] ? `Gerando "${outlineSections[currentSection]?.title}"` : "Preparando..."}
              </span>
              <div style={{ marginLeft: "auto", width: 120, height: 4, borderRadius: 2, background: "rgba(255,255,255,0.1)" }}>
                <div style={{ width: `${outlineSections.length > 0 ? ((sections.length / outlineSections.length) * 100) : 0}%`, height: "100%", borderRadius: 2, background: "#22c55e", transition: "width 0.3s" }} />
              </div>
            </div>
          )}

          {/* Editable banner */}
          {stage === "document" && (
            <div style={{ padding: "6px 20px", background: "rgba(34,197,94,0.05)", borderBottom: "1px solid rgba(34,197,94,0.1)", fontSize: 12, color: "#22c55e" }}>
              Este documento e editavel. A IA entende e preserva as suas edicoes! Clique no texto para comecar.
            </div>
          )}

          {/* Document content */}
          <div ref={docRef} style={{ flex: 1, overflowY: "auto", padding: "32px 48px", maxWidth: 900, margin: "0 auto", width: "100%" }}>
            {sections.map((sec, i) => (
              <div key={i} id={`section-${i}`} style={{ marginBottom: 32 }}>
                {/* Section number badge */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                  <span style={{ width: 22, height: 22, borderRadius: "50%", background: sec.is_sources ? "rgba(234,179,8,0.15)" : "rgba(34,197,94,0.15)", color: sec.is_sources ? "#eab308" : "#22c55e", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700 }}>{sec.is_sources ? "★" : i + 1}</span>
                  <span style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", background: "rgba(255,255,255,0.03)", padding: "2px 8px", borderRadius: 4 }}>{sec.section_title}</span>
                </div>
                {/* Section title */}
                <h3 style={{ fontSize: 15, fontWeight: 800, color: "#fff", marginBottom: 12, letterSpacing: 0.3 }}>{sec.section_title}</h3>
                {/* Section content - editable */}
                <div contentEditable={stage === "document"} suppressContentEditableWarning
                  style={{ fontSize: 14, color: "rgba(255,255,255,0.8)", lineHeight: 1.85, whiteSpace: "pre-wrap", textAlign: "justify", outline: "none", minHeight: 40 }}>
                  {sec.content}
                </div>
                {/* Source badges */}
                {(sec.sources_count > 0 || sec.models_used?.length > 0) && (
                  <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                    {sec.sources_count > 0 && <span style={{ fontSize: 10, padding: "2px 7px", borderRadius: 8, background: "rgba(234,179,8,0.1)", color: "#eab308" }}>{sec.sources_count} fontes</span>}
                    {(sec.models_used || []).map((m, j) => (
                      <span key={j} style={{ fontSize: 10, padding: "2px 7px", borderRadius: 8, background: m === "Jurema 7B" ? "rgba(34,197,94,0.1)" : "rgba(167,139,250,0.1)", color: m === "Jurema 7B" ? "#22c55e" : "#a78bfa" }}>{m}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {stage === "generating" && sections.length === 0 && (
              <div style={{ textAlign: "center", padding: 60, color: "rgba(255,255,255,0.3)" }}>
                <div style={{ fontSize: 32, marginBottom: 16 }}>📝</div>
                Preparando documento...
              </div>
            )}
          </div>

          {/* ── Adversarial Panel (below document) ── */}
          {adversarial && (
            <div style={{ borderTop: "1px solid rgba(255,255,255,0.08)", maxHeight: "45vh", overflowY: "auto", padding: 20, background: "rgba(255,255,255,0.01)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                <span style={{ fontSize: 20 }}>⚔️</span>
                <div>
                  <h3 style={{ fontSize: 15, fontWeight: 700, color: "#fff", margin: 0 }}>Analise adversarial estruturada</h3>
                  <p style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", margin: 0 }}>Peca adversaria gerada e vulnerabilidades com correcoes aplicaveis.</p>
                </div>
              </div>

              {/* Classification */}
              <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 12px", background: "rgba(255,255,255,0.03)", borderRadius: 8, marginBottom: 12, fontSize: 12, flexWrap: "wrap" }}>
                <span style={{ color: "rgba(255,255,255,0.5)" }}>{adversarial.classification?.tipo_peca}</span>
                <span style={{ color: "rgba(255,255,255,0.3)" }}>→</span>
                <span style={{ fontWeight: 700, color: "#d4bbff" }}>{adversarial.classification?.peca_adversaria}</span>
                <span style={{ color: "rgba(255,255,255,0.4)" }}>TRILHA: <strong style={{ color: "#a78bfa" }}>{adversarial.classification?.trilha}</strong></span>
                <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 11 }}>Confianca</span>
                  <div style={{ width: 60, height: 5, borderRadius: 3, background: "rgba(255,255,255,0.1)" }}>
                    <div style={{ width: `${adversarial.classification?.confianca || 0}%`, height: "100%", borderRadius: 3, background: "#ef4444" }} />
                  </div>
                  <span style={{ fontWeight: 700, color: "#ef4444", fontSize: 12 }}>{adversarial.classification?.confianca}%</span>
                </div>
              </div>

              {/* Racional + Strategy */}
              {adversarial.classification?.racional && (
                <div style={{ padding: 12, background: "rgba(255,255,255,0.02)", borderRadius: 8, marginBottom: 8 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.4)", letterSpacing: 1, marginBottom: 4 }}>RACIONAL</div>
                  <p style={{ fontSize: 12.5, color: "rgba(255,255,255,0.65)", lineHeight: 1.5, margin: 0 }}>{adversarial.classification.racional}</p>
                </div>
              )}
              {adversarial.classification?.estrategia_adversarial && (
                <div style={{ padding: 12, background: "rgba(255,255,255,0.02)", borderRadius: 8, marginBottom: 14 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.4)", letterSpacing: 1, marginBottom: 4 }}>ESTRATEGIA ADVERSARIAL</div>
                  <p style={{ fontSize: 12.5, color: "rgba(255,255,255,0.65)", lineHeight: 1.5, margin: 0 }}>{adversarial.classification.estrategia_adversarial}</p>
                </div>
              )}

              {/* Tabs */}
              <div style={{ display: "flex", gap: 0, marginBottom: 14, borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                <button onClick={() => setAdvTab("doc")} style={{ padding: "8px 16px", background: "none", border: "none", cursor: "pointer", fontSize: 12, fontWeight: 600, color: advTab === "doc" ? "#d4bbff" : "rgba(255,255,255,0.4)", borderBottom: advTab === "doc" ? "2px solid #a78bfa" : "2px solid transparent" }}>Peca adversaria</button>
                <button onClick={() => setAdvTab("vulns")} style={{ padding: "8px 16px", background: "none", border: "none", cursor: "pointer", fontSize: 12, fontWeight: 600, color: advTab === "vulns" ? "#d4bbff" : "rgba(255,255,255,0.4)", borderBottom: advTab === "vulns" ? "2px solid #a78bfa" : "2px solid transparent" }}>Vulnerabilidades <span style={{ fontSize: 10, background: "rgba(239,68,68,0.15)", color: "#ef4444", padding: "1px 5px", borderRadius: 6, marginLeft: 3 }}>{adversarial.vulnerabilities?.length || 0}</span></button>
              </div>

              {advTab === "doc" && adversarial.adversarialDoc && (
                <div style={{ fontSize: 13, color: "rgba(255,255,255,0.65)", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>{adversarial.adversarialDoc.content}</div>
              )}

              {advTab === "vulns" && (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 10 }}>
                  {(adversarial.vulnerabilities || []).map((v, i) => (
                    <div key={i} style={{ padding: 14, borderRadius: 8, background: `${SEV[v.severity] || SEV.MEDIA}12`, border: `1px solid ${SEV[v.severity] || SEV.MEDIA}30`, borderLeft: `3px solid ${SEV[v.severity] || SEV.MEDIA}` }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                        <h5 style={{ fontSize: 12.5, fontWeight: 700, color: "#fff", margin: 0, flex: 1 }}>{v.title}</h5>
                        <span style={{ fontSize: 9, fontWeight: 700, padding: "2px 6px", borderRadius: 4, background: SEV[v.severity], color: "#fff" }}>{v.severity}</span>
                        <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 4, background: "rgba(255,255,255,0.06)", color: CAT_COLOR[v.category] || "#a78bfa" }}>{v.category}</span>
                      </div>
                      <p style={{ fontSize: 11.5, color: "rgba(255,255,255,0.55)", lineHeight: 1.4, margin: 0 }}>{v.description}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Bottom: Chat input ── */}
          <div style={{ padding: "10px 20px", borderTop: "1px solid rgba(255,255,255,0.06)", background: "rgba(255,255,255,0.02)" }}>
            <div style={{ display: "flex", gap: 8, maxWidth: 800, margin: "0 auto" }}>
              <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && handleChat()} placeholder="Instrucoes para melhoria da minuta..."
                style={{ flex: 1, padding: "10px 14px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)", color: "#fff", fontSize: 13, outline: "none" }} />
              <button onClick={handleChat} style={{ padding: "10px 16px", borderRadius: 8, background: "var(--accent)", border: "none", color: "#fff", cursor: "pointer", fontWeight: 600, fontSize: 12 }}>Enviar</button>
            </div>
            {chatMessages.length > 0 && (
              <div style={{ maxHeight: 120, overflowY: "auto", marginTop: 8, maxWidth: 800, margin: "8px auto 0" }}>
                {chatMessages.slice(-3).map((m, i) => (
                  <div key={i} style={{ fontSize: 12, color: m.role === "user" ? "#a78bfa" : m.role === "system" ? "#ef4444" : "rgba(255,255,255,0.6)", padding: "3px 0" }}>
                    {m.role === "user" ? "Voce: " : m.role === "system" ? "Erro: " : "IA: "}{m.text?.substring(0, 200)}
                  </div>
                ))}
              </div>
            )}
            <div style={{ textAlign: "center", fontSize: 10, color: "rgba(255,255,255,0.2)", marginTop: 4 }}>
              JurisGen AI pode cometer erros. Nunca dispense a revisao humana final.
            </div>
          </div>
        </div>

        {/* ── Right sidebar: Tool icons ── */}
        <div style={{ width: 44, borderLeft: "1px solid rgba(255,255,255,0.06)", display: "flex", flexDirection: "column", alignItems: "center", padding: "12px 0", gap: 4, flexShrink: 0 }}>
          <button onClick={() => setLeftPanelOpen(p => !p)} title="Roteiro" style={{ width: 32, height: 32, borderRadius: 6, background: "none", border: "none", color: "rgba(255,255,255,0.4)", cursor: "pointer", fontSize: 14 }}>📋</button>
          <button onClick={copyDocument} title="Copiar documento" style={{ width: 32, height: 32, borderRadius: 6, background: "none", border: "none", color: "rgba(255,255,255,0.4)", cursor: "pointer", fontSize: 14 }}>📄</button>
          {stage === "document" && (
            <>
              <button onClick={handleAdversarial} disabled={advLoading} title="Analise adversarial" style={{ width: 32, height: 32, borderRadius: 6, background: "none", border: "none", color: adversarial ? "#ef4444" : "rgba(255,255,255,0.4)", cursor: "pointer", fontSize: 14 }}>⚔️</button>
              <button title="Pesquisas" style={{ width: 32, height: 32, borderRadius: 6, background: "none", border: "none", color: "rgba(255,255,255,0.4)", cursor: "pointer", fontSize: 14 }}>🔍</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

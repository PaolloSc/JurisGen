import { useCallback, useEffect, useRef, useState } from "react";

// ─── Config ──────────────────────────────────────────────
const API_BASE = import.meta.env.VITE_API_BASE || "";
const API_TIMEOUT_MS = 60000;

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
];

function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function detectDocumentType(message) {
  const normalized = normalizeText(message);

  for (const docType of DOC_TYPES) {
    const label = normalizeText(docType.label);
    if (normalized.includes(label)) {
      return docType;
    }
  }

  if (normalized.includes("peticao") || normalized.includes("petição")) {
    return DOC_TYPES.find(item => item.id === "peticao_inicial") || null;
  }

  return null;
}

// ─── Message Types ───────────────────────────────────────
// Messages in chat can be: text, questions (structured form), outline, document_section, system

// ─── Sub-Components ──────────────────────────────────────

function ThinkingBlock({ text }) {
  const [open, setOpen] = useState(false);
  if (!text) return null;
  return (
    <div style={{ margin: "8px 0", borderRadius: 8, overflow: "hidden", border: "1px solid rgba(167,139,250,0.15)", background: "rgba(167,139,250,0.04)" }}>
      <button onClick={() => setOpen(!open)} style={{ width: "100%", padding: "8px 12px", background: "none", border: "none", color: "#a78bfa", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontFamily: "var(--mono)" }}>
        <span style={{ transform: open ? "rotate(90deg)" : "", transition: "transform 0.15s", display: "inline-block" }}>▶</span>
        Cadeia de pensamento
      </button>
      {open && <div style={{ padding: "4px 12px 10px", fontSize: 11.5, lineHeight: 1.65, color: "rgba(167,139,250,0.75)", fontFamily: "var(--mono)", whiteSpace: "pre-wrap", maxHeight: 220, overflowY: "auto" }}>{text}</div>}
    </div>
  );
}

function QuestionFormInline({ questions, onSubmit }) {
  const safeQuestions = Array.isArray(questions) ? questions : [];
  const [answers, setAnswers] = useState({});
  const [customs, setCustoms] = useState({});

  const normalizeOption = (option) => {
    if (typeof option === "string") {
      return { id: option, label: option };
    }
    if (option && typeof option === "object") {
      return {
        id: option.id ?? option.value ?? option.label ?? option.text ?? "option",
        label: option.label ?? option.text ?? option.value ?? option.id ?? "Opção",
        desc: option.desc ?? option.description ?? "",
      };
    }
    return { id: String(option ?? "option"), label: String(option ?? "Opção") };
  };

  const getQuestionType = (question) => {
    const type = String(question?.type || "").toLowerCase();
    if (type === "choice" || type === "select" || type === "single") return "single";
    if (type === "multiple" || type === "multi") return "multiple";
    return "text";
  };

  const toggle = (qId, optId, type) => {
    if (type === "multiple") {
      setAnswers(p => {
        const cur = p[qId] || [];
        return { ...p, [qId]: cur.includes(optId) ? cur.filter(x => x !== optId) : [...cur, optId] };
      });
    } else {
      setAnswers(p => ({ ...p, [qId]: optId }));
    }
  };

  const buildMap = () => {
    const r = {};
    for (const q of safeQuestions) {
      const a = answers[q.id]; if (!a) continue;
      const options = Array.isArray(q.options) ? q.options.map(normalizeOption) : [];
      const questionType = getQuestionType(q);
      if (questionType === "multiple") {
        r[q.text] = Array.isArray(a)
          ? a.map(id => id === "other" ? (customs[q.id] || "Outro") : (options.find(o => o.id === id)?.label || id))
          : [];
      } else if (questionType === "single") {
        r[q.text] = a === "other" ? (customs[q.id] || "Outro") : (options.find(o => o.id === a)?.label || a);
      } else {
        r[q.text] = typeof a === "string" ? a : Array.isArray(a) ? a.join(", ") : String(a);
      }
    }
    return r;
  };

  // At least 1 answer is enough — unanswered fields become placeholders in the document
  const answeredCount = safeQuestions.filter(q => {
    const a = answers[q.id];
    if (!a) return false;
    if (typeof a === "string") return a.trim().length > 0;
    if (Array.isArray(a)) return a.length > 0;
    return true;
  }).length;
  const done = safeQuestions.length > 0 && answeredCount >= 1;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
      {safeQuestions.map((q, qi) => {
        const options = Array.isArray(q.options) ? q.options.map(normalizeOption) : [];
        const questionType = getQuestionType(q);
        const otherOn = questionType === "multiple" ? (answers[q.id] || []).includes("other") : answers[q.id] === "other";
        return (
          <div key={q.id}>
            <div style={{ display: "flex", gap: 8, marginBottom: 10, alignItems: "flex-start" }}>
              <span style={{ background: "var(--accent)", color: "#fff", width: 22, height: 22, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, flexShrink: 0, marginTop: 1 }}>{qi + 1}</span>
              <span style={{ fontSize: 13.5, color: "var(--text)", fontWeight: 500, lineHeight: 1.45 }}>{q.text}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, paddingLeft: 30 }}>
              {questionType === "text" ? (
                <textarea
                  value={answers[q.id] || ""}
                  onChange={e => setAnswers(p => ({ ...p, [q.id]: e.target.value }))}
                  placeholder="Digite sua resposta..."
                  rows={3}
                  style={{ padding: "10px 12px", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(167,139,250,0.25)", borderRadius: 6, color: "var(--text)", fontSize: 13, outline: "none", resize: "vertical", minHeight: 84 }}
                />
              ) : (
                <>
                  {options.map(opt => {
                    const sel = questionType === "multiple" ? (answers[q.id] || []).includes(opt.id) : answers[q.id] === opt.id;
                    return (
                      <button key={opt.id} onClick={() => toggle(q.id, opt.id, questionType === "multiple" ? "multiple" : "single")} style={{
                        padding: opt.desc ? "10px 12px" : "8px 12px", background: sel ? "rgba(167,139,250,0.12)" : "rgba(255,255,255,0.02)", border: sel ? "1px solid rgba(167,139,250,0.4)" : "1px solid rgba(255,255,255,0.07)", borderRadius: 7, color: sel ? "#d4bbff" : "var(--text-dim)", cursor: "pointer", textAlign: "left", display: "flex", alignItems: "flex-start", gap: 8, fontSize: 13, transition: "all 0.12s",
                      }}>
                        <span style={{ width: 16, height: 16, borderRadius: questionType === "multiple" ? 3 : "50%", border: sel ? "2px solid var(--accent)" : "2px solid rgba(255,255,255,0.18)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 1, background: sel ? "var(--accent)" : "transparent", transition: "all 0.12s" }}>
                          {sel && <span style={{ color: "#fff", fontSize: 10, fontWeight: 700 }}>✓</span>}
                        </span>
                        <div>
                          <div style={{ fontWeight: 500 }}>{opt.label}</div>
                          {opt.desc && <div style={{ fontSize: 11.5, color: "rgba(255,255,255,0.3)", marginTop: 2 }}>{opt.desc}</div>}
                        </div>
                      </button>
                    );
                  })}
                  {otherOn && (
                <input autoFocus value={customs[q.id] || ""} onChange={e => setCustoms(p => ({ ...p, [q.id]: e.target.value }))} placeholder="Especifique..."
                  style={{ padding: "8px 12px", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(167,139,250,0.25)", borderRadius: 6, color: "var(--text)", fontSize: 13, outline: "none", marginLeft: 24 }} />
                  )}
                </>
              )}
            </div>
          </div>
        );
      })}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 4 }}>
        <span style={{ fontSize: 11, color: "rgba(255,255,255,0.25)" }}>
          {answeredCount}/{safeQuestions.length} respondidas — campos vazios virarão [placeholders]
        </span>
        <button onClick={() => onSubmit(buildMap())} disabled={!done} style={{
          padding: "10px 22px", background: done ? "var(--accent)" : "rgba(255,255,255,0.05)", border: "none", borderRadius: 7, color: done ? "#fff" : "rgba(255,255,255,0.2)", fontWeight: 600, cursor: done ? "pointer" : "not-allowed", fontSize: 13,
        }}>Continuar →</button>
      </div>
    </div>
  );
}

function OutlineCard({ outline, onApprove, onRegenerate }) {
  const safeKeyArguments = Array.isArray(outline.key_arguments) ? outline.key_arguments : [];
  const safeSections = Array.isArray(outline.sections) ? outline.sections : [];
  return (
    <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 10, padding: 20 }}>
      <h4 style={{ fontSize: 15, fontWeight: 700, color: "#d4bbff", marginBottom: 4, fontFamily: "var(--display)" }}>{outline.title}</h4>
      {outline.subtitle && <p style={{ color: "rgba(255,255,255,0.35)", fontSize: 12, marginBottom: 16 }}>{outline.subtitle}</p>}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        <span style={{ background: "rgba(167,139,250,0.1)", color: "#a78bfa", padding: "3px 10px", borderRadius: 16, fontSize: 11.5 }}>📄 ~{outline.estimated_pages} páginas</span>
        <span style={{ background: "rgba(167,139,250,0.1)", color: "#a78bfa", padding: "3px 10px", borderRadius: 16, fontSize: 11.5 }}>📑 {safeSections.length} seções</span>
      </div>
      {safeKeyArguments.map((a, i) => (
        <div key={i} style={{ padding: "6px 10px", background: "rgba(34,197,94,0.06)", border: "1px solid rgba(34,197,94,0.15)", borderRadius: 6, color: "#86efac", fontSize: 12, marginBottom: 5 }}>✦ {a}</div>
      ))}
      <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 14 }}>
        {safeSections.map((s, i) => (
          <div key={i} style={{ padding: 12, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <span style={{ background: "var(--accent)", color: "#fff", width: 20, height: 20, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700, flexShrink: 0 }}>{i + 1}</span>
              <span style={{ fontWeight: 600, fontSize: 13.5, color: "var(--text)" }}>{s.title}</span>
            </div>
            <p style={{ fontSize: 12, color: "rgba(255,255,255,0.4)", lineHeight: 1.45, paddingLeft: 28, marginBottom: 6 }}>{s.description}</p>
            {Array.isArray(s.legal_basis) && s.legal_basis.length > 0 && (
              <div style={{ paddingLeft: 28, display: "flex", gap: 5, flexWrap: "wrap" }}>
                {s.legal_basis.map((l, li) => (
                  <span key={li} style={{ background: "rgba(251,191,36,0.08)", color: "#fbbf24", padding: "2px 8px", borderRadius: 4, fontSize: 10.5, fontWeight: 500 }}>⚖️ {l}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 16 }}>
        <button onClick={onRegenerate} style={{ padding: "8px 18px", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 6, color: "rgba(255,255,255,0.5)", cursor: "pointer", fontSize: 13 }}>↻ Regenerar</button>
        <button onClick={onApprove} style={{ padding: "8px 22px", background: "var(--accent)", border: "none", borderRadius: 6, color: "#fff", fontWeight: 600, cursor: "pointer", fontSize: 13 }}>Aprovar e gerar →</button>
      </div>
    </div>
  );
}

function DocumentSection({ section }) {
  return (
    <div style={{ marginBottom: 24 }}>
      <h4 style={{ fontSize: 14, fontWeight: 700, color: "#d4bbff", marginBottom: 10, paddingBottom: 6, borderBottom: "1px solid rgba(167,139,250,0.15)", fontFamily: "var(--display)" }}>{section.section_title}</h4>
      <div style={{ fontSize: 13.5, color: "var(--text-dim)", lineHeight: 1.8, whiteSpace: "pre-wrap", textAlign: "justify" }}>{section.content}</div>
    </div>
  );
}

function SharePointPanel({ sessionId, references, onAttach, onDetach, onSearch }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [syncDocs, setSyncDocs] = useState([]);
  const [syncMessage, setSyncMessage] = useState("");
  const [libraries, setLibraries] = useState([]);
  const [selectedLibrary, setSelectedLibrary] = useState("Documentos");
  const [searching, setSearching] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [indexing, setIndexing] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        setSyncMessage("Carregando bibliotecas do SharePoint...");
        const resp = await api("/api/bibliotecas-sharepoint", {}, 120000);
        const data = await resp.json();
        const items = Array.isArray(data.bibliotecas) ? data.bibliotecas : [];
        setLibraries(items);
        if (items.length > 0) {
          setSelectedLibrary(items[0].title || "Documentos");
          setSyncMessage(`Bibliotecas encontradas: ${items.length}. Selecione uma e carregue os documentos.`);
        } else {
          setSyncMessage("Nenhuma biblioteca visível foi retornada pelo SharePoint.");
        }
      } catch (e) {
        setSyncMessage(`Falha ao carregar bibliotecas do SharePoint: ${e.name === "AbortError" ? "tempo esgotado" : e.message}`);
      }
    })();
  }, []);

  const search = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const resp = await api("/api/sharepoint/search", {
        method: "POST",
        body: JSON.stringify({ query: query.trim(), file_types: ["docx", "doc"], max_results: 8 }),
      });
      const data = await resp.json();
      setResults(data.results || []);
    } catch (e) {
      console.error(e);
    }
    setSearching(false);
  };

  const upload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("session_id", sessionId);
      formData.append("file", file);

      const resp = await fetch(`${API_BASE}/api/sharepoint/upload`, {
        method: "POST",
        body: formData,
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail));
      }

      const data = await resp.json();
      const ref = data.ref;
      if (ref) {
        onAttach({
          id: ref.id,
          item_id: ref.id,
          name: ref.name,
          content: ref.content,
          source: ref.source,
          web_url: ref.web_url,
        });
      }
    } catch (e) {
      console.error(e);
    }
    setUploading(false);
    event.target.value = "";
  };

  const loadLibraryDocuments = async () => {
    setSyncing(true);
    setSyncMessage("");
    try {
      const listResp = await api("/api/listar-sharepoint", {
        method: "POST",
        body: JSON.stringify({ biblioteca: selectedLibrary }),
      }, 120000);

      const listData = await listResp.json();
      setSyncDocs(Array.isArray(listData.documentos) ? listData.documentos : []);
      setSyncMessage(`${listData.total_documentos || 0} documentos encontrados na biblioteca ${selectedLibrary}.`);
    } catch (e) {
      setSyncDocs([]);
      setSyncMessage(`Falha ao carregar documentos do SharePoint: ${e.name === "AbortError" ? "tempo esgotado" : e.message}`);
    }
    setSyncing(false);
  };

  const indexLibrary = async () => {
    setIndexing(true);
    setSyncMessage("Iniciando indexação...");
    try {
      await api("/api/indexar-sharepoint", {
        method: "POST",
        body: JSON.stringify({ biblioteca: selectedLibrary }),
      }, 120000);
      // Start polling for progress
      pollIndexStatus();
    } catch (e) {
      setSyncMessage(`Falha ao indexar SharePoint: ${e.name === "AbortError" ? "tempo esgotado" : e.message}`);
      setIndexing(false);
    }
  };

  const pollIndexStatus = () => {
    const interval = setInterval(async () => {
      try {
        const resp = await api("/api/indexar-status");
        const data = await resp.json();
        setSyncMessage(data.progress || "Processando...");
        if (Array.isArray(data.documentos) && data.documentos.length > 0) {
          setSyncDocs(data.documentos);
        }
        if (!data.running) {
          clearInterval(interval);
          setIndexing(false);
          setSyncMessage(`Concluído: ${data.total_documentos} documentos, ${data.total_chunks} trechos indexados.`);
        }
      } catch {
        clearInterval(interval);
        setIndexing(false);
      }
    }, 3000);
  };

  const loadIndexedDocs = async () => {
    try {
      const resp = await api("/api/documentos-indexados");
      const data = await resp.json();
      setSyncDocs(Array.isArray(data.documentos) ? data.documentos : []);
      setSyncMessage(`${data.total} documentos na memória (${data.total_chunks} trechos).`);
    } catch (e) {
      setSyncMessage(`Erro ao carregar documentos indexados: ${e.message}`);
    }
  };

  // Load indexed docs on mount
  useEffect(() => {
    loadIndexedDocs();
  }, []);

  return (
    <div style={{ borderBottom: "1px solid rgba(255,255,255,0.06)", paddingBottom: 12, marginBottom: 12 }}>
      <button onClick={() => setExpanded(!expanded)} style={{
        width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
        background: "none", border: "none", color: "var(--text)", cursor: "pointer", padding: "6px 0", fontSize: 13, fontWeight: 600,
      }}>
        <span>📂 Modelos SharePoint</span>
        <span style={{ fontSize: 11, color: "rgba(255,255,255,0.3)" }}>{references.length > 0 ? `${references.length} anexo(s)` : ""} {expanded ? "▼" : "▶"}</span>
      </button>

      {expanded && (
        <div style={{ marginTop: 8 }}>
          {references.length > 0 && (
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Referências de estilo</div>
              {references.map((r, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "6px 8px", background: "rgba(34,197,94,0.06)", borderRadius: 6, marginBottom: 4, fontSize: 12 }}>
                  <span style={{ color: "#86efac", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 160 }}>
                    📎 {r.web_url ? <a href={r.web_url} target="_blank" rel="noreferrer" style={{ color: "#86efac", textDecoration: "none" }}>{r.name}</a> : r.name}
                  </span>
                  <button onClick={() => onDetach(r.item_id)} style={{ background: "none", border: "none", color: "rgba(255,255,255,0.3)", cursor: "pointer", fontSize: 11, padding: "2px 4px" }}>✕</button>
                </div>
              ))}
            </div>
          )}

          <div style={{ display: "flex", gap: 6 }}>
            <input
              value={query} onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === "Enter" && search()}
              placeholder="Buscar modelos..."
              style={{ flex: 1, padding: "7px 10px", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, color: "var(--text)", fontSize: 12, outline: "none" }}
            />
            <button onClick={search} disabled={searching} style={{ padding: "7px 12px", background: "var(--accent)", border: "none", borderRadius: 6, color: "#fff", cursor: "pointer", fontSize: 12, opacity: searching ? 0.5 : 1 }}>
              {searching ? "..." : "🔍"}
            </button>
          </div>

          <div style={{ marginTop: 8 }}>
            <button onClick={loadLibraryDocuments} disabled={syncing} style={{ width: "100%", padding: "8px 12px", background: syncing ? "rgba(255,255,255,0.05)" : "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.18)", borderRadius: 6, color: syncing ? "rgba(255,255,255,0.35)" : "#86efac", cursor: syncing ? "not-allowed" : "pointer", fontSize: 12, fontWeight: 600 }}>
              {syncing ? "Carregando documentos..." : "Carregar documentos do SharePoint"}
            </button>
            <button onClick={indexLibrary} disabled={indexing} style={{ width: "100%", marginTop: 6, padding: "8px 12px", background: indexing ? "rgba(255,255,255,0.05)" : "rgba(124,58,237,0.10)", border: "1px solid rgba(124,58,237,0.20)", borderRadius: 6, color: indexing ? "rgba(255,255,255,0.35)" : "#d4bbff", cursor: indexing ? "not-allowed" : "pointer", fontSize: 12, fontWeight: 600 }}>
              {indexing ? "Indexando acervo..." : "Baixar e indexar documentos"}
            </button>
            <button onClick={loadIndexedDocs} style={{ width: "100%", marginTop: 6, padding: "8px 12px", background: "rgba(59,130,246,0.08)", border: "1px solid rgba(59,130,246,0.18)", borderRadius: 6, color: "#93c5fd", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
              Ver documentos na memória
            </button>
            <div style={{ fontSize: 11, color: "rgba(255,255,255,0.25)", marginTop: 5 }}>
              Baixa todos os documentos do SharePoint e indexa na memória da IA.
            </div>
            <div style={{ marginTop: 8 }}>
              <select
                value={selectedLibrary}
                onChange={e => setSelectedLibrary(e.target.value)}
                style={{ width: "100%", padding: "8px 10px", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, color: "var(--text)", fontSize: 12, outline: "none" }}
              >
                {libraries.length > 0 ? libraries.map(lib => (
                  <option key={lib.title} value={lib.title}>{lib.title}</option>
                )) : <option value="Documentos">Documentos</option>}
              </select>
              <div style={{ fontSize: 11, color: "rgba(255,255,255,0.25)", marginTop: 4 }}>
                Biblioteca selecionada para descoberta e sincronização.
              </div>
            </div>
            {syncMessage && (
              <div style={{ marginTop: 8, fontSize: 11.5, color: syncMessage.startsWith("Falha") ? "#fca5a5" : "#86efac", lineHeight: 1.45 }}>
                {syncMessage}
              </div>
            )}
            {syncDocs.length > 0 && (
              <div style={{ marginTop: 10, maxHeight: 300, overflowY: "auto" }}>
                <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                  {syncDocs.length} documento(s) {indexing ? "(indexando...)" : ""}
                </div>
                {syncDocs.map((doc, idx) => {
                  const isError = doc.status?.startsWith("erro");
                  const isEmpty = doc.status === "sem texto";
                  const isOk = doc.status === "indexado";
                  const statusColor = isError ? "#fca5a5" : isEmpty ? "#fbbf24" : isOk ? "#86efac" : "rgba(255,255,255,0.4)";
                  const bgColor = isError ? "rgba(239,68,68,0.05)" : isEmpty ? "rgba(251,191,36,0.05)" : "rgba(34,197,94,0.05)";
                  return (
                    <div key={idx} style={{ padding: "8px 10px", marginBottom: 6, borderRadius: 6, background: bgColor, border: `1px solid ${statusColor}22` }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 12, fontWeight: 600 }}>
                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: statusColor }}>
                          {isOk ? "✓" : isEmpty ? "○" : isError ? "✕" : "•"} {doc.name}
                        </span>
                        <span style={{ flexShrink: 0, color: "rgba(255,255,255,0.3)", fontSize: 11 }}>
                          {doc.chunks > 0 ? `${doc.chunks} trechos` : doc.status}
                        </span>
                      </div>
                      {doc.folder && (
                        <div style={{ fontSize: 10, color: "rgba(255,255,255,0.2)", marginTop: 2 }}>📁 {doc.folder}</div>
                      )}
                      {doc.preview && (
                        <div style={{ marginTop: 4, fontSize: 11, color: "rgba(255,255,255,0.3)", lineHeight: 1.4, maxHeight: 44, overflow: "hidden" }}>
                          {doc.preview.slice(0, 200)}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 8 }}>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "7px 12px", background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, color: "var(--text-dim)", cursor: "pointer", fontSize: 12 }}>
              <span>{uploading ? "Enviando..." : "⬆ Upload"}</span>
              <input type="file" accept=".doc,.docx,.pdf,.txt" onChange={upload} style={{ display: "none" }} />
            </label>
            <span style={{ fontSize: 11, color: "rgba(255,255,255,0.25)" }}>Enviar modelo ou referência para a sessão</span>
          </div>

          {results.length > 0 && (
            <div style={{ marginTop: 8, maxHeight: 200, overflowY: "auto" }}>
              {results.map((r, i) => (
                <button key={i} onClick={() => onAttach(r)} style={{
                  width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 10px",
                  background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: 6,
                  color: "var(--text-dim)", cursor: "pointer", marginBottom: 4, textAlign: "left", fontSize: 12,
                }}>
                  <div style={{ overflow: "hidden" }}>
                    <div style={{ fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 170 }}>{r.name}</div>
                    {r.summary && <div style={{ fontSize: 11, color: "rgba(255,255,255,0.25)", marginTop: 2 }}>{r.summary.slice(0, 60)}...</div>}
                  </div>
                  <span style={{ color: "var(--accent)", fontSize: 11, flexShrink: 0, marginLeft: 6 }}>+ Anexar</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Chat Message Renderer ───────────────────────────────
function ChatMessage({ msg, onQuestionSubmit, onOutlineApprove, onOutlineRegenerate }) {
  const isUser = msg.role === "user";
  const isSystem = msg.role === "system";
  const safeContent = typeof msg.content === "string" ? msg.content : JSON.stringify(msg.content ?? "", null, 2);
  const safeQuestions = Array.isArray(msg.questions) ? msg.questions : [];
  const safeOutline = msg.outline && typeof msg.outline === "object" ? msg.outline : { title: "Roteiro indisponível", sections: [], key_arguments: [] };
  const safeSections = Array.isArray(msg.sections) ? msg.sections : [];

  return (
    <div style={{
      display: "flex",
      justifyContent: isUser ? "flex-end" : "flex-start",
      marginBottom: 16,
      paddingLeft: isUser ? 48 : 0,
      paddingRight: isUser ? 0 : 48,
      animation: "msgIn 0.25s ease-out",
    }}>
      <div style={{
        maxWidth: "100%",
        padding: isSystem ? "8px 12px" : "12px 16px",
        borderRadius: isUser ? "14px 14px 4px 14px" : "14px 14px 14px 4px",
        background: isSystem
          ? "rgba(251,191,36,0.06)"
          : isUser
            ? "rgba(167,139,250,0.15)"
            : "rgba(255,255,255,0.03)",
        border: isSystem
          ? "1px solid rgba(251,191,36,0.15)"
          : isUser
            ? "1px solid rgba(167,139,250,0.25)"
            : "1px solid rgba(255,255,255,0.06)",
        color: isSystem ? "#fbbf24" : "var(--text-dim)",
        fontSize: isSystem ? 12 : 13.5,
        lineHeight: 1.6,
      }}>
        {msg.thinking && <ThinkingBlock text={msg.thinking} />}

        {msg.type === "text" && (
          <div style={{ whiteSpace: "pre-wrap" }}>{safeContent}</div>
        )}

        {msg.type === "questions" && (
          <div>
            {msg.thinking_summary && (
              <div style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", marginBottom: 12, fontStyle: "italic", lineHeight: 1.5 }}>
                💭 {msg.thinking_summary}
              </div>
            )}
            {safeQuestions.length > 0 ? (
              <QuestionFormInline questions={safeQuestions} onSubmit={onQuestionSubmit} />
            ) : (
              <div style={{ whiteSpace: "pre-wrap" }}>{safeContent || "O servidor não retornou perguntas válidas para continuar."}</div>
            )}
          </div>
        )}

        {msg.type === "outline" && (
          <OutlineCard outline={safeOutline} onApprove={onOutlineApprove} onRegenerate={onOutlineRegenerate} />
        )}

        {msg.type === "document_section" && (
          <DocumentSection section={msg.section} />
        )}

        {msg.type === "document_complete" && (
          <div>
            {safeSections.length > 0 ? safeSections.map((s, i) => <DocumentSection key={i} section={s} />) : <div style={{ whiteSpace: "pre-wrap" }}>{safeContent || "Documento concluído, mas sem seções estruturadas para exibir."}</div>}
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
              <button onClick={() => {
                const text = safeSections.map(s => `${s.section_title}\n\n${s.content}`).join("\n\n" + "─".repeat(40) + "\n\n");
                navigator.clipboard.writeText(text);
              }} style={{
                padding: "8px 18px", background: "var(--accent)", border: "none", borderRadius: 6, color: "#fff", fontWeight: 600, cursor: "pointer", fontSize: 12,
              }}>📋 Copiar tudo</button>
            </div>
          </div>
        )}

        {!msg.type && (
          <div style={{ whiteSpace: "pre-wrap" }}>{safeContent}</div>
        )}
      </div>
    </div>
  );
}

// ─── Main App ────────────────────────────────────────────
export default function JurisGenApp() {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [docType, setDocType] = useState("");
  const [stage, setStage] = useState("select_type");
  const [allAnswers, setAllAnswers] = useState({});
  const [outline, setOutline] = useState(null);
  const [references, setReferences] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [llmStatus, setLlmStatus] = useState(null);
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  const initRef = useRef(false);

  const scrollToBottom = () => {
    setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
  };

  const addMessage = useCallback((msg) => {
    setMessages(prev => [...prev, msg]);
    scrollToBottom();
  }, []);

  // Initialize session on mount (only once, even in StrictMode)
  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;

    (async () => {
      try {
        // Try to restore previous session
        const savedSession = localStorage.getItem("jurisgen_session_id");
        let restoredSession = false;

        if (savedSession) {
          try {
            const checkResp = await api(`/api/sessions/${savedSession}`);
            const sessionData = await checkResp.json();
            setSessionId(savedSession);

            // Restore state
            if (sessionData.doc_type) setDocType(sessionData.doc_type);
            if (sessionData.answers && Object.keys(sessionData.answers).length > 0) setAllAnswers(sessionData.answers);
            if (sessionData.outline) { setOutline(sessionData.outline); setStage("outline"); }
            else if (sessionData.doc_type) setStage("questions");

            // Load message history
            const histResp = await api(`/api/sessions/${savedSession}/messages`);
            const histData = await histResp.json();
            if (histData.messages && histData.messages.length > 0) {
              for (const msg of histData.messages) {
                addMessage({ role: msg.role, type: msg.type || "text", content: msg.content || "" });
              }
              restoredSession = true;
            }
          } catch {
            localStorage.removeItem("jurisgen_session_id");
          }
        }

        if (!restoredSession) {
          const resp = await api("/api/sessions", { method: "POST", body: JSON.stringify({}) });
          const data = await resp.json();
          const newId = data.session_id || data.id;
          setSessionId(newId);
          localStorage.setItem("jurisgen_session_id", newId);
          addMessage({
            role: "assistant", type: "text",
            content: "Olá! Sou o PetiçãoAI + JurisGen. Posso ajudar a elaborar qualquer tipo de documento jurídico.\n\nVocê pode selecionar um tipo abaixo, ou simplesmente me dizer o que precisa — eu me adapto.",
          });
        }
      } catch (e) {
        addMessage({ role: "system", type: "text", content: `⚠️ Erro ao conectar com o servidor: ${e.message}. Verifique se o backend está rodando em ${API_BASE}` });
      }
    })();

    (async () => {
      try {
        const resp = await api("/api/llm/status");
        const data = await resp.json();
        setLlmStatus(data);
      } catch (e) {
        setLlmStatus({ available: false, message: `Não foi possível consultar o Claude: ${e.message}` });
      }
    })();
  }, []);

  // ─── Handlers ────────────────────────────────────────

  const handleSelectType = async (type, sourceMessage = null) => {
    setDocType(type);
    setStage("questions");
    addMessage({ role: "user", type: "text", content: sourceMessage || `Quero elaborar: ${type}` });
    setLoading(true);

    try {
      const resp = await api("/api/pipeline/set-type", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, doc_type: type, context: sourceMessage || type }),
      });
      const data = await resp.json();
      addMessage({
        role: "assistant", type: "questions",
        thinking: data.thinking,
        thinking_summary: data.thinking_summary,
        questions: data.questions,
      });
    } catch (e) {
      addMessage({ role: "system", type: "text", content: `⚠️ ${e.message}` });
    }
    setLoading(false);
  };

  const handleQuestionSubmit = async (roundAnswers) => {
    const merged = { ...allAnswers, ...roundAnswers };
    setAllAnswers(merged);

    addMessage({
      role: "user", type: "text",
      content: Object.entries(roundAnswers).map(([q, a]) => `• ${q}: ${Array.isArray(a) ? a.join(", ") : a}`).join("\n"),
    });

    setLoading(true);
    try {
      const resp = await api("/api/pipeline/answer", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, answers: roundAnswers }),
      });
      const data = await resp.json();

      if (data.action === "more_questions") {
        addMessage({
          role: "assistant", type: "text",
          content: "Preciso de mais algumas informações para refinar o documento:",
        });
        addMessage({
          role: "assistant", type: "questions",
          thinking: data.thinking,
          questions: data.questions,
        });
      } else if (data.action === "outline") {
        setOutline(data.outline);
        setStage("outline");
        addMessage({
          role: "assistant", type: "text",
          content: "Aqui está o roteiro estruturado do documento. Revise e aprove para iniciar a redação:",
        });
        addMessage({
          role: "assistant", type: "outline",
          thinking: data.thinking,
          outline: data.outline,
        });
      }
    } catch (e) {
      addMessage({ role: "system", type: "text", content: `⚠️ ${e.message}` });
    }
    setLoading(false);
  };

  const handleOutlineApprove = async () => {
    setStage("document");
    addMessage({ role: "user", type: "text", content: "✅ Roteiro aprovado. Pode gerar o documento." });
    addMessage({ role: "assistant", type: "text", content: "Gerando o documento seção por seção..." });
    setLoading(true);

    try {
      const resp = await fetch(`${API_BASE}/api/pipeline/generate-document/${sessionId}`, { method: "POST" });
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      const allSections = [];

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
            if (event.type === "section") {
              allSections.push(event.data);
              addMessage({
                role: "assistant", type: "document_section",
                thinking: event.thinking,
                section: event.data,
              });
            } else if (event.type === "progress") {
              // Update loading indicator
            }
          } catch { }
        }
      }

      addMessage({
        role: "assistant", type: "text",
        content: `✅ Documento completo — ${allSections.length} seções geradas. Você pode copiar acima ou me pedir ajustes em qualquer seção.`,
      });
    } catch (e) {
      addMessage({ role: "system", type: "text", content: `⚠️ ${e.message}` });
    }
    setLoading(false);
  };

  const handleOutlineRegenerate = async () => {
    setLoading(true);
    try {
      const resp = await api(`/api/pipeline/regenerate-outline/${sessionId}`, { method: "POST" });
      const data = await resp.json();
      setOutline(data.outline);
      addMessage({
        role: "assistant", type: "outline",
        thinking: data.thinking,
        outline: data.outline,
      });
    } catch (e) {
      addMessage({ role: "system", type: "text", content: `⚠️ ${e.message}` });
    }
    setLoading(false);
  };

  const handleChatSend = async () => {
    if (!input.trim() || loading) return;
    const msg = input.trim();
    setInput("");

    const detectedType = detectDocumentType(msg);
    if (detectedType) {
      return handleSelectType(detectedType.label, msg);
    }

    // Check if user typed a doc type directly
    if (stage === "select_type") {
      const match = DOC_TYPES.find(d => msg.toLowerCase().includes(d.label.toLowerCase()));
      if (match) {
        return handleSelectType(match.label, msg);
      }
      // Treat as custom type or free chat
      return handleSelectType(msg, msg);
    }

    addMessage({ role: "user", type: "text", content: msg });
    setLoading(true);
    try {
      const resp = await api("/api/chat", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, message: msg }),
      });
      const data = await resp.json();
      addMessage({
        role: "assistant", type: "text",
        thinking: data.thinking,
        content: data.response || data.message?.content || data.message?.detail || data.error || "Resposta vazia do servidor.",
      });
    } catch (e) {
      addMessage({ role: "system", type: "text", content: `⚠️ ${typeof e.message === "string" ? e.message : JSON.stringify(e.message)}` });
    }
    setLoading(false);
  };

  const handleAttachRef = async (doc) => {
    try {
      if (doc.source === "upload") {
        setReferences(prev => [...prev, { name: doc.name, item_id: doc.id }]);
        addMessage({ role: "system", type: "text", content: `📎 Arquivo "${doc.name}" enviado como referência da sessão.` });
        return;
      }

      const resp = await api("/api/sharepoint/attach", {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionId,
          drive_id: doc.drive_id,
          item_id: doc.id,
          name: doc.name,
        }),
      });
      const data = await resp.json();
      setReferences(prev => [...prev, { name: doc.name, item_id: doc.id }]);
      addMessage({ role: "system", type: "text", content: `📎 Modelo "${doc.name}" anexado como referência de estilo.` });
    } catch (e) {
      addMessage({ role: "system", type: "text", content: `⚠️ Erro ao anexar: ${e.message}` });
    }
  };

  const handleDetachRef = async (itemId) => {
    try {
      await api(`/api/sharepoint/detach/${sessionId}/${itemId}`, { method: "DELETE" });
      setReferences(prev => prev.filter(r => r.item_id !== itemId));
    } catch (e) {
      console.error(e);
    }
  };

  // ─── Render ────────────────────────────────────────

  return (
    <div style={{
      height: "100vh",
      display: "flex",
      background: "#0b0910",
      color: "#e0d6f0",
      fontFamily: "'DM Sans', system-ui, sans-serif",
      overflow: "hidden",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=JetBrains+Mono:wght@400;500&display=swap');
        :root {
          --accent: #7c3aed;
          --accent-light: #a78bfa;
          --bg-deep: #0b0910;
          --bg-surface: rgba(255,255,255,0.03);
          --border: rgba(255,255,255,0.06);
          --text: #e0d6f0;
          --text-dim: #b0a6c4;
          --mono: 'JetBrains Mono', monospace;
          --display: 'Fraunces', serif;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(124,58,237,0.25); border-radius: 3px; }
        @keyframes msgIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0%,100% { opacity: 0.4; } 50% { opacity: 1; } }
      `}</style>

      {/* ─── Sidebar ─── */}
      <div style={{
        width: sidebarOpen ? 260 : 0,
        flexShrink: 0,
        background: "rgba(255,255,255,0.015)",
        borderRight: sidebarOpen ? "1px solid var(--border)" : "none",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        transition: "width 0.2s",
      }}>
        <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--border)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 30, height: 30, borderRadius: 7, background: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>⚖️</div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, fontFamily: "var(--display)" }}>PetiçãoAI + JurisGen</div>
              <div style={{ fontSize: 10, color: "rgba(255,255,255,0.3)" }}>Gerador Adaptativo Unificado</div>
            </div>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "12px 14px" }}>
          <SharePointPanel
            sessionId={sessionId}
            references={references}
            onAttach={handleAttachRef}
            onDetach={handleDetachRef}
          />

          {/* Session info */}
          <div style={{ fontSize: 11, color: "rgba(255,255,255,0.25)", marginTop: 12 }}>
            <div style={{ fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>Sessão</div>
            <div>Tipo: {docType || "—"}</div>
            <div>Estágio: {stage}</div>
            <div>Respostas: {Object.keys(allAnswers).length}</div>
            <div>Referências: {references.length}</div>
          </div>
        </div>
      </div>

      {/* ─── Main Chat Area ─── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Header */}
        <div style={{
          padding: "10px 16px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}>
          <button onClick={() => setSidebarOpen(!sidebarOpen)} style={{
            background: "none", border: "none", color: "rgba(255,255,255,0.4)", cursor: "pointer", fontSize: 18, padding: "4px",
          }}>
            {sidebarOpen ? "◀" : "▶"}
          </button>
          <span style={{ fontSize: 13, color: "rgba(255,255,255,0.5)" }}>
            {docType ? `📄 ${docType}` : "Novo documento"}
          </span>
          {stage !== "select_type" && (
            <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
              {["select_type", "questions", "outline", "document"].map((s, i) => (
                <div key={s} style={{
                  width: 8, height: 8, borderRadius: "50%",
                  background: ["select_type", "questions", "outline", "document"].indexOf(stage) >= i ? "var(--accent)" : "rgba(255,255,255,0.08)",
                  transition: "background 0.2s",
                }} />
              ))}
            </div>
          )}
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px 16px" }}>
          {llmStatus && llmStatus.provider === "claude_cli" && (
            <div style={{ marginBottom: 16, padding: "10px 12px", borderRadius: 10, background: llmStatus.available ? "rgba(59,130,246,0.08)" : "rgba(251,191,36,0.08)", border: llmStatus.available ? "1px solid rgba(59,130,246,0.22)" : "1px solid rgba(251,191,36,0.2)", color: llmStatus.available ? "#93c5fd" : "#fbbf24", fontSize: 12.5, lineHeight: 1.55 }}>
              <strong>Claude CLI ativo:</strong> {llmStatus.message || "o backend está configurado para usar o Claude via CLI."}
              {!llmStatus.available && <div style={{ marginTop: 4 }}>Se o chat falhar, faça login no Claude Code ou aguarde o reset da cota.</div>}
            </div>
          )}

          {/* Type selector shown inline if no type yet */}
          {stage === "select_type" && messages.length <= 1 && (
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontSize: 12, color: "rgba(255,255,255,0.3)", marginBottom: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Tipos de documento</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {DOC_TYPES.map(d => (
                  <button key={d.id} onClick={() => handleSelectType(d.label)} style={{
                    padding: "8px 14px", background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)", borderRadius: 20,
                    color: "var(--text-dim)", cursor: "pointer", fontSize: 13, display: "flex", alignItems: "center", gap: 6, transition: "all 0.15s", whiteSpace: "nowrap",
                  }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(124,58,237,0.4)"; e.currentTarget.style.background = "rgba(124,58,237,0.08)"; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)"; e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}
                  >
                    <span>{d.icon}</span> {d.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <ChatMessage
              key={i}
              msg={msg}
              onQuestionSubmit={handleQuestionSubmit}
              onOutlineApprove={handleOutlineApprove}
              onOutlineRegenerate={handleOutlineRegenerate}
            />
          ))}

          {loading && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 0", animation: "pulse 1.5s infinite" }}>
              <div style={{ display: "flex", gap: 4 }}>
                {[0, 1, 2].map(i => (
                  <div key={i} style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent-light)", animation: `pulse 1.2s infinite ${i * 0.2}s` }} />
                ))}
              </div>
              <span style={{ fontSize: 12, color: "rgba(255,255,255,0.3)" }}>Pensando...</span>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        {/* Input bar */}
        <div style={{
          padding: "12px 16px",
          borderTop: "1px solid var(--border)",
          background: "rgba(255,255,255,0.015)",
        }}>
          <div style={{
            display: "flex",
            gap: 8,
            alignItems: "flex-end",
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: 12,
            padding: "4px 4px 4px 14px",
          }}>
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => {
                setInput(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
              }}
              onKeyDown={e => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleChatSend();
                }
              }}
              placeholder={stage === "select_type" ? "Digite o tipo de documento ou descreva o que precisa..." : "Digite sua mensagem ou dúvida..."}
              rows={1}
              style={{
                flex: 1,
                background: "none",
                border: "none",
                color: "var(--text)",
                fontSize: 14,
                lineHeight: 1.5,
                resize: "none",
                outline: "none",
                padding: "8px 0",
                maxHeight: 120,
                fontFamily: "inherit",
              }}
            />
            <button
              onClick={handleChatSend}
              disabled={!input.trim() || loading}
              style={{
                width: 36, height: 36,
                borderRadius: 8,
                background: input.trim() && !loading ? "var(--accent)" : "rgba(255,255,255,0.05)",
                border: "none",
                color: input.trim() && !loading ? "#fff" : "rgba(255,255,255,0.2)",
                cursor: input.trim() && !loading ? "pointer" : "not-allowed",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 16,
                flexShrink: 0,
                transition: "all 0.15s",
              }}
            >
              ↑
            </button>
          </div>
          <div style={{ fontSize: 11, color: "rgba(255,255,255,0.2)", marginTop: 6, textAlign: "center" }}>
            Enter para enviar · Shift+Enter para quebrar linha · Anexe modelos do SharePoint na barra lateral
          </div>
        </div>
      </div>
    </div>
  );
}

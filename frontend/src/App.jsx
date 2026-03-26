import { useCallback, useEffect, useRef, useState } from "react";

const API = import.meta.env.VITE_API_BASE || "";

async function api(path, opts = {}) {
  const ctrl = new AbortController();
  const tid = setTimeout(() => ctrl.abort(), 180000);
  try {
    const r = await fetch(`${API}${path}`, {
      headers: { "Content-Type": "application/json", ...opts.headers },
      signal: ctrl.signal, ...opts,
    });
    if (!r.ok) {
      const e = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(typeof e.detail === "string" ? e.detail : JSON.stringify(e.detail));
    }
    return r;
  } finally { clearTimeout(tid); }
}

/* ════════════════════════ Small UI Atoms ════════════════════════ */

function Toggle({ on, onChange }) {
  return (
    <div onClick={() => onChange(!on)} style={{
      width: 40, height: 22, borderRadius: 11, background: on ? "#22c55e" : "rgba(255,255,255,0.15)",
      cursor: "pointer", position: "relative", transition: "background 0.2s", flexShrink: 0
    }}>
      <div style={{ width: 16, height: 16, borderRadius: "50%", background: "#fff", position: "absolute", top: 3, left: on ? 21 : 3, transition: "left 0.2s" }} />
    </div>
  );
}

function Pill({ options, value, onChange }) {
  return (
    <div style={{ display: "flex", background: "rgba(255,255,255,0.05)", borderRadius: 8, overflow: "hidden" }}>
      {options.map(o => (
        <button key={o.id} onClick={() => onChange(o.id)} style={{
          flex: 1, padding: "8px 4px", fontSize: 12, fontWeight: value === o.id ? 700 : 500, border: "none", cursor: "pointer",
          background: value === o.id ? "rgba(255,255,255,0.1)" : "transparent",
          color: value === o.id ? "#fff" : "rgba(255,255,255,0.35)", transition: "all 0.15s"
        }}>
          {o.icon && <span style={{ marginRight: 4 }}>{o.icon}</span>}{o.label}
          {o.rec && <div style={{ fontSize: 9, color: "rgba(255,255,255,0.3)", fontWeight: 400 }}>Recomendado</div>}
        </button>
      ))}
    </div>
  );
}

function FeatureRow({ icon, label, desc, on, onChange }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 0", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
      <span style={{ fontSize: 20, width: 32, textAlign: "center" }}>{icon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#fff" }}>{label}</div>
        <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)" }}>{desc}</div>
      </div>
      <Toggle on={on} onChange={onChange} />
    </div>
  );
}

function Dot({ color, label }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4, marginRight: 10 }}>
      <span style={{ width: 7, height: 7, borderRadius: "50%", background: color }} />
      <span style={{ fontSize: 11, color: "rgba(255,255,255,0.5)" }}>{label}</span>
    </span>
  );
}

/* ════════════════════════ Reasoning Panel ════════════════════════ */

const REASONING_SETS = {
  analyzing: [
    { title: "Análise da Solicitação Jurídica", desc: "Estou analisando o tipo de documento solicitado e identificando os requisitos jurídicos específicos para esta peça processual." },
    { title: "Identificando Requisitos Processuais", desc: "Estou concentrando-me nos requisitos legais específicos, buscando clareza e precisão jurídica para elaborar o documento." },
    { title: "Formulando Perguntas Iniciais", desc: "Estou priorizando as perguntas de esclarecimento essenciais antes de redigir. Foco nos fatos, fundamentação e pedidos." },
    { title: "Definindo Estratégia de Elaboração", desc: "Estou definindo a estratégia de abordagem, considerando a legislação aplicável e a jurisprudência relevante." },
  ],
  adjusting: [
    { title: "Processando Respostas", desc: "Estou integrando as informações específicas fornecidas pelo usuário para personalizar o documento." },
    { title: "Ajustando a Abordagem", desc: "Estou refinando a estratégia jurídica com base nas respostas, considerando as particularidades do caso concreto." },
    { title: "Ajustando as Perguntas", desc: "Estou refinando as perguntas de esclarecimento, garantindo que o plano reflita todas as informações fornecidas." },
  ],
  outlining: [
    { title: "Estruturando o Documento", desc: "Estou preparando o conteúdo, completando o plano com subtópicos detalhados e objetivos para cada seção." },
    { title: "Desenvolvendo a Estrutura da Petição", desc: "Estou refinando a estrutura detalhada. As seções principais estão estabelecidas, incluindo a identificação das partes, os argumentos e os pedidos." },
    { title: "Finalizando o Plano do Documento", desc: "Estou implementando a estrutura, incluindo todas as questões, as etapas do plano e seus objetivos. A estrutura está pronta para a geração do documento." },
  ],
};

function ReasoningPanel({ steps, expanded, onToggle }) {
  if (!steps || steps.length === 0) return null;
  const last = steps[steps.length - 1];
  return (
    <div style={{ margin: "16px 0" }}>
      <div onClick={onToggle} style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", padding: "8px 0" }}>
        <span style={{ width: 16, height: 16, borderRadius: "50%", border: "2px solid rgba(255,255,255,0.2)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 8 }}>○</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: "rgba(255,255,255,0.5)", letterSpacing: 0.5 }}>PROCESSO DE RACIOCÍNIO ({steps.length})</span>
        <span style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", marginLeft: "auto" }}>{expanded ? "Recolher ∧" : "Expandir ∨"}</span>
      </div>
      {expanded ? (
        steps.map((s, i) => (
          <div key={i} style={{ padding: "10px 0 10px 24px", borderLeft: "2px solid rgba(255,255,255,0.06)", marginLeft: 7 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "rgba(255,255,255,0.7)", marginBottom: 4 }}>{i + 1}. {s.title}</div>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", lineHeight: 1.5 }}>{s.desc}</div>
          </div>
        ))
      ) : (
        <div style={{ padding: "10px 0 10px 24px", borderLeft: "2px solid rgba(255,255,255,0.06)", marginLeft: 7 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "rgba(255,255,255,0.7)", marginBottom: 4 }}>{steps.length}. {last.title}</div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", lineHeight: 1.5 }}>{last.desc}</div>
        </div>
      )}
    </div>
  );
}

/* ════════════════════════ Status Bar ════════════════════════ */

function StatusBar({ features, startTime }) {
  const elapsed = startTime ? Math.floor((Date.now() - startTime) / 1000) : 0;
  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");
  return (
    <div style={{ padding: "8px 16px", background: "rgba(255,255,255,0.02)", borderRadius: 8, marginBottom: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 11, color: "rgba(255,255,255,0.4)", marginBottom: 6 }}>
        <span>⚡ resposta longa</span>
        <span>pensamento médio</span>
        <span style={{ marginLeft: "auto" }}>{mm}:{ss}</span>
      </div>
      <div>
        <Dot color={features.jurisprudencia ? "#22c55e" : "rgba(255,255,255,0.2)"} label="Jurisprudência" />
        <Dot color={features.legislacao ? "#22c55e" : "rgba(255,255,255,0.2)"} label="Legislação" />
        <Dot color={features.modelos ? "#22c55e" : "rgba(255,255,255,0.2)"} label="Modelos" />
        <Dot color={features.contadoria ? "#22c55e" : "rgba(255,255,255,0.2)"} label="Contadoria" />
        <Dot color="#22c55e" label="Contexto inteligente" />
      </div>
      <div style={{ marginTop: 4 }}>
        <Dot color={features.perguntas ? "#22c55e" : "rgba(255,255,255,0.2)"} label="Perguntas" />
        <Dot color={features.roteiro ? "#22c55e" : "rgba(255,255,255,0.2)"} label="Roteiro" />
      </div>
    </div>
  );
}

/* ════════════════════════ Answers Card ════════════════════════ */

function AnswersCard({ answers }) {
  const entries = Object.entries(answers);
  if (entries.length === 0) return null;
  return (
    <div style={{ background: "rgba(34,197,94,0.05)", border: "1px solid rgba(34,197,94,0.15)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 20, height: 20, borderRadius: "50%", background: "#22c55e", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: "#fff" }}>✓</div>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#fff" }}>Respostas fornecidas</span>
        </div>
        <span style={{ fontSize: 12, color: "#22c55e", fontWeight: 600 }}>{entries.length} respostas</span>
      </div>
      {entries.map(([q, a], i) => (
        <div key={i} style={{ display: "flex", gap: 10, padding: "8px 0", borderTop: i > 0 ? "1px solid rgba(255,255,255,0.04)" : "none" }}>
          <div style={{ width: 22, height: 22, borderRadius: "50%", background: "#22c55e", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, flexShrink: 0 }}>{i + 1}</div>
          <div>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,0.5)", marginBottom: 2 }}>{q}</div>
            <div style={{ fontSize: 13, color: "#22c55e", fontWeight: 600 }}>{String(a)}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ════════════════════════ Question Form ════════════════════════ */

function QuestionForm({ questions, onSubmit }) {
  const safeQ = Array.isArray(questions) ? questions : [];
  const [answers, setAnswers] = useState({});
  const set = (id, val) => setAnswers(p => ({ ...p, [id]: val }));
  const answered = Object.keys(answers).filter(k => { const v = answers[k]; return v && (typeof v === "string" ? v.trim() : true); }).length;
  const required = safeQ.filter(q => q.required !== false).length;

  const norm = (o) => {
    if (typeof o === "string") return { id: o, label: o };
    return { id: o.id ?? o.label ?? "o", label: o.label ?? o.text ?? "Opção", desc: o.desc || "" };
  };

  return (
    <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 12, padding: 20, marginTop: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <span style={{ fontSize: 16 }}>⊙</span>
        <span style={{ fontSize: 14, fontWeight: 700, color: "#fff" }}>Preciso de algumas informações</span>
      </div>
      <p style={{ fontSize: 12, color: "rgba(255,255,255,0.4)", marginBottom: 20, paddingLeft: 24 }}>
        Responda às perguntas abaixo para eu elaborar o documento com mais precisão.
      </p>
      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", marginBottom: 16, paddingLeft: 24 }}>{answered}/{safeQ.length}</div>

      {safeQ.map((q, idx) => {
        const opts = Array.isArray(q.options) ? q.options.map(norm) : [];
        return (
          <div key={q.id} style={{ marginBottom: 20, paddingLeft: 8 }}>
            <div style={{ display: "flex", gap: 10, marginBottom: 8 }}>
              <div style={{
                width: 24, height: 24, borderRadius: "50%", flexShrink: 0,
                background: answers[q.id] ? "#22c55e" : "rgba(167,139,250,0.2)",
                color: answers[q.id] ? "#fff" : "#a78bfa",
                display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700
              }}>{idx + 1}</div>
              <div style={{ fontSize: 13, color: "rgba(255,255,255,0.75)", lineHeight: 1.4 }}>
                {q.text}{q.required !== false && <span style={{ color: "#ef4444" }}>*</span>}
              </div>
            </div>
            <div style={{ paddingLeft: 34 }}>
              {(q.type === "choice" || q.type === "multiple") && opts.length > 0 ? (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {opts.map(o => {
                    const sel = q.type === "multiple"
                      ? (answers[q.id] || []).includes(o.label)
                      : answers[q.id] === o.label;
                    return (
                      <button key={o.id} onClick={() => {
                        if (q.type === "multiple") {
                          const cur = answers[q.id] || [];
                          set(q.id, sel ? cur.filter(x => x !== o.label) : [...cur, o.label]);
                        } else {
                          set(q.id, o.id === "other" ? "" : o.label);
                        }
                      }} style={{
                        padding: "7px 16px", borderRadius: 20, fontSize: 12, cursor: "pointer",
                        border: sel ? "1px solid #22c55e" : "1px solid rgba(255,255,255,0.1)",
                        background: sel ? "rgba(34,197,94,0.1)" : "rgba(255,255,255,0.03)",
                        color: sel ? "#22c55e" : "rgba(255,255,255,0.5)", fontWeight: sel ? 600 : 400
                      }}>
                        {o.label}
                      </button>
                    );
                  })}
                  {answers[q.id] === "" && (
                    <input autoFocus placeholder="Especifique..." onChange={e => set(q.id, e.target.value)}
                      style={{ flex: 1, minWidth: 160, padding: "7px 14px", borderRadius: 20, border: "1px solid rgba(255,255,255,0.1)", background: "rgba(255,255,255,0.03)", color: "#fff", fontSize: 12, outline: "none" }} />
                  )}
                </div>
              ) : (
                <textarea value={answers[q.id] || ""} onChange={e => set(q.id, e.target.value)}
                  placeholder={q.placeholder || "Digite sua resposta..."}
                  rows={2} style={{
                    width: "100%", padding: "10px 14px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.06)",
                    background: "rgba(255,255,255,0.02)", color: "#fff", fontSize: 12.5, resize: "vertical",
                    outline: "none", fontFamily: "inherit", lineHeight: 1.5
                  }} />
              )}
            </div>
          </div>
        );
      })}

      <div style={{ display: "flex", justifyContent: "flex-end", paddingTop: 12, borderTop: "1px solid rgba(255,255,255,0.04)" }}>
        <button onClick={() => {
          const final = {};
          safeQ.forEach(q => { if (answers[q.id]) final[q.text || q.id] = typeof answers[q.id] === "object" ? answers[q.id].join(", ") : answers[q.id]; });
          if (Object.keys(final).length > 0) onSubmit(final);
        }} disabled={answered < 1} style={{
          padding: "10px 24px", borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: answered < 1 ? "not-allowed" : "pointer",
          background: answered >= 1 ? "var(--accent)" : "rgba(255,255,255,0.05)",
          border: "none", color: answered >= 1 ? "#fff" : "rgba(255,255,255,0.3)",
          display: "flex", alignItems: "center", gap: 6
        }}>
          Continuar <span>→</span>
        </button>
      </div>
    </div>
  );
}

/* ════════════════════════ Outline Editor ════════════════════════ */

function OutlineSection({ section, index, total, onEdit, onDelete, onDuplicate, onMove }) {
  const [expanded, setExpanded] = useState(true);
  const _subs = section.subtopics || section.sub_topics || []; const subs = Array.isArray(_subs) ? _subs : typeof _subs === 'string' ? [_subs] : [];
  return (
    <div style={{
      background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)",
      borderRadius: 12, padding: 16, marginBottom: 10, transition: "all 0.15s"
    }}>
      <div style={{ display: "flex", gap: 12 }}>
        <div style={{
          width: 28, height: 28, borderRadius: "50%", background: "rgba(167,139,250,0.15)", color: "#a78bfa",
          display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 700, flexShrink: 0, cursor: "grab"
        }}>{index + 1}</div>
        <div style={{ flex: 1 }}>
          <h4 style={{ fontSize: 14, fontWeight: 700, color: "#fff", margin: "0 0 6px", lineHeight: 1.3 }}>{section.title}</h4>
          <p style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", margin: "0 0 10px", lineHeight: 1.5 }}>{section.description}</p>
          {subs.length > 0 && (
            <div>
              <div onClick={() => setExpanded(!expanded)} style={{ fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,0.5)", cursor: "pointer", marginBottom: 6 }}>
                Subtópicos {expanded ? "▾" : "▸"}
              </div>
              {expanded && subs.map((s, i) => (
                <div key={i} style={{ fontSize: 12, color: "rgba(255,255,255,0.5)", padding: "3px 0 3px 12px", borderLeft: "2px solid rgba(167,139,250,0.15)" }}>
                  {typeof s === "string" ? s : s.title || s.text || JSON.stringify(s)}
                </div>
              ))}
            </div>
          )}
          {section.legal_basis?.length > 0 && (
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 8 }}>
              {section.legal_basis.map((l, j) => (
                <span key={j} style={{ fontSize: 10, padding: "2px 8px", borderRadius: 4, background: "rgba(251,191,36,0.06)", color: "#fbbf24", border: "1px solid rgba(251,191,36,0.12)" }}>{l}</span>
              ))}
            </div>
          )}
        </div>
      </div>
      <div style={{ display: "flex", gap: 6, justifyContent: "flex-end", marginTop: 10, paddingTop: 8, borderTop: "1px solid rgba(255,255,255,0.04)" }}>
        {index > 0 && <button onClick={() => onMove(index, index - 1)} style={btnSmall}>↑</button>}
        {index < total - 1 && <button onClick={() => onMove(index, index + 1)} style={btnSmall}>↓</button>}
        <span style={{ flex: 1 }} />
        <button onClick={() => onDuplicate(index)} style={btnSmall}>Duplicar</button>
        <button onClick={() => onDelete(index)} style={{ ...btnSmall, color: "#ef4444", borderColor: "rgba(239,68,68,0.2)" }}>Excluir</button>
      </div>
    </div>
  );
}

const btnSmall = {
  padding: "4px 10px", fontSize: 11, borderRadius: 6, cursor: "pointer",
  background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)",
  color: "rgba(255,255,255,0.5)", fontWeight: 500
};

/* ════════════════════════ Legislation Panel ════════════════════════ */

function LegislationPanel({ sources, onClose }) {
  const [expandedIdx, setExpandedIdx] = useState(-1);
  if (!sources || sources.length === 0) return null;
  const totalResults = sources.reduce((acc, s) => acc + (s.results?.length || 0), 0);
  return (
    <div style={{
      position: "fixed", top: 0, right: 0, width: 480, height: "100vh", background: "#0f0f17",
      borderLeft: "1px solid rgba(255,255,255,0.08)", zIndex: 100, display: "flex", flexDirection: "column",
      boxShadow: "-4px 0 20px rgba(0,0,0,0.5)"
    }}>
      <div style={{ padding: 20, borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 20 }}>📖</span>
            <div>
              <h3 style={{ fontSize: 15, fontWeight: 700, color: "#fff", margin: 0 }}>Consultas de Legislação</h3>
              <p style={{ fontSize: 12, color: "rgba(255,255,255,0.4)", margin: 0 }}>
                {sources.length} consulta(s) realizadas com {totalResults} resultado(s)
              </p>
            </div>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "rgba(255,255,255,0.4)", cursor: "pointer", fontSize: 18 }}>×</button>
        </div>
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: 16 }}>
        {sources.map((s, i) => (
          <div key={i} style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 14, marginBottom: 8 }}>
            <div onClick={() => setExpandedIdx(expandedIdx === i ? -1 : i)} style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
              <span style={{ fontSize: 16 }}>📖</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#fff" }}>Consulta #{i + 1}</span>
              <span style={{ fontSize: 11, color: "#22c55e", background: "rgba(34,197,94,0.1)", padding: "2px 8px", borderRadius: 10 }}>
                {s.results?.length || 0} resultado(s)
              </span>
              <span style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", marginLeft: "auto" }}>⏱ {s.time || "0.2s"}</span>
              <span style={{ color: "rgba(255,255,255,0.3)", fontSize: 12 }}>{expandedIdx === i ? "∧" : "∨"}</span>
            </div>
            {s.source && <div style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", marginTop: 4, paddingLeft: 26 }}>📖 {s.source}</div>}
            {expandedIdx === i && s.results?.map((r, j) => (
              <div key={j} style={{ marginTop: 8, padding: "8px 10px", background: "rgba(255,255,255,0.02)", borderRadius: 6, marginLeft: 26 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#fff" }}>{r.title || r.law || "Referência"}</div>
                {r.text && <div style={{ fontSize: 11, color: "rgba(255,255,255,0.45)", marginTop: 4, lineHeight: 1.5 }}>{r.text.substring(0, 300)}</div>}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ════════════════════════ Verification Popup ════════════════════════ */

function VerificationPopup({ source, position, onClose }) {
  if (!source) return null;
  return (
    <div style={{
      position: "absolute", top: position?.top || 0, left: position?.left || 0, zIndex: 200,
      background: "#1a1a2e", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10,
      padding: 16, width: 360, boxShadow: "0 8px 32px rgba(0,0,0,0.6)"
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span style={{ color: "#22c55e", fontSize: 14 }}>✓</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: "#fff" }}>Conteúdo Verificado</span>
        <span style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", marginLeft: 8 }}>Apenas Referência</span>
        <button onClick={onClose} style={{ marginLeft: "auto", background: "none", border: "none", color: "rgba(255,255,255,0.4)", cursor: "pointer" }}>×</button>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 10px", background: "rgba(255,255,255,0.03)", borderRadius: 6, marginBottom: 10 }}>
        <span style={{ fontSize: 12, color: "#fbbf24", fontWeight: 600 }}>{source.law || source.title || "Lei"}</span>
        {source.url && (
          <a href={source.url} target="_blank" rel="noreferrer" style={{ marginLeft: "auto", fontSize: 11, color: "#a78bfa", textDecoration: "none", display: "flex", alignItems: "center", gap: 4 }}>
            ↗ Abrir Fonte
          </a>
        )}
      </div>
      {source.article && <div style={{ fontSize: 13, fontWeight: 600, color: "#fff", marginBottom: 6 }}>{source.article}</div>}
      {source.text && <div style={{ fontSize: 12, color: "rgba(255,255,255,0.55)", lineHeight: 1.5 }}>{source.text.substring(0, 400)}</div>}
    </div>
  );
}

/* ════════════════════════ Historico Panel ════════════════════════ */

function HistoricoPanel({ history, onReopen }) {
  if (history.length === 0) {
    return (
      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "rgba(255,255,255,0.3)" }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>📋</div>
        <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>Nenhum histórico ainda</div>
        <div style={{ fontSize: 13 }}>Seus documentos gerados aparecerão aqui</div>
      </div>
    );
  }
  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 32 }}>
      <h2 style={{ fontSize: 20, fontWeight: 800, color: "#fff", marginBottom: 24 }}>Histórico de documentos</h2>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 720, margin: "0 auto" }}>
        {history.map(h => (
          <div key={h.id} style={{
            background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)",
            borderRadius: 12, padding: "16px 20px", display: "flex", alignItems: "center", gap: 16
          }}>
            <div style={{ width: 40, height: 40, borderRadius: 10, background: "rgba(167,139,250,0.15)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, flexShrink: 0 }}>📄</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#fff", marginBottom: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{h.title}</div>
              <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)" }}>{h.date}{h.sections ? ` · ${h.sections} seções` : ""}</div>
            </div>
            {onReopen && (
              <button onClick={() => onReopen(h)} style={{
                padding: "6px 14px", borderRadius: 8, background: "rgba(167,139,250,0.1)",
                border: "1px solid rgba(167,139,250,0.2)", color: "#a78bfa", fontSize: 12, cursor: "pointer", fontWeight: 600
              }}>Reabrir</button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ════════════════════════ Modelos Panel ════════════════════════ */

const MODELOS = [
  { icon: "⚖️", cat: "Contencioso", items: ["Petição Inicial - Danos Morais", "Contestação", "Recurso Ordinário", "Agravo de Instrumento", "Embargos de Declaração"] },
  { icon: "📑", cat: "Trabalhista", items: ["Reclamação Trabalhista", "Defesa Trabalhista", "Acordo Extrajudicial", "Homologação de Rescisão", "Recurso de Revista"] },
  { icon: "🏢", cat: "Empresarial", items: ["Contrato de Prestação de Serviços", "Contrato Social", "Distrato", "Procuração", "Notificação Extrajudicial"] },
  { icon: "🏠", cat: "Imobiliário", items: ["Contrato de Locação", "Ação de Despejo", "Usucapião", "Contrato de Compra e Venda", "Instrumento de Promessa"] },
  { icon: "👨‍👩‍👧", cat: "Família", items: ["Divórcio Consensual", "Alimentos", "Guarda de Filhos", "Inventário", "Testamento"] },
  { icon: "💻", cat: "Consumidor", items: ["Ação de Consumidor - Produto Defeituoso", "Dano Moral Bancário", "Fraude de Cartão", "Cobranças Indevidas", "Rescisão de Contrato"] },
];

function ModelosPanel({ onSelect }) {
  const [search, setSearch] = useState("");
  const filtered = MODELOS.map(cat => ({
    ...cat,
    items: cat.items.filter(i => !search || i.toLowerCase().includes(search.toLowerCase()))
  })).filter(cat => cat.items.length > 0);

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 32 }}>
      <h2 style={{ fontSize: 20, fontWeight: 800, color: "#fff", marginBottom: 8 }}>Modelos de documentos</h2>
      <p style={{ fontSize: 13, color: "rgba(255,255,255,0.4)", marginBottom: 24 }}>Clique para gerar um documento com este modelo como ponto de partida</p>
      <input value={search} onChange={e => setSearch(e.target.value)}
        placeholder="Buscar modelo..."
        style={{ width: "100%", maxWidth: 480, padding: "10px 14px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)", color: "#fff", fontSize: 13, outline: "none", marginBottom: 28 }} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16, maxWidth: 960, margin: "0 auto" }}>
        {filtered.map(cat => (
          <div key={cat.cat} style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 14, overflow: "hidden" }}>
            <div style={{ padding: "14px 16px", borderBottom: "1px solid rgba(255,255,255,0.05)", display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 18 }}>{cat.icon}</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: "#fff" }}>{cat.cat}</span>
            </div>
            {cat.items.map(item => (
              <button key={item} onClick={() => onSelect(item)} style={{
                display: "block", width: "100%", padding: "10px 16px", background: "none", border: "none",
                color: "rgba(255,255,255,0.65)", fontSize: 12, textAlign: "left", cursor: "pointer",
                borderBottom: "1px solid rgba(255,255,255,0.03)", transition: "all 0.15s"
              }}
                onMouseEnter={e => { e.currentTarget.style.background = "rgba(167,139,250,0.08)"; e.currentTarget.style.color = "#a78bfa"; }}
                onMouseLeave={e => { e.currentTarget.style.background = "none"; e.currentTarget.style.color = "rgba(255,255,255,0.65)"; }}>
                {item}
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ════════════════════════ Referencias Panel ════════════════════════ */

function ReferenciasPanel() {
  const [query, setQuery] = useState("");
  const [tribunal, setTribunal] = useState("tst");
  const [results, setResults] = useState([]);
  const [ragResults, setRagResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("cnj");

  const searchCnj = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setResults([]);
    try {
      const r = await api("/api/cnj/search", { method: "POST", body: JSON.stringify({ tribunal, query, limit: 10 }) });
      const d = await r.json();
      setResults(d.resultados || []);
    } catch (e) { setResults([]); } finally { setLoading(false); }
  };

  const searchRag = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setRagResults([]);
    try {
      const r = await api("/api/rag/search", { method: "POST", body: JSON.stringify({ query, n_results: 8 }) });
      const d = await r.json();
      setRagResults(d.results || []);
    } catch (e) { setRagResults([]); } finally { setLoading(false); }
  };

  const doSearch = () => { if (tab === "cnj") searchCnj(); else searchRag(); };

  const TRIBUNAIS = [
    ["tst","TST"],["trf1","TRF1"],["trf2","TRF2"],["trf3","TRF3"],["trf4","TRF4"],["trf5","TRF5"],
    ["tjsp","TJSP"],["tjrj","TJRJ"],["tjmg","TJMG"],["tjrs","TJRS"],["tjpr","TJPR"],
  ];

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 32 }}>
      <h2 style={{ fontSize: 20, fontWeight: 800, color: "#fff", marginBottom: 8 }}>Referências jurídicas</h2>
      <p style={{ fontSize: 13, color: "rgba(255,255,255,0.4)", marginBottom: 24 }}>Busque jurisprudência no DataJud CNJ ou nos documentos indexados do escritório</p>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {[["cnj", "⚖️ Jurisprudência CNJ"], ["rag", "📚 Documentos do Escritório"]].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} style={{
            padding: "7px 16px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 13, fontWeight: 600,
            background: tab === id ? "rgba(167,139,250,0.15)" : "rgba(255,255,255,0.04)",
            color: tab === id ? "#a78bfa" : "rgba(255,255,255,0.5)"
          }}>{label}</button>
        ))}
      </div>

      {/* Search bar */}
      <div style={{ display: "flex", gap: 8, maxWidth: 720, marginBottom: 20 }}>
        {tab === "cnj" && (
          <select value={tribunal} onChange={e => setTribunal(e.target.value)} style={{
            padding: "10px 12px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.08)",
            background: "rgba(255,255,255,0.04)", color: "#fff", fontSize: 12, cursor: "pointer"
          }}>
            {TRIBUNAIS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        )}
        <input value={query} onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === "Enter" && doSearch()}
          placeholder={tab === "cnj" ? "Número do processo ou palavras-chave..." : "Busca semântica nos documentos indexados..."}
          style={{ flex: 1, padding: "10px 14px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)", color: "#fff", fontSize: 13, outline: "none" }} />
        <button onClick={doSearch} disabled={loading || !query.trim()} style={{
          padding: "10px 20px", borderRadius: 8, background: "#7c3aed", border: "none",
          color: "#fff", fontWeight: 700, cursor: "pointer", fontSize: 13, opacity: loading ? 0.6 : 1
        }}>{loading ? "..." : "Buscar"}</button>
      </div>

      {/* CNJ Results */}
      {tab === "cnj" && results.length > 0 && (
        <div style={{ maxWidth: 720, display: "flex", flexDirection: "column", gap: 10 }}>
          {results.map((r, i) => (
            <div key={i} style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 12, padding: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 6, background: "rgba(167,139,250,0.15)", color: "#a78bfa", fontWeight: 700 }}>{r.tribunal}</span>
                <span style={{ fontSize: 11, color: "rgba(255,255,255,0.4)" }}>{r.classe}</span>
                <span style={{ fontSize: 11, color: "rgba(255,255,255,0.25)", marginLeft: "auto" }}>{r.grau}</span>
              </div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#fff", marginBottom: 6, fontFamily: "monospace" }}>{r.numeroProcesso}</div>
              <div style={{ display: "flex", gap: 16, fontSize: 11, color: "rgba(255,255,255,0.4)" }}>
                <span>🏛️ {r.orgaoJulgador}</span>
                {r.assuntoPrincipal && <span>📌 {r.assuntoPrincipal}</span>}
                {r.dataAjuizamento && <span>📅 {r.dataAjuizamento?.slice(0, 10)}</span>}
              </div>
              {r.movimentos?.length > 0 && (
                <div style={{ marginTop: 8, fontSize: 11, color: "rgba(255,255,255,0.3)" }}>
                  Último: {r.movimentos[0]}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* RAG Results */}
      {tab === "rag" && ragResults.length > 0 && (
        <div style={{ maxWidth: 720, display: "flex", flexDirection: "column", gap: 10 }}>
          {ragResults.map((r, i) => (
            <div key={i} style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 12, padding: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 6, background: "rgba(34,197,94,0.1)", color: "#22c55e", fontWeight: 700 }}>score: {(r.score * 100).toFixed(0)}%</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: "#fff" }}>{r.filename}</span>
                {r.folder && <span style={{ fontSize: 11, color: "rgba(255,255,255,0.35)" }}>📁 {r.folder}</span>}
              </div>
              <div style={{ fontSize: 12, color: "rgba(255,255,255,0.65)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{r.text.slice(0, 400)}{r.text.length > 400 ? "..." : ""}</div>
              {r.web_url && (
                <a href={r.web_url} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: "#a78bfa", textDecoration: "none", display: "inline-block", marginTop: 8 }}>↗ Abrir no SharePoint</a>
              )}
            </div>
          ))}
        </div>
      )}

      {!loading && tab === "cnj" && results.length === 0 && query && (
        <div style={{ color: "rgba(255,255,255,0.3)", fontSize: 13 }}>Nenhum resultado encontrado.</div>
      )}
      {!loading && tab === "rag" && ragResults.length === 0 && query && (
        <div style={{ color: "rgba(255,255,255,0.3)", fontSize: 13 }}>Nenhum documento relevante encontrado. Certifique-se de que a biblioteca foi sincronizada.</div>
      )}
    </div>
  );
}

/* ════════════════════════ Biblioteca Panel ════════════════════════ */

function BibliotecaPanel() {
  const [files, setFiles] = useState([]);
  const [syncStatus, setSyncStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [search, setSearch] = useState("");
  const [folder, setFolder] = useState("all");
  const [sortBy, setSortBy] = useState("name");

  const load = async () => {
    setLoading(true);
    try {
      const [libResp, statusResp] = await Promise.all([
        api("/api/sharepoint/biblioteca"),
        api("/api/sharepoint/sync-status"),
      ]);
      const libData = await libResp.json();
      const statusData = await statusResp.json();
      setFiles(libData.files || []);
      setSyncStatus({ ...libData, ...statusData });
    } catch (e) { setFiles([]); } finally { setLoading(false); }
  };

  const triggerSync = async (force = false) => {
    setSyncing(true);
    try {
      await api("/api/sharepoint/sync", { method: "POST", body: JSON.stringify({ force }) });
      // Poll until done
      const poll = setInterval(async () => {
        try {
          const r = await api("/api/sharepoint/sync-status");
          const d = await r.json();
          setSyncStatus(d);
          if (!d.running) { clearInterval(poll); setSyncing(false); load(); }
        } catch { clearInterval(poll); setSyncing(false); }
      }, 2000);
    } catch { setSyncing(false); }
  };

  useEffect(() => { load(); }, []);

  const folders = ["all", ...new Set(files.map(f => f.folder || "").filter(Boolean))];
  const filtered = files.filter(f => {
    const matchSearch = !search || f.name.toLowerCase().includes(search.toLowerCase());
    const matchFolder = folder === "all" || (f.folder || "") === folder;
    return matchSearch && matchFolder;
  }).sort((a, b) => {
    if (sortBy === "name") return a.name.localeCompare(b.name);
    if (sortBy === "size") return (b.size || 0) - (a.size || 0);
    if (sortBy === "modified") return (b.modified || "").localeCompare(a.modified || "");
    return 0;
  });

  const fmtSize = (bytes) => {
    if (!bytes) return "—";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const extIcon = (name) => {
    const ext = name.split(".").pop()?.toLowerCase();
    if (ext === "pdf") return "🔴";
    if (ext === "docx" || ext === "doc") return "🔵";
    if (ext === "txt") return "⬜";
    return "📄";
  };

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 32 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ fontSize: 20, fontWeight: 800, color: "#fff", marginBottom: 4 }}>Biblioteca SharePoint</h2>
          <p style={{ fontSize: 13, color: "rgba(255,255,255,0.4)" }}>
            {loading ? "Carregando..." : `${files.length} arquivo(s) disponíveis localmente`}
            {syncStatus?.last_sync && ` · Último sync: ${new Date(syncStatus.last_sync).toLocaleString("pt-BR")}`}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => triggerSync(false)} disabled={syncing || loading} style={{
            padding: "8px 16px", borderRadius: 8, background: "rgba(34,197,94,0.1)",
            border: "1px solid rgba(34,197,94,0.2)", color: "#22c55e", fontSize: 12, cursor: "pointer", fontWeight: 600, opacity: syncing ? 0.6 : 1
          }}>{syncing ? "⏳ Sincronizando..." : "🔄 Sincronizar"}</button>
          <button onClick={() => triggerSync(true)} disabled={syncing || loading} style={{
            padding: "8px 16px", borderRadius: 8, background: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(255,255,255,0.08)", color: "rgba(255,255,255,0.5)", fontSize: 12, cursor: "pointer", opacity: syncing ? 0.6 : 1
          }}>🔃 Re-indexar tudo</button>
        </div>
      </div>

      {/* Sync progress */}
      {syncing && syncStatus && (
        <div style={{ padding: "12px 16px", borderRadius: 10, background: "rgba(34,197,94,0.05)", border: "1px solid rgba(34,197,94,0.15)", marginBottom: 20, fontSize: 12, color: "#22c55e" }}>
          ⚡ {syncStatus.progress || "Sincronizando..."}
        </div>
      )}

      {/* Filters */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap", alignItems: "center" }}>
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Buscar arquivo..."
          style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)", color: "#fff", fontSize: 12, outline: "none", width: 220 }} />
        {folders.length > 1 && (
          <select value={folder} onChange={e => setFolder(e.target.value)} style={{
            padding: "8px 12px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.08)",
            background: "rgba(255,255,255,0.04)", color: "#fff", fontSize: 12, cursor: "pointer"
          }}>
            <option value="all">📁 Todas as pastas</option>
            {folders.filter(f => f !== "all").map(f => <option key={f} value={f}>{f}</option>)}
          </select>
        )}
        <select value={sortBy} onChange={e => setSortBy(e.target.value)} style={{
          padding: "8px 12px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.08)",
          background: "rgba(255,255,255,0.04)", color: "#fff", fontSize: 12, cursor: "pointer"
        }}>
          <option value="name">↕ Nome</option>
          <option value="size">↕ Tamanho</option>
          <option value="modified">↕ Modificado</option>
        </select>
        <span style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", marginLeft: 8 }}>{filtered.length} arquivo(s)</span>
      </div>

      {/* File list */}
      {loading ? (
        <div style={{ color: "rgba(255,255,255,0.3)", fontSize: 14, textAlign: "center", padding: 40 }}>Carregando biblioteca...</div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: "center", padding: 60, color: "rgba(255,255,255,0.3)" }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📭</div>
          {files.length === 0
            ? <div><div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>Biblioteca vazia</div><div style={{ fontSize: 13 }}>Clique em "Sincronizar" para baixar os documentos do SharePoint</div></div>
            : <div style={{ fontSize: 14 }}>Nenhum arquivo encontrado para "{search}"</div>
          }
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {filtered.map(f => (
            <div key={f.item_id || f.name} style={{
              display: "flex", alignItems: "center", gap: 12, padding: "12px 16px",
              background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)",
              borderRadius: 10, transition: "all 0.15s"
            }}
              onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.04)"}
              onMouseLeave={e => e.currentTarget.style.background = "rgba(255,255,255,0.02)"}>
              <span style={{ fontSize: 20, flexShrink: 0 }}>{extIcon(f.name)}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#fff", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name}</div>
                <div style={{ display: "flex", gap: 12, fontSize: 11, color: "rgba(255,255,255,0.35)", marginTop: 2 }}>
                  {f.folder && <span>📁 {f.folder}</span>}
                  <span>{fmtSize(f.size)}</span>
                  {f.chunks > 0 && <span style={{ color: "#22c55e" }}>✓ {f.chunks} chunks</span>}
                  {f.modified && <span>📅 {f.modified?.slice(0, 10)}</span>}
                </div>
              </div>
              <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                {f.available_locally && f.item_id && (
                  <a href={`${import.meta.env.VITE_API_BASE || ""}/api/sharepoint/files/${f.item_id}`}
                    target="_blank" rel="noreferrer" download={f.name}
                    style={{
                      padding: "5px 12px", borderRadius: 6, background: "rgba(167,139,250,0.1)",
                      border: "1px solid rgba(167,139,250,0.2)", color: "#a78bfa",
                      fontSize: 11, fontWeight: 600, textDecoration: "none"
                    }}>↓ Baixar</a>
                )}
                {f.web_url && (
                  <a href={f.web_url} target="_blank" rel="noreferrer" style={{
                    padding: "5px 12px", borderRadius: 6, background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.08)", color: "rgba(255,255,255,0.5)",
                    fontSize: 11, textDecoration: "none"
                  }}>↗ SP</a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════════
   ██  MAIN APP
   ════════════════════════════════════════════════════════════════════ */

export default function JurisGenApp() {
  // ── State ──
  const [sessionId, setSessionId] = useState(null);
  const [stage, setStage] = useState("home"); // home | thinking | questions | outline | generating | document
  const [input, setInput] = useState("");
  const [docType, setDocType] = useState("");
  const [error, setError] = useState("");

  // Features & settings
  const [features, setFeatures] = useState({ jurisprudencia: true, legislacao: true, modelos: false, contadoria: false, perguntas: true, roteiro: true });
  const [verbosidade, setVerbosidade] = useState("longo");
  const [pensamento, setPensamento] = useState("medio");
  const [showSettings, setShowSettings] = useState(false);

  // Reasoning
  const [reasoning, setReasoning] = useState([]);
  const [reasoningExpanded, setReasoningExpanded] = useState(false);
  const reasoningTimer = useRef(null);

  // Questions
  const [questions, setQuestions] = useState([]);
  const [allAnswers, setAllAnswers] = useState({});
  const [answerRound, setAnswerRound] = useState(1);

  // Outline
  const [outline, setOutline] = useState(null);

  // Document
  const [sections, setSections] = useState([]);
  const [currentSection, setCurrentSection] = useState(-1);
  const [researchLog, setResearchLog] = useState([]);

  // UI
  const [loading, setLoading] = useState(false);
  const [startTime, setStartTime] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [showLegPanel, setShowLegPanel] = useState(false);
  const [verifyPopup, setVerifyPopup] = useState(null);
  const [history, setHistory] = useState([]);
  const [sidebarTab, setSidebarTab] = useState("inicio");
  const [activeTab, setActiveTab] = useState("inicio");
  const docRef = useRef(null);

  // Timer
  useEffect(() => {
    if (!startTime) return;
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - startTime) / 1000)), 1000);
    return () => clearInterval(t);
  }, [startTime]);

  // ── Session ──
  const ensureSession = useCallback(async () => {
    if (sessionId) return sessionId;
    try {
      const r = await api("/api/sessions", { method: "POST", body: JSON.stringify({}) });
      const d = await r.json();
      setSessionId(d.id);
      return d.id;
    } catch (e) {
      const backendUrl = import.meta.env.VITE_API_BASE;
      if (!backendUrl) {
        setError("Backend não configurado. Defina o secret VITE_API_BASE no GitHub com a URL do servidor e faça um novo deploy.");
      } else {
        setError("Falha ao conectar ao servidor (" + backendUrl + "): " + e.message);
      }
      return null;
    }
  }, [sessionId]);

  useEffect(() => { ensureSession(); }, []);

  // ── Reasoning simulator ──
  const startReasoning = (set) => {
    setReasoning([]);
    let idx = 0;
    const steps = REASONING_SETS[set] || REASONING_SETS.analyzing;
    reasoningTimer.current = setInterval(() => {
      if (idx < steps.length) {
        setReasoning(prev => [...prev, steps[idx]]);
        idx++;
      }
    }, 2500);
  };
  const stopReasoning = () => clearInterval(reasoningTimer.current);

  // ── Handlers ──
  const handleSubmitPrompt = async (text) => {
    if (!text?.trim()) return;
    const prompt = text.trim();
    setDocType(prompt);
    setInput("");
    setError("");
    setStage("thinking");
    setLoading(true);
    setStartTime(Date.now());
    startReasoning("analyzing");

    try {
      const sid = await ensureSession();
      if (!sid) throw new Error("Servidor indisponível");
      const r = await api("/api/pipeline/set-type", {
        method: "POST",
        body: JSON.stringify({ session_id: sid, doc_type: prompt, context: prompt }),
      });
      const d = await r.json();
      stopReasoning();
      if (features.perguntas && d.questions?.length > 0) {
        setQuestions(d.questions);
        setStage("questions");
      } else {
        // Skip questions, go to outline
        await handleGenerateOutline(sid);
      }
      setHistory(prev => [{ id: Date.now(), title: prompt, date: new Date().toLocaleDateString("pt-BR") }, ...prev]);
    } catch (e) {
      stopReasoning();
      setError(e.message);
      setStage("home");
    }
    setLoading(false);
  };

  const handleQuestionSubmit = async (roundAnswers) => {
    const merged = { ...allAnswers, ...roundAnswers };
    setAllAnswers(merged);
    setLoading(true);
    setStage("thinking");
    startReasoning("adjusting");

    try {
      const sid = sessionId || await ensureSession();
      const r = await api("/api/pipeline/answer", {
        method: "POST",
        body: JSON.stringify({ session_id: sid, answers: roundAnswers }),
      });
      const d = await r.json();
      stopReasoning();
      if (d.action === "more_questions") {
        setQuestions(d.questions || []);
        setAnswerRound(r => r + 1);
        setStage("questions");
      } else {
        setOutline(d.outline);
        setStage(features.roteiro ? "outline" : "generating");
        if (!features.roteiro) handleGenerate();
      }
    } catch (e) {
      stopReasoning();
      setError(e.message);
      setStage("questions");
    }
    setLoading(false);
  };

  const handleGenerateOutline = async (sid) => {
    // This would need a dedicated outline endpoint; for now handled by answer flow
  };

  const handleGenerate = async () => {
    setStage("generating");
    setSections([]);
    setResearchLog([]);
    setCurrentSection(-1);
    setStartTime(Date.now());

    try {
      const sid = sessionId || await ensureSession();
      const r = await fetch(`${API}/api/pipeline/generate-document/${sid}`, { method: "POST" });
      const reader = r.body.getReader();
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
            const ev = JSON.parse(line);
            if (ev.type === "research") {
              setResearchLog(prev => [...prev, ev.data]);
            } else if (ev.type === "section") {
              setSections(prev => {
                const next = [...prev, ev.data];
                setCurrentSection(next.length - 1);
                return next;
              });
            }
          } catch {}
        }
      }
      setStage("document");
      setStartTime(null);
    } catch (e) {
      setError(e.message);
      setStage("outline");
      setStartTime(null);
    }
  };

  const handleOutlineEdit = (idx, field, value) => {
    if (!outline) return;
    const secs = [...(outline.sections || [])];
    secs[idx] = { ...secs[idx], [field]: value };
    setOutline({ ...outline, sections: secs });
  };

  const handleOutlineMove = (from, to) => {
    const secs = [...(outline.sections || [])];
    const [item] = secs.splice(from, 1);
    secs.splice(to, 0, item);
    setOutline({ ...outline, sections: secs });
  };

  const handleOutlineDelete = (idx) => {
    const secs = [...(outline.sections || [])];
    secs.splice(idx, 1);
    setOutline({ ...outline, sections: secs });
  };

  const handleOutlineDuplicate = (idx) => {
    const secs = [...(outline.sections || [])];
    secs.splice(idx + 1, 0, { ...secs[idx], title: secs[idx].title + " (cópia)" });
    setOutline({ ...outline, sections: secs });
  };

  // Collect legislation sources from sections
  const allSources = sections.flatMap((s, i) =>
    (s.sources || []).map(src => ({ ...src, section: s.section_title, sectionIdx: i }))
  );
  const legislationSources = researchLog.filter(r => r.status === "done" && r.total > 0).map(r => ({
    source: r.section,
    time: `${(r.duration || 0.2).toFixed(1)}s`,
    results: (r.sources || []).map(s => ({ title: s.title || s.law || "Referência", text: s.text || s.snippet || "", law: s.law }))
  }));

  const outlineSections = outline?.sections || [];
  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");

  // ═══════════════ RENDER ═══════════════

  /* ── HOME ── */
  if (stage === "home") {
    return (
      <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#0a0a0f", color: "#fff" }}>
        {/* Top nav */}
        <div style={{ height: 52, borderBottom: "1px solid rgba(255,255,255,0.06)", display: "flex", alignItems: "center", justifyContent: "center", gap: 4, flexShrink: 0, background: "rgba(255,255,255,0.02)" }}>
          {[["🏠","Início","inicio"],["📋","Histórico","historico"],["💎","Modelos","modelos"],["📚","Referências","referencias"],["📖","Biblioteca","biblioteca"]].map(([ic,lb,id]) => {
            const isActive = activeTab === id;
            return (
              <button key={id} onClick={() => setActiveTab(id)} style={{
                display: "flex", flexDirection: "column", alignItems: "center", gap: 1,
                padding: "4px 14px", background: isActive ? "rgba(167,139,250,0.12)" : "none",
                border: "none", borderBottom: isActive ? "2px solid #a78bfa" : "2px solid transparent",
                cursor: "pointer", color: isActive ? "#a78bfa" : "rgba(255,255,255,0.4)", fontSize: 10, fontWeight: isActive ? 700 : 600,
                transition: "all 0.15s"
              }}>
                <span style={{ fontSize: 16 }}>{ic}</span>{lb}
              </button>
            );
          })}
        </div>

        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          {/* Left sidebar */}
          <div style={{ width: 240, borderRight: "1px solid rgba(255,255,255,0.06)", padding: 16, overflowY: "auto", flexShrink: 0 }}>
            <button onClick={() => { setStage("home"); setOutline(null); setSections([]); setAllAnswers({}); setSessionId(null); }}
              style={{ width: "100%", padding: "10px 14px", borderRadius: 8, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", color: "#fff", cursor: "pointer", fontSize: 13, fontWeight: 600, textAlign: "left", marginBottom: 16 }}>
              + Nova minuta
            </button>
            {["Compartilhamentos","Metadados CNJ","Comunicações DJEN","Histórico de Lote"].map(item => (
              <div key={item} style={{ padding: "8px 10px", fontSize: 12, color: "rgba(255,255,255,0.4)", cursor: "pointer", borderRadius: 6 }}
                onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.03)"}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                {item}
              </div>
            ))}
            <div style={{ margin: "16px 0", borderTop: "1px solid rgba(255,255,255,0.06)" }} />
            <div style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.3)", letterSpacing: 1, marginBottom: 8, paddingLeft: 10 }}>HISTÓRICO</div>
            {history.length === 0 && <div style={{ fontSize: 11, color: "rgba(255,255,255,0.2)", paddingLeft: 10 }}>Nenhum documento ainda</div>}
            {history.map(h => (
              <div key={h.id} style={{ padding: "6px 10px", fontSize: 12, color: "rgba(255,255,255,0.5)", cursor: "pointer", borderRadius: 6 }}>
                {h.title.substring(0, 30)}...
              </div>
            ))}
          </div>

          {/* Center: tab-driven */}
          {activeTab === "inicio" && (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
              <div style={{ maxWidth: 600, width: "100%", padding: 32 }}>
                <h1 style={{ fontSize: 36, fontWeight: 800, textAlign: "center", marginBottom: 4, color: "#fff" }}>
                  <span style={{ color: "#a78bfa" }}>Juris</span>Gen AI
                </h1>
                <p style={{ textAlign: "center", fontSize: 14, color: "rgba(255,255,255,0.4)", marginBottom: 32 }}>
                  O futuro do Direito começa aqui
                </p>

                {/* Settings toggle */}
                <div style={{ display: "flex", justifyContent: "center", gap: 8, marginBottom: 24 }}>
                  <button onClick={() => setShowSettings(false)} style={{
                    padding: "6px 16px", borderRadius: 20, fontSize: 12, fontWeight: 600, cursor: "pointer",
                    background: !showSettings ? "rgba(255,255,255,0.08)" : "transparent",
                    border: "1px solid rgba(255,255,255,0.08)", color: !showSettings ? "#fff" : "rgba(255,255,255,0.4)"
                  }}>📄 Padrão</button>
                  <button onClick={() => setShowSettings(true)} style={{
                    padding: "6px 16px", borderRadius: 20, fontSize: 12, fontWeight: 600, cursor: "pointer",
                    background: showSettings ? "rgba(167,139,250,0.15)" : "transparent",
                    border: showSettings ? "1px solid rgba(167,139,250,0.3)" : "1px solid rgba(255,255,255,0.08)",
                    color: showSettings ? "#a78bfa" : "rgba(255,255,255,0.4)"
                  }}>⚡ Agêntico <span style={{ fontSize: 9, background: "rgba(167,139,250,0.2)", padding: "1px 5px", borderRadius: 4 }}>beta</span></button>
                </div>

                {/* Settings panel */}
                {showSettings && (
                  <div style={{ display: "flex", gap: 20, marginBottom: 24 }}>
                    <div style={{ flex: 1 }}>
                      <FeatureRow icon="⚖️" label="Jurisprudência" desc="Busca decisões judiciais relevantes" on={features.jurisprudencia} onChange={v => setFeatures(f => ({ ...f, jurisprudencia: v }))} />
                      <FeatureRow icon="📖" label="Legislação" desc="Busca leis e normas aplicáveis" on={features.legislacao} onChange={v => setFeatures(f => ({ ...f, legislacao: v }))} />
                      <FeatureRow icon="📄" label="Modelos" desc="Busca peças e modelos de referência" on={features.modelos} onChange={v => setFeatures(f => ({ ...f, modelos: v }))} />
                      <FeatureRow icon="🧮" label="Contadoria (cálculos)" desc="Realiza cálculos judiciais e financeiros" on={features.contadoria} onChange={v => setFeatures(f => ({ ...f, contadoria: v }))} />
                    </div>
                    <div style={{ width: 220 }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                        <div><div style={{ fontSize: 13, fontWeight: 600, color: "#fff" }}>Perguntas</div><div style={{ fontSize: 10, color: "rgba(255,255,255,0.3)" }}>Responde automaticamente</div></div>
                        <Toggle on={features.perguntas} onChange={v => setFeatures(f => ({ ...f, perguntas: v }))} />
                      </div>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid rgba(255,255,255,0.04)", marginBottom: 16 }}>
                        <div><div style={{ fontSize: 13, fontWeight: 600, color: "#fff" }}>Roteiro</div><div style={{ fontSize: 10, color: "rgba(255,255,255,0.3)" }}>Aprova o plano de execução</div></div>
                        <Toggle on={features.roteiro} onChange={v => setFeatures(f => ({ ...f, roteiro: v }))} />
                      </div>
                      <div style={{ marginBottom: 12 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,0.4)", letterSpacing: 1, marginBottom: 6 }}>VERBOSIDADE</div>
                        <div style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", marginBottom: 6 }}>Tamanho e nível de detalhe do documento.</div>
                        <Pill options={[{ id: "curto", icon: "≡", label: "Curto" }, { id: "longo", icon: "≡", label: "Longo", rec: true }]} value={verbosidade} onChange={setVerbosidade} />
                      </div>
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,0.4)", letterSpacing: 1, marginBottom: 6 }}>PENSAMENTO</div>
                        <div style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", marginBottom: 6 }}>Profundidade de raciocínio antes de redigir.</div>
                        <Pill options={[{ id: "baixo", label: "Baixo" }, { id: "medio", label: "Médio", rec: true }, { id: "alto", label: "Alto" }]} value={pensamento} onChange={setPensamento} />
                      </div>
                    </div>
                  </div>
                )}

                {error && (
                  <div style={{ padding: "10px 14px", marginBottom: 12, borderRadius: 8, background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444", fontSize: 12 }}>
                    {error}
                  </div>
                )}

                {/* Chat input */}
                <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
                  <div style={{ flex: 1, position: "relative" }}>
                    <input value={input} onChange={e => { setInput(e.target.value); setError(""); }}
                      onKeyDown={e => e.key === "Enter" && handleSubmitPrompt(input)}
                      placeholder="Instruções ao JurisGen para geração da minuta..."
                      style={{
                        width: "100%", padding: "14px 16px", borderRadius: 12,
                        border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)",
                        color: "#fff", fontSize: 14, outline: "none", fontFamily: "inherit"
                      }} />
                  </div>
                  <button onClick={() => handleSubmitPrompt(input)} disabled={!input.trim() || loading}
                    style={{
                      width: 44, height: 44, borderRadius: "50%", border: "none", cursor: "pointer",
                      background: input.trim() ? "var(--accent)" : "rgba(255,255,255,0.05)",
                      color: "#fff", fontSize: 18, display: "flex", alignItems: "center", justifyContent: "center"
                    }}>↑</button>
                </div>
                <div style={{ textAlign: "center", fontSize: 10, color: "rgba(255,255,255,0.2)", marginTop: 8 }}>
                  JurisGen AI pode cometer erros. Nunca dispense a revisão humana final.
                </div>
              </div>
            </div>
          )}

          {activeTab === "historico" && (
            <HistoricoPanel history={history} onReopen={(h) => { setActiveTab("inicio"); setInput(h.title); }} />
          )}

          {activeTab === "modelos" && (
            <ModelosPanel onSelect={(modelo) => { setActiveTab("inicio"); setInput(modelo); }} />
          )}

          {activeTab === "referencias" && <ReferenciasPanel />}

          {activeTab === "biblioteca" && <BibliotecaPanel />}
        </div>
      </div>
    );
  }

  /* ── THINKING / QUESTIONS ── */
  if (stage === "thinking" || stage === "questions") {
    return (
      <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#0a0a0f", color: "#fff" }}>
        {/* Top bar */}
        <div style={{ height: 52, borderBottom: "1px solid rgba(255,255,255,0.06)", display: "flex", alignItems: "center", justifyContent: "center", gap: 4, flexShrink: 0, background: "rgba(255,255,255,0.02)" }}>
          {[["🏠","Início"],["📋","Histórico"]].map(([ic,lb]) => (
            <button key={lb} onClick={() => lb === "Início" && setStage("home")} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 1, padding: "4px 14px", background: "none", border: "none", cursor: "pointer", color: "rgba(255,255,255,0.4)", fontSize: 10, fontWeight: 600 }}>
              <span style={{ fontSize: 16 }}>{ic}</span>{lb}
            </button>
          ))}
        </div>

        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          {/* Sidebar */}
          <div style={{ width: 220, borderRight: "1px solid rgba(255,255,255,0.06)", padding: 16, overflowY: "auto", flexShrink: 0 }}>
            <button onClick={() => setStage("home")} style={{ width: "100%", padding: "8px 12px", borderRadius: 8, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", color: "#fff", cursor: "pointer", fontSize: 12, fontWeight: 600, textAlign: "left", marginBottom: 12 }}>
              + Nova minuta
            </button>
            {["Documentos","Modelos","Legislação","Jurisprudência"].map(item => (
              <div key={item} style={{ padding: "8px 10px", fontSize: 12, color: "rgba(255,255,255,0.4)", cursor: "pointer", borderRadius: 6, display: "flex", alignItems: "center", gap: 8 }}>
                <span>{item === "Documentos" ? "📄" : item === "Modelos" ? "💎" : item === "Legislação" ? "📖" : "⚖️"}</span>
                {item}
              </div>
            ))}
          </div>

          {/* Center content */}
          <div style={{ flex: 1, overflowY: "auto", padding: "24px 48px", maxWidth: 800, margin: "0 auto" }}>
            {/* User prompt */}
            <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 16 }}>
              <div style={{ background: "rgba(167,139,250,0.15)", border: "1px solid rgba(167,139,250,0.25)", borderRadius: 10, padding: "10px 16px", maxWidth: 500, fontSize: 13, color: "#d4bbff" }}>
                {docType}
              </div>
            </div>

            {/* Status bar */}
            <StatusBar features={features} startTime={startTime} />

            {/* Thinking indicator */}
            {(loading || stage === "thinking") && (
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                <div style={{ width: 32, height: 32, borderRadius: 8, background: "rgba(167,139,250,0.1)", display: "flex", alignItems: "center", justifyContent: "center", animation: "pulse 1.5s infinite" }}>
                  <span style={{ fontSize: 18 }}>⚡</span>
                </div>
                <span style={{ fontSize: 14, fontWeight: 600, color: "rgba(255,255,255,0.6)" }}>Pensando...</span>
              </div>
            )}

            {/* Reasoning */}
            <ReasoningPanel steps={reasoning} expanded={reasoningExpanded} onToggle={() => setReasoningExpanded(!reasoningExpanded)} />

            {/* Answers card */}
            {Object.keys(allAnswers).length > 0 && <AnswersCard answers={allAnswers} />}

            {/* Adjusting message */}
            {stage === "thinking" && Object.keys(allAnswers).length > 0 && (
              <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "16px 0" }}>
                <span style={{ fontSize: 18 }}>⚡</span>
                <span style={{ fontSize: 13, color: "rgba(255,255,255,0.5)" }}>Ajustando o roteiro conforme suas respostas...</span>
              </div>
            )}

            {/* Questions form */}
            {stage === "questions" && !loading && (
              <QuestionForm questions={questions} onSubmit={handleQuestionSubmit} />
            )}
          </div>
        </div>

        {/* Bottom bar */}
        <div style={{ padding: "8px 20px", borderTop: "1px solid rgba(255,255,255,0.06)", background: "rgba(255,255,255,0.02)", display: "flex", alignItems: "center", justifyContent: "center", gap: 12 }}>
          <span style={{ fontSize: 11, color: "rgba(255,255,255,0.3)" }}>⚡ Agêntico</span>
          <span style={{ fontSize: 11, color: "rgba(255,255,255,0.3)" }}>📖 📄</span>
          <span style={{ fontSize: 11, color: "rgba(255,255,255,0.3)" }}>Médio</span>
        </div>
      </div>
    );
  }

  /* ── OUTLINE ── */
  if (stage === "outline" && outline) {
    const secs = outline.sections || [];
    return (
      <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#0a0a0f", color: "#fff" }}>
        <div style={{ height: 52, borderBottom: "1px solid rgba(255,255,255,0.06)", display: "flex", alignItems: "center", padding: "0 20px", background: "rgba(255,255,255,0.02)" }}>
          <button onClick={() => setStage("questions")} style={{ background: "none", border: "none", color: "rgba(255,255,255,0.4)", cursor: "pointer", fontSize: 16, marginRight: 12 }}>←</button>
          <span style={{ fontSize: 14, fontWeight: 600, color: "#fff" }}>{outline.title || docType}</span>
          <span style={{ marginLeft: 12, fontSize: 11, padding: "3px 10px", borderRadius: 12, background: "rgba(167,139,250,0.1)", color: "#a78bfa", fontWeight: 600 }}>{secs.length} etapas</span>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "24px 48px", maxWidth: 800, margin: "0 auto", width: "100%" }}>
          <h2 style={{ fontSize: 20, fontWeight: 800, color: "#fff", marginBottom: 4 }}>{outline.title || docType}</h2>
          <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
            <span style={{ fontSize: 12, color: "rgba(255,255,255,0.4)" }}>{secs.length} etapas</span>
            {outline.subtitle && <span style={{ fontSize: 12, color: "rgba(255,255,255,0.4)" }}>|</span>}
            {outline.subtitle && <span style={{ fontSize: 12, color: "#a78bfa" }}>{outline.subtitle}</span>}
          </div>

          {secs.map((s, i) => (
            <OutlineSection key={i} section={s} index={i} total={secs.length}
              onEdit={(idx, f, v) => handleOutlineEdit(idx, f, v)}
              onDelete={handleOutlineDelete}
              onDuplicate={handleOutlineDuplicate}
              onMove={handleOutlineMove} />
          ))}

          <button onClick={() => {
            const secs2 = [...secs, { title: "Nova seção", description: "Descreva o conteúdo desta seção", subtopics: [] }];
            setOutline({ ...outline, sections: secs2 });
          }} style={{
            width: "100%", padding: "12px", borderRadius: 10, border: "1px dashed rgba(255,255,255,0.1)",
            background: "rgba(255,255,255,0.01)", color: "rgba(255,255,255,0.4)", cursor: "pointer",
            fontSize: 13, fontWeight: 500, marginBottom: 8
          }}>+ Adicionar etapa ao final</button>

          <p style={{ fontSize: 11, color: "rgba(255,255,255,0.25)", textAlign: "center", marginBottom: 20 }}>
            Use as setas para reordenar as etapas.
          </p>

          <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", paddingTop: 16, borderTop: "1px solid rgba(255,255,255,0.06)" }}>
            <button onClick={() => setStage("questions")} style={{ padding: "10px 20px", borderRadius: 8, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.5)", cursor: "pointer", fontSize: 13 }}>Voltar</button>
            <button onClick={handleGenerate} style={{ padding: "10px 24px", borderRadius: 8, background: "var(--accent)", border: "none", color: "#fff", fontWeight: 700, cursor: "pointer", fontSize: 13, boxShadow: "0 2px 8px rgba(124,58,237,0.3)" }}>
              Aprovar e gerar documento →
            </button>
          </div>
        </div>
      </div>
    );
  }

  /* ── GENERATING / DOCUMENT ── */
  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#0a0a0f", color: "#fff" }}>
      {/* Top bar */}
      <div style={{ height: 52, background: "rgba(255,255,255,0.02)", borderBottom: "1px solid rgba(255,255,255,0.06)", display: "flex", alignItems: "center", padding: "0 16px", gap: 12, flexShrink: 0 }}>
        <button onClick={() => { setStage("home"); setSections([]); setOutline(null); setAllAnswers({}); setStartTime(null); setSessionId(null); }}
          style={{ background: "none", border: "none", color: "rgba(255,255,255,0.4)", cursor: "pointer", fontSize: 16 }}>← Início</button>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#fff" }}>{outline?.title || docType}</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {stage === "generating" && (
            <span style={{ fontSize: 12, color: "#22c55e", display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#22c55e", animation: "pulse 1.5s infinite" }} />
              Escrevendo ({mm}:{ss})
            </span>
          )}
          {stage === "document" && (
            <>
              <button onClick={() => {
                const text = sections.filter(s => !s.is_sources).map(s => `${s.section_title}\n\n${s.content}`).join("\n\n");
                navigator.clipboard.writeText(text);
              }} title="Copiar" style={{ padding: "5px 10px", borderRadius: 6, background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", color: "rgba(255,255,255,0.5)", cursor: "pointer", fontSize: 11 }}>📋 Copiar</button>
              <button onClick={() => setShowLegPanel(!showLegPanel)} title="Legislação" style={{
                padding: "5px 10px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.08)", cursor: "pointer", fontSize: 11, fontWeight: 600,
                background: showLegPanel ? "rgba(34,197,94,0.1)" : "rgba(255,255,255,0.05)",
                color: showLegPanel ? "#22c55e" : "rgba(255,255,255,0.5)"
              }}>📖 {legislationSources.length}</button>
            </>
          )}
        </div>
      </div>

      {/* Green editable banner */}
      {stage === "document" && (
        <div style={{ padding: "6px 20px", background: "rgba(34,197,94,0.05)", borderBottom: "1px solid rgba(34,197,94,0.1)", fontSize: 12, color: "#22c55e", textAlign: "center" }}>
          ● Este documento é editável. A IA entende e preserva as suas edições! Clique no texto para começar.
        </div>
      )}

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Left panel */}
        <div style={{ width: 280, borderRight: "1px solid rgba(255,255,255,0.06)", background: "rgba(255,255,255,0.01)", flexShrink: 0, overflowY: "auto", padding: 16 }}>
          {/* Title + status */}
          <div style={{ fontSize: 13, fontWeight: 700, color: "#fff", marginBottom: 8 }}>{outline?.title || docType}</div>
          <StatusBar features={features} startTime={startTime} />

          {/* Answers */}
          <AnswersCard answers={allAnswers} />

          {/* Section progress */}
          {outlineSections.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,0.4)", letterSpacing: 0.5, marginBottom: 8 }}>ROTEIRO</div>
              {outlineSections.map((s, i) => {
                const done = sections.some(sec => sec.section_title === s.title);
                return (
                  <div key={i} style={{ display: "flex", gap: 8, padding: "5px 0", alignItems: "center", cursor: done ? "pointer" : "default", opacity: done ? 1 : 0.4 }}
                    onClick={() => { if (done) document.getElementById(`section-${i}`)?.scrollIntoView({ behavior: "smooth" }); }}>
                    <div style={{
                      width: 18, height: 18, borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center",
                      background: done ? "#22c55e" : "transparent", border: done ? "none" : "1.5px solid rgba(255,255,255,0.2)",
                      fontSize: 10, color: "#fff"
                    }}>{done ? "✓" : ""}</div>
                    <span style={{ fontSize: 11, color: done ? "#fff" : "rgba(255,255,255,0.4)" }}>{s.title}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Center: Document */}
        <div ref={docRef} style={{ flex: 1, overflowY: "auto", padding: "32px 48px", maxWidth: 900, margin: "0 auto", width: "100%", position: "relative" }}>
          {/* Progress bar */}
          {stage === "generating" && (
            <div style={{ width: "100%", height: 3, borderRadius: 2, background: "rgba(255,255,255,0.05)", marginBottom: 24 }}>
              <div style={{ width: `${outlineSections.length > 0 ? (sections.length / outlineSections.length) * 100 : 0}%`, height: "100%", borderRadius: 2, background: "#22c55e", transition: "width 0.5s" }} />
            </div>
          )}

          {sections.filter(s => !s.is_sources).map((sec, i) => (
            <div key={i} id={`section-${i}`} style={{ marginBottom: 28, position: "relative" }}>
              <h3 style={{ fontSize: 15, fontWeight: 800, color: "#fff", marginBottom: 10, letterSpacing: 0.3 }}>{sec.section_title}</h3>
              <div contentEditable={stage === "document"} suppressContentEditableWarning
                style={{ fontSize: 14, color: "rgba(255,255,255,0.8)", lineHeight: 1.85, whiteSpace: "pre-wrap", textAlign: "justify", outline: "none" }}>
                {sec.content}
              </div>
              {/* Verification badges */}
              {sec.sources_count > 0 && (
                <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap", alignItems: "center" }}>
                  {(sec.verification_sources || []).slice(0, 3).map((vs, j) => (
                    <button key={j} onClick={(e) => setVerifyPopup({ source: vs, top: e.clientY - 200, left: e.clientX - 180 })}
                      style={{
                        display: "inline-flex", alignItems: "center", gap: 4, padding: "3px 8px", borderRadius: 6,
                        background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.2)",
                        cursor: "pointer", fontSize: 11, color: "#22c55e", fontWeight: 500
                      }}>
                      <span>✓</span> LEGIS
                    </button>
                  ))}
                  {sec.sources_count > 0 && (
                    <span style={{ fontSize: 10, color: "rgba(255,255,255,0.3)" }}>
                      {sec.sources_count} fonte(s)
                    </span>
                  )}
                  {(sec.models_used || []).map((m, j) => (
                    <span key={j} style={{ fontSize: 10, padding: "2px 7px", borderRadius: 8, background: "rgba(167,139,250,0.1)", color: "#a78bfa" }}>{m}</span>
                  ))}
                </div>
              )}
            </div>
          ))}

          {stage === "generating" && sections.length === 0 && (
            <div style={{ textAlign: "center", padding: 60, color: "rgba(255,255,255,0.3)" }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>⚡</div>
              Preparando documento...
            </div>
          )}
        </div>

        {/* Legislation panel */}
        {showLegPanel && <LegislationPanel sources={legislationSources} onClose={() => setShowLegPanel(false)} />}
      </div>

      {/* Verification popup */}
      {verifyPopup && <VerificationPopup source={verifyPopup.source} position={verifyPopup} onClose={() => setVerifyPopup(null)} />}

      {/* Bottom chat */}
      {stage === "document" && (
        <div style={{ padding: "10px 20px", borderTop: "1px solid rgba(255,255,255,0.06)", background: "rgba(255,255,255,0.02)" }}>
          <div style={{ display: "flex", gap: 8, maxWidth: 700, margin: "0 auto", alignItems: "center" }}>
            <input value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") { /* handle chat */ } }}
              placeholder="Instruções para melhoria da minuta..."
              style={{ flex: 1, padding: "10px 14px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.06)", background: "rgba(255,255,255,0.02)", color: "#fff", fontSize: 13, outline: "none" }} />
            <span style={{ fontSize: 11, color: "rgba(255,255,255,0.2)" }}>Sem contexto</span>
          </div>
          <div style={{ textAlign: "center", fontSize: 10, color: "rgba(255,255,255,0.15)", marginTop: 4 }}>
            JurisGen AI pode cometer erros. Nunca dispense a revisão humana final.
          </div>
        </div>
      )}

      {/* Expandir controles */}
      {stage === "generating" && (
        <div style={{ padding: "8px 20px", borderTop: "1px solid rgba(255,255,255,0.06)", background: "rgba(255,255,255,0.02)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontSize: 12, color: "rgba(255,255,255,0.3)", cursor: "pointer" }}>▸ Expandir controles</span>
          <button onClick={() => {}} style={{ width: 20, height: 20, borderRadius: "50%", background: "#ef4444", border: "none", cursor: "pointer" }} title="Parar geração" />
        </div>
      )}
    </div>
  );
}

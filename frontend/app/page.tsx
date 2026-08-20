"use client";

import { DragEvent, FormEvent, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { BookOpen, FileText, LayoutGrid, LogOut, Sparkles, Target, Trash2, Upload, Users } from "lucide-react";

type Exam = { id: string; title: string };
type Notice = {
  id: string;
  filename: string;
  extraction_metadata: { analysis?: { subjects?: { name: string }[] } };
};
type ActiveUser = { id: string; full_name: string | null };
type Me = { id: string; email: string; full_name: string | null };
type StudyPlan = {
  id: string;
  exam_id: string | null;
  position_id: string | null;
  title: string;
  available_minutes_per_day: number;
  starts_on: string;
  ends_on: string | null;
  is_active: boolean;
};
type ScheduleEntry = {
  item: { id: string; subject_id: string | null; topic_id: string | null; scheduled_for: string; planned_minutes: number; priority: number };
  subject_name: string | null;
  topic_name: string | null;
  session_id: string | null;
  session_status: string;
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const fadeUp = { hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0 } };

export default function Home() {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [exams, setExams] = useState<Exam[]>([]);
  const [selected, setSelected] = useState("");
  const [notices, setNotices] = useState<Notice[]>([]);
  const [users, setUsers] = useState<ActiveUser[]>([]);
  const [studyPlans, setStudyPlans] = useState<StudyPlan[]>([]);
  const [schedule, setSchedule] = useState<ScheduleEntry[]>([]);
  const [creatingPlan, setCreatingPlan] = useState(false);
  const [rescheduling, setRescheduling] = useState(false);
  const [itemActionId, setItemActionId] = useState<string | null>(null);
  const [showAllDays, setShowAllDays] = useState(false);
  const [rotinaView, setRotinaView] = useState<"semana" | "lista">("semana");
  const [weekOffset, setWeekOffset] = useState(0);
  const [tab, setTab] = useState<"painel" | "usuarios" | "rotina">("painel");
  const [msg, setMsg] = useState("Entre para conectar seus dados.");
  const [me, setMe] = useState<Me | null>(null);
  const [username, setUsername] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const req = async (path: string, init: RequestInit = {}, authToken = token) => {
    const res = await fetch(API + path, { ...init, headers: { Authorization: `Bearer ${authToken}`, ...init.headers } });
    if (!res.ok) throw new Error((await res.json().catch(() => ({ detail: "Erro na API" }))).detail);
    return res;
  };

  const load = async (authToken = token) => {
    try {
      setMe(await (await req("/api/v1/auth/me", {}, authToken)).json());
    } catch {
      setMe(null);
    }
    try {
      const data = await (await req("/api/v1/exams", {}, authToken)).json();
      setExams(data);
      if (data[0]) setSelected((current: string) => current || data[0].id);
    } catch (error) {
      setMsg(error instanceof Error ? error.message : "API indisponível");
    }
    try {
      setUsers(await (await req("/api/v1/users", {}, authToken)).json());
    } catch {
      setUsers([]);
    }
    try {
      setStudyPlans(await (await req("/api/v1/study-plans", {}, authToken)).json());
    } catch {
      setStudyPlans([]);
    }
  };

  const loadSchedule = async (planId: string) => {
    try {
      setSchedule(await (await req(`/api/v1/study-plans/${planId}/schedule`)).json());
    } catch {
      setSchedule([]);
    }
  };

  const saveUsername = async (event: FormEvent) => {
    event.preventDefault();
    if (!username.trim()) return;
    setSavingName(true);
    try {
      const updated = await (
        await req("/api/v1/auth/me", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ full_name: username.trim() }) })
      ).json();
      setMe(updated);
      await load();
    } catch (error) {
      setMsg(error instanceof Error ? error.message : "Não deu pra salvar o nome");
    } finally {
      setSavingName(false);
    }
  };

  const loadNotices = async (examId = selected) => {
    if (!examId) return;
    try {
      setNotices(await (await req(`/api/v1/exams/${examId}/notices`)).json());
    } catch {
      setNotices([]);
    }
  };

  useEffect(() => {
    const stored = localStorage.getItem("concursos_token");
    if (stored) {
      setToken(stored);
      void load(stored);
    }
  }, []);

  useEffect(() => {
    if (token) void loadNotices();
  }, [token, selected]);

  const activePlan = studyPlans.find((plan) => plan.exam_id === selected && plan.is_active) || null;

  useEffect(() => {
    if (activePlan) void loadSchedule(activePlan.id);
    else setSchedule([]);
  }, [activePlan?.id]);

  const login = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const res = await fetch(API + "/api/v1/auth/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);
      localStorage.setItem("concursos_token", data.access_token);
      setToken(data.access_token);
      await load(data.access_token);
    } catch (error) {
      setMsg(error instanceof Error ? error.message : "Falha ao entrar");
    }
  };

  const createExam = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      const created = await (
        await req("/api/v1/exams", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: form.get("title"), examining_board: form.get("board") || null }),
        })
      ).json();
      setExams((current) => [created, ...current]);
      setSelected(created.id);
      formElement.reset();
    } catch (error) {
      setMsg(error instanceof Error ? error.message : "Não deu pra criar o concurso");
    }
  };

  const pickFile = (file: File | undefined | null) => {
    if (!file) return;
    if (file.type !== "application/pdf") {
      setMsg("Só arquivos PDF são aceitos.");
      return;
    }
    setPendingFile(file);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(false);
    if (!selected) return;
    pickFile(event.dataTransfer.files?.[0]);
  };

  const submitUpload = async (event: FormEvent) => {
    event.preventDefault();
    if (!pendingFile || !selected) return;
    const body = new FormData();
    body.append("file", pendingFile);
    setUploading(true);
    try {
      await req(`/api/v1/exams/${selected}/notices`, { method: "POST", body });
      await loadNotices();
      setPendingFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setMsg("Edital importado.");
    } catch (error) {
      setMsg(error instanceof Error ? error.message : "Não deu pra importar o edital");
    } finally {
      setUploading(false);
    }
  };

  const analyzeNotice = async (noticeId: string) => {
    setAnalyzingId(noticeId);
    try {
      const result = await (await req(`/api/v1/exams/${selected}/notices/${noticeId}/analyze`, { method: "POST" })).json();
      await loadNotices();
      const foundSomething = Boolean(result.examining_board) || (result.subjects?.length ?? 0) > 0 || (result.positions?.length ?? 0) > 0;
      setMsg(
        foundSomething
          ? "Edital analisado."
          : "Analisado, mas não achou banca/disciplinas. Confira se este é o edital completo (não um anexo/quadro de vagas) e se não é um PDF escaneado."
      );
    } catch (error) {
      setMsg(error instanceof Error ? error.message : "Não deu pra analisar o edital");
    } finally {
      setAnalyzingId(null);
    }
  };

  const deleteNotice = async (noticeId: string) => {
    if (!confirm("Excluir este edital? Não dá pra desfazer.")) return;
    setDeletingId(noticeId);
    try {
      await req(`/api/v1/exams/${selected}/notices/${noticeId}`, { method: "DELETE" });
      await loadNotices();
      setMsg("Edital excluído.");
    } catch (error) {
      setMsg(error instanceof Error ? error.message : "Não deu pra excluir o edital");
    } finally {
      setDeletingId(null);
    }
  };

  const createStudyPlan = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selected) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setCreatingPlan(true);
    try {
      const created = await (
        await req("/api/v1/study-plans", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            exam_id: selected,
            title: form.get("title"),
            available_minutes_per_day: Number(form.get("minutes")),
            starts_on: form.get("starts_on"),
            ends_on: form.get("ends_on") || null,
          }),
        })
      ).json();
      setStudyPlans((current) => [created, ...current]);
      setMsg("Plano de estudos gerado.");
    } catch (error) {
      setMsg(error instanceof Error ? error.message : "Não deu pra gerar o plano");
    } finally {
      setCreatingPlan(false);
    }
  };

  const reschedulePlan = async () => {
    if (!activePlan) return;
    setRescheduling(true);
    try {
      setSchedule(await (await req(`/api/v1/study-plans/${activePlan.id}/reschedule`, { method: "POST" })).json());
      setMsg("Agenda futura recalculada.");
    } catch (error) {
      setMsg(error instanceof Error ? error.message : "Não deu pra reagendar");
    } finally {
      setRescheduling(false);
    }
  };

  const markItem = async (itemId: string, outcome: "complete" | "skip") => {
    if (!activePlan) return;
    setItemActionId(itemId);
    try {
      await req(`/api/v1/study-plans/${activePlan.id}/items/${itemId}/${outcome}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      await loadSchedule(activePlan.id);
      setMsg(outcome === "complete" ? "Sessão marcada como concluída." : "Sessão marcada como pulada.");
    } catch (error) {
      setMsg(error instanceof Error ? error.message : "Não deu pra registrar");
    } finally {
      setItemActionId(null);
    }
  };

  const logout = () => {
    localStorage.removeItem("concursos_token");
    setToken("");
  };

  if (!token) {
    return (
      <main className="auth">
        <motion.div className="auth-copy" initial="hidden" animate="show" variants={fadeUp} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}>
          <span className="eyebrow">
            <Sparkles size={13} /> Concursos
          </span>
          <h1>Estude com direção.</h1>
          <p>Editais, provas e desempenho num só lugar — e um plano que se ajusta ao que você já sabe.</p>
        </motion.div>

        <motion.form
          className="panel"
          onSubmit={login}
          initial="hidden"
          animate="show"
          variants={fadeUp}
          transition={{ duration: 0.5, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
        >
          <h2>Entrar</h2>
          <label className="field">
            E-mail
            <input required type="email" placeholder="voce@email.com" aria-label="E-mail" onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="field">
            Senha
            <input required type="password" placeholder="••••••••" aria-label="Senha" onChange={(e) => setPassword(e.target.value)} />
          </label>
          <button type="submit">Entrar</button>
          <small className="hint">{msg}</small>
        </motion.form>
      </main>
    );
  }

  if (me && !me.full_name) {
    return (
      <main className="auth">
        <motion.div className="auth-copy" initial="hidden" animate="show" variants={fadeUp} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}>
          <span className="eyebrow">
            <Sparkles size={13} /> Quase lá
          </span>
          <h1>Como te chamamos?</h1>
          <p>Escolha o nome que os outros vão ver no painel. Dá pra trocar depois se quiser.</p>
        </motion.div>

        <motion.form
          className="panel"
          onSubmit={saveUsername}
          initial="hidden"
          animate="show"
          variants={fadeUp}
          transition={{ duration: 0.5, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
        >
          <h2>Criar nome de usuário</h2>
          <label className="field">
            Nome
            <input required minLength={1} maxLength={120} placeholder="Seu nome" aria-label="Nome de usuário" value={username} onChange={(e) => setUsername(e.target.value)} />
          </label>
          <button type="submit" disabled={savingName}>
            {savingName ? "Salvando…" : "Continuar"}
          </button>
        </motion.form>
      </main>
    );
  }

  const subjectsCount = notices.reduce((total, notice) => total + (notice.extraction_metadata.analysis?.subjects?.length || 0), 0);

  return (
    <main>
      <div className="app-header">
        <div>
          <span className="eyebrow">
            <Target size={13} /> Painel de estudos
          </span>
          <h1>{me?.full_name ? `Bem-vindo, ${me.full_name.split(" ")[0]}` : "Seu próximo avanço"}</h1>
        </div>
        <button className="ghost" onClick={logout}>
          <LogOut size={14} style={{ verticalAlign: -2, marginRight: 6 }} />
          Sair
        </button>
      </div>

      <p className="status-line">
        <span className="status-dot" />
        {msg}
      </p>

      <div className="tabs" role="tablist">
        <button className={tab === "painel" ? "" : "ghost"} role="tab" aria-selected={tab === "painel"} onClick={() => setTab("painel")}>
          <LayoutGrid size={14} style={{ verticalAlign: -2, marginRight: 6 }} />
          Painel
        </button>
        <button className={tab === "rotina" ? "" : "ghost"} role="tab" aria-selected={tab === "rotina"} onClick={() => setTab("rotina")}>
          <BookOpen size={14} style={{ verticalAlign: -2, marginRight: 6 }} />
          Rotina
        </button>
        <button className={tab === "usuarios" ? "" : "ghost"} role="tab" aria-selected={tab === "usuarios"} onClick={() => setTab("usuarios")}>
          <Users size={14} style={{ verticalAlign: -2, marginRight: 6 }} />
          Usuários ativos
        </button>
      </div>

      {tab === "rotina" ? (
        <motion.section className="panel" initial="hidden" animate="show" variants={fadeUp} transition={{ duration: 0.4 }}>
          <h2>Rotina de estudos</h2>

          {!selected && <p className="hint" style={{ marginTop: 10 }}>Selecione um concurso no Painel primeiro.</p>}

          {selected && !activePlan && (
            <form onSubmit={createStudyPlan} style={{ marginTop: 12 }}>
              <input required name="title" placeholder="Nome do plano" defaultValue="Plano de estudos" aria-label="Nome do plano" />
              <input required name="minutes" type="number" min={15} max={720} defaultValue={60} placeholder="Minutos por dia" aria-label="Minutos disponíveis por dia" />
              <label className="field">
                Início
                <input required name="starts_on" type="date" defaultValue={new Date().toISOString().slice(0, 10)} aria-label="Data de início" />
              </label>
              <label className="field">
                Fim (opcional — usa a data da prova se vazio)
                <input name="ends_on" type="date" aria-label="Data final" />
              </label>
              <button type="submit" disabled={creatingPlan}>
                {creatingPlan ? "Gerando…" : "Gerar plano"}
              </button>
            </form>
          )}

          {selected && activePlan && (
            <>
              <div className="item" style={{ borderTop: "none", paddingTop: 0 }}>
                <div>
                  <b>{activePlan.title}</b>
                  <small>
                    {activePlan.available_minutes_per_day} min/dia · {activePlan.starts_on} até {activePlan.ends_on || "data da prova"}
                  </small>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <div className="view-toggle">
                    <button className={rotinaView === "semana" ? "" : "ghost"} onClick={() => setRotinaView("semana")}>
                      Semana
                    </button>
                    <button className={rotinaView === "lista" ? "" : "ghost"} onClick={() => setRotinaView("lista")}>
                      Lista
                    </button>
                  </div>
                  <button className="ghost" disabled={rescheduling} onClick={reschedulePlan}>
                    {rescheduling ? "Reagendando…" : "Reagendar"}
                  </button>
                </div>
              </div>

              {schedule.length === 0 && <p className="hint" style={{ marginTop: 14 }}>Sem sessões geradas ainda.</p>}

              {schedule.length > 0 &&
                (() => {
                  const todayKey = new Date().toISOString().slice(0, 10);
                  const grouped = schedule.reduce<Record<string, ScheduleEntry[]>>((acc, entry) => {
                    const key = entry.item.scheduled_for.slice(0, 10);
                    (acc[key] ||= []).push(entry);
                    return acc;
                  }, {});
                  const priorityLabel = (p: number) => (p >= 0.6 ? "alta" : p >= 0.3 ? "média" : "baixa");

                  if (rotinaView === "semana") {
                    const today = new Date();
                    today.setHours(0, 0, 0, 0);
                    const mondayOffset = (today.getDay() + 6) % 7;
                    const weekStart = new Date(today);
                    weekStart.setDate(today.getDate() - mondayOffset + weekOffset * 7);
                    const days = Array.from({ length: 7 }, (_, i) => {
                      const d = new Date(weekStart);
                      d.setDate(weekStart.getDate() + i);
                      return d;
                    });
                    const weekLabel = `${weekStart.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" })} – ${days[6].toLocaleDateString("pt-BR", { day: "2-digit", month: "short" })}`;

                    return (
                      <>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 16, marginBottom: 10 }}>
                          <button className="ghost" onClick={() => setWeekOffset((w) => w - 1)} aria-label="Semana anterior">
                            ←
                          </button>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <b style={{ fontSize: "0.85rem" }}>{weekLabel}</b>
                            {weekOffset !== 0 && (
                              <button className="ghost" style={{ padding: "4px 10px", fontSize: "0.76rem" }} onClick={() => setWeekOffset(0)}>
                                Hoje
                              </button>
                            )}
                          </div>
                          <button className="ghost" onClick={() => setWeekOffset((w) => w + 1)} aria-label="Próxima semana">
                            →
                          </button>
                        </div>

                        <div className="week-grid">
                          {days.map((d) => {
                            const dateKey = d.toISOString().slice(0, 10);
                            const isToday = dateKey === todayKey;
                            const entries = (grouped[dateKey] || []).sort((a, b) => a.item.scheduled_for.localeCompare(b.item.scheduled_for));
                            return (
                              <div className={`week-col${isToday ? " is-today" : ""}`} key={dateKey}>
                                <div className="week-col-head">
                                  <small>{d.toLocaleDateString("pt-BR", { weekday: "short" })}</small>
                                  <b>{d.getDate()}</b>
                                </div>
                                <div className="week-col-body">
                                  {entries.length === 0 && <span className="week-empty">—</span>}
                                  {entries.map((entry) => {
                                    const when = new Date(entry.item.scheduled_for);
                                    const isDone = entry.session_status === "completed";
                                    const isSkipped = entry.session_status === "skipped";
                                    return (
                                      <div className={`day-chip${isDone ? " is-done" : ""}${isSkipped ? " is-skipped" : ""}`} key={entry.item.id}>
                                        <span className="day-chip-time">{when.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</span>
                                        <b>
                                          {entry.subject_name || "Assunto"}
                                          {entry.topic_name ? ` · ${entry.topic_name}` : ""}
                                        </b>
                                        <small>
                                          {entry.item.planned_minutes} min · prioridade {priorityLabel(entry.item.priority)}
                                        </small>
                                        {!isDone && !isSkipped && (
                                          <div className="day-chip-actions">
                                            <button className="ghost" disabled={itemActionId === entry.item.id} onClick={() => markItem(entry.item.id, "complete")}>
                                              Concluir
                                            </button>
                                            <button className="ghost" disabled={itemActionId === entry.item.id} onClick={() => markItem(entry.item.id, "skip")}>
                                              Pular
                                            </button>
                                          </div>
                                        )}
                                        {(isDone || isSkipped) && <small>{isDone ? "Concluída" : "Pulada"}</small>}
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </>
                    );
                  }

                  const dateKeys = Object.keys(grouped).sort();
                  const visibleKeys = showAllDays ? dateKeys : dateKeys.slice(0, 7);
                  const hiddenDays = dateKeys.length - visibleKeys.length;

                  return (
                    <>
                      {visibleKeys.map((dateKey) => {
                        const isToday = dateKey === todayKey;
                        const dayLabel = new Date(`${dateKey}T00:00:00`).toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "short" });
                        return (
                          <div key={dateKey} style={{ marginTop: 18 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                              <b style={{ fontSize: "0.82rem", textTransform: "capitalize", color: isToday ? "var(--accent)" : "var(--text-muted)" }}>
                                {isToday ? "Hoje" : dayLabel}
                              </b>
                              {isToday && <span className="status-dot" />}
                            </div>
                            {grouped[dateKey].map((entry) => {
                              const when = new Date(entry.item.scheduled_for);
                              const isDone = entry.session_status === "completed" || entry.session_status === "skipped";
                              return (
                                <div className="item" key={entry.item.id}>
                                  <div>
                                    <b>
                                      {entry.subject_name || "Assunto"}
                                      {entry.topic_name ? ` · ${entry.topic_name}` : ""}
                                    </b>
                                    <small>
                                      {when.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })} · {entry.item.planned_minutes} min · prioridade {priorityLabel(entry.item.priority)} ·{" "}
                                      {entry.session_status === "completed" ? "Concluída" : entry.session_status === "skipped" ? "Pulada" : "Planejada"}
                                    </small>
                                  </div>
                                  {!isDone && (
                                    <div style={{ display: "flex", gap: 8 }}>
                                      <button className="ghost" disabled={itemActionId === entry.item.id} onClick={() => markItem(entry.item.id, "complete")}>
                                        Concluir
                                      </button>
                                      <button className="ghost" disabled={itemActionId === entry.item.id} onClick={() => markItem(entry.item.id, "skip")}>
                                        Pular
                                      </button>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        );
                      })}

                      {hiddenDays > 0 && (
                        <button className="ghost" style={{ marginTop: 16 }} onClick={() => setShowAllDays(true)}>
                          Ver mais {hiddenDays} dias
                        </button>
                      )}
                      {showAllDays && dateKeys.length > 7 && (
                        <button className="ghost" style={{ marginTop: 16 }} onClick={() => setShowAllDays(false)}>
                          Mostrar menos
                        </button>
                      )}
                    </>
                  );
                })()}
            </>
          )}
        </motion.section>
      ) : tab === "usuarios" ? (
        <motion.section className="panel" initial="hidden" animate="show" variants={fadeUp} transition={{ duration: 0.4 }}>
          <h2>Usuários ativos</h2>
          {users.length === 0 && <p className="hint" style={{ marginTop: 10 }}>Nenhum usuário encontrado.</p>}
          {users.map((user) => (
            <div className="item" key={user.id}>
              <div className="user-row">
                <span className="avatar">{(user.full_name || "?").charAt(0).toUpperCase()}</span>
                <b>{user.full_name || "Sem nome"}</b>
              </div>
            </div>
          ))}
        </motion.section>
      ) : (
        <>
          <motion.section className="metrics" initial="hidden" animate="show" variants={fadeUp} transition={{ duration: 0.4 }}>
            <article>
              <b>{exams.length}</b>
              <small>Concursos</small>
            </article>
            <article>
              <b>{notices.length}</b>
              <small>Editais</small>
            </article>
            <article>
              <b>{subjectsCount}</b>
              <small>Disciplinas mapeadas</small>
            </article>
          </motion.section>

          <motion.section className="workspace" initial="hidden" animate="show" variants={fadeUp} transition={{ duration: 0.4, delay: 0.05 }}>
        <aside className="panel">
          <h2>Concursos</h2>
          <form style={{ marginTop: 12 }}>
            <select value={selected} onChange={(e) => setSelected(e.target.value)} aria-label="Concurso selecionado">
              {exams.length === 0 && <option value="">Nenhum concurso ainda</option>}
              {exams.map((exam) => (
                <option key={exam.id} value={exam.id}>
                  {exam.title}
                </option>
              ))}
            </select>
          </form>
          <form onSubmit={createExam}>
            <input required name="title" placeholder="Novo concurso" aria-label="Nome do novo concurso" />
            <input name="board" placeholder="Banca (opcional)" aria-label="Banca examinadora" />
            <button type="submit">Criar concurso</button>
          </form>
        </aside>

        <div>
          <section className="panel">
            <h2>Edital e análise</h2>

            {!selected && <p className="hint" style={{ marginTop: 10 }}>Crie ou selecione um concurso ao lado para importar um edital.</p>}

            {selected && (
              <form onSubmit={submitUpload} style={{ marginTop: 12 }}>
                <div
                  className={`dropzone${dragActive ? " active" : ""}${pendingFile ? " filled" : ""}`}
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragActive(true);
                  }}
                  onDragLeave={() => setDragActive(false)}
                  onDrop={handleDrop}
                  role="button"
                  tabIndex={0}
                >
                  <Upload size={18} />
                  <span>{pendingFile ? pendingFile.name : "Arraste o PDF aqui ou clique para escolher"}</span>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="application/pdf"
                    aria-label="Arquivo do edital em PDF"
                    style={{ display: "none" }}
                    onChange={(e) => pickFile(e.target.files?.[0])}
                  />
                </div>
                <button type="submit" disabled={!pendingFile || uploading} style={{ marginTop: 10 }}>
                  <Upload size={14} style={{ verticalAlign: -2, marginRight: 6 }} />
                  {uploading ? "Importando…" : "Importar edital"}
                </button>
              </form>
            )}

            {notices.length === 0 && <p className="hint" style={{ marginTop: 14 }}>Nenhum edital importado ainda para este concurso.</p>}

            {notices.map((notice) => {
              const analysis = notice.extraction_metadata.analysis;
              const subjectNames = analysis?.subjects?.map((s) => s.name).join(" · ");
              const label = subjectNames || (analysis ? "Nada identificado — confira se é o edital completo" : "Aguardando análise");
              return (
                <div className="item" key={notice.id}>
                  <div>
                    <b>{notice.filename}</b>
                    <small>{label}</small>
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="ghost" disabled={analyzingId === notice.id} onClick={() => analyzeNotice(notice.id)}>
                      {analyzingId === notice.id ? "Analisando…" : "Analisar"}
                    </button>
                    <button
                      className="ghost icon-button"
                      disabled={deletingId === notice.id}
                      onClick={() => deleteNotice(notice.id)}
                      aria-label={`Excluir ${notice.filename}`}
                      title="Excluir edital"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              );
            })}
          </section>

          <section className="cards">
            <article className="panel">
              <FileText size={18} color="var(--accent)" />
              <h2 style={{ marginTop: 10 }}>Provas e simulados</h2>
              <p>Questões e gabaritos importados por prova.</p>
            </article>
            <article className="panel" role="button" tabIndex={0} onClick={() => setTab("rotina")} style={{ cursor: "pointer" }}>
              <BookOpen size={18} color="var(--accent)" />
              <h2 style={{ marginTop: 10 }}>Rotina</h2>
              <p>{activePlan ? `${schedule.length} sessões planejadas — ver agenda` : "Gerar plano adaptativo de estudos"}</p>
            </article>
            <article className="panel">
              <Target size={18} color="var(--accent)" />
              <h2 style={{ marginTop: 10 }}>Competitividade</h2>
              <p>Margem e nota de corte estimadas aparecem aqui.</p>
            </article>
          </section>
        </div>
          </motion.section>
        </>
      )}
    </main>
  );
}

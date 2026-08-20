"use client";

import { DragEvent, FormEvent, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { BookOpen, FileText, LayoutGrid, LogOut, Sparkles, Target, Upload, Users } from "lucide-react";

type Exam = { id: string; title: string };
type Notice = {
  id: string;
  filename: string;
  extraction_metadata: { analysis?: { subjects?: { name: string }[] } };
};
type ActiveUser = { id: string; full_name: string | null };
type Me = { id: string; email: string; full_name: string | null };

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
  const [tab, setTab] = useState<"painel" | "usuarios">("painel");
  const [msg, setMsg] = useState("Entre para conectar seus dados.");
  const [me, setMe] = useState<Me | null>(null);
  const [username, setUsername] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
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
    const form = new FormData(event.currentTarget);
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
      event.currentTarget.reset();
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
    try {
      await req(`/api/v1/exams/${selected}/notices/${noticeId}/analyze`, { method: "POST" });
      await loadNotices();
      setMsg("Edital analisado.");
    } catch (error) {
      setMsg(error instanceof Error ? error.message : "Não deu pra analisar o edital");
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
        <button className={tab === "usuarios" ? "" : "ghost"} role="tab" aria-selected={tab === "usuarios"} onClick={() => setTab("usuarios")}>
          <Users size={14} style={{ verticalAlign: -2, marginRight: 6 }} />
          Usuários ativos
        </button>
      </div>

      {tab === "usuarios" ? (
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

            {notices.map((notice) => (
              <div className="item" key={notice.id}>
                <div>
                  <b>{notice.filename}</b>
                  <small>{notice.extraction_metadata.analysis?.subjects?.map((s) => s.name).join(" · ") || "Aguardando análise"}</small>
                </div>
                <button className="ghost" onClick={() => analyzeNotice(notice.id)}>
                  Analisar
                </button>
              </div>
            ))}
          </section>

          <section className="cards">
            <article className="panel">
              <FileText size={18} color="var(--accent)" />
              <h2 style={{ marginTop: 10 }}>Provas e simulados</h2>
              <p>Questões e gabaritos importados por prova.</p>
            </article>
            <article className="panel">
              <BookOpen size={18} color="var(--accent)" />
              <h2 style={{ marginTop: 10 }}>Rotina</h2>
              <p>Seu plano adaptativo de estudos aparece aqui.</p>
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

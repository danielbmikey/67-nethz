import { createContext, useCallback, useContext, useEffect, useState } from "react";
import axios from "axios";
import { BrowserRouter, Link, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { Activity, ArrowUp, CalendarDays, Check, ChevronRight, Clapperboard, Download, Eye, EyeOff, Flag, Gamepad2, Heart, Instagram, LogIn, LogOut, Mail, MessageCircle, Plus, Radio, Shield, ShieldCheck, Sparkles, Trash2, Trophy, Twitch, UserPlus, Users, X, Youtube } from "lucide-react";
import "@/App.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const client = axios.create({ baseURL: API, withCredentials: true });
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("neth_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

const AuthContext = createContext(null);
const useAuth = () => useContext(AuthContext);

function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const [modal, setModal] = useState(null); // "login" | "signup" | null
  useEffect(() => {
    (async () => {
      if (localStorage.getItem("neth_token")) {
        try { const r = await client.get("/auth/me"); setUser(r.data); } catch { localStorage.removeItem("neth_token"); }
      }
      setReady(true);
    })();
  }, []);
  const login = async (email, password, remember = false) => {
    const r = await client.post("/auth/login", { email, password, remember });
    localStorage.setItem("neth_token", r.data.token);
    setUser(r.data);
    setModal(null);
    return r.data;
  };
  const signup = async (payload) => {
    const r = await client.post("/auth/signup", payload);
    localStorage.setItem("neth_token", r.data.token);
    setUser(r.data);
    setModal(null);
    return r.data;
  };
  const logout = async () => {
    try { await client.post("/auth/logout"); } catch {}
    localStorage.removeItem("neth_token");
    setUser(null);
  };
  const updateUser = (patch) => setUser(u => ({ ...u, ...patch }));
  const requireAuth = useCallback((action) => {
    if (user) { action(); return true; }
    setModal("login");
    return false;
  }, [user]);
  return <AuthContext.Provider value={{ user, ready, login, signup, logout, updateUser, modal, setModal, requireAuth }}>{children}{modal && <AuthModal/>}</AuthContext.Provider>;
}

function AuthModal() {
  const { modal, setModal, login, signup } = useAuth();
  const [form, setForm] = useState({ email: "", password: "", nickname: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const isSignup = modal === "signup";
  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      if (isSignup) await signup(form);
      else await login(form.email, form.password);
    } catch (ex) { setErr(ex?.response?.data?.detail || "Falhou. Tente novamente."); }
    finally { setBusy(false); }
  };
  return <Modal title={isSignup ? "Entra pra tropa" : "Bem-vindo de volta"} onClose={() => setModal(null)}>
    <p className="muted" style={{marginTop:-10, marginBottom:20, fontSize:13}}>
      {isSignup ? "Cria sua conta e comece a sugerir jogos, mandar clipes e comentar." : "Faça login pra votar, comentar e enviar clipes."}
    </p>
    <form className="form" onSubmit={submit}>
      {isSignup && <input required minLength={3} maxLength={24} placeholder="Nickname (3-24 caracteres)" data-testid="auth-nickname-input" value={form.nickname} onChange={e=>setForm({...form,nickname:e.target.value})}/>}
      <input required type="email" placeholder="Email" data-testid="auth-email-input" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/>
      <input required type="password" minLength={6} placeholder="Senha (mínimo 6)" data-testid="auth-password-input" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/>
      {err && <div className="err" data-testid="auth-error">{err}</div>}
      <button className="btn primary" disabled={busy} data-testid="auth-submit-button">{isSignup ? <><UserPlus size={16}/> Criar conta</> : <><LogIn size={16}/> Entrar</>}</button>
    </form>
    <div className="auth-swap">
      {isSignup ? <>Já é da tropa? <button data-testid="auth-switch-login" onClick={()=>setModal("login")}>Fazer login</button></> : <>Novo por aqui? <button data-testid="auth-switch-signup" onClick={()=>setModal("signup")}>Criar conta</button></>}
    </div>
  </Modal>;
}

function Gate({ children }) {
  const { user, ready } = useAuth();
  if (!ready) return <div className="boot-screen" data-testid="boot-screen">CARREGANDO NETH//HQ...</div>;
  if (!user) return <AuthGate/>;
  return children;
}

function AuthGate() {
  const { login, signup } = useAuth();
  const [view, setView] = useState("login"); // login | signup | forgot | reset
  const [form, setForm] = useState({ email: "", password: "", nickname: "", code: "", remember: false });
  const [showPw, setShowPw] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const swap = (v) => { setView(v); setErr(""); setMsg(""); };
  const copy = {
    login: "Área exclusiva da tropa. Faça login pra sugerir jogos, votar, mandar clipes e comentar.",
    signup: "Cria sua conta e entra pra tropa. Leva menos de um minuto.",
    forgot: "Digite seu email e enviaremos um código de recuperação.",
    reset: "Digite o código que chegou no seu email e crie uma nova senha.",
  };
  const submit = async (e) => {
    e.preventDefault(); setErr(""); setMsg(""); setBusy(true);
    try {
      if (view === "login") await login(form.email, form.password, form.remember);
      else if (view === "signup") await signup({ email: form.email, password: form.password, nickname: form.nickname });
      else if (view === "forgot") {
        const r = await client.post("/auth/forgot-password", { email: form.email });
        setMsg(r.data.message);
        setView("reset");
      } else {
        const r = await client.post("/auth/reset-password", { email: form.email, code: form.code, new_password: form.password });
        setMsg(r.data.message);
        setForm({ ...form, password: "", code: "" });
        setView("login");
      }
    } catch (ex) { setErr(ex?.response?.data?.detail || "Falhou. Tente novamente."); }
    finally { setBusy(false); }
  };
  const pwField = (placeholder) => <div className="pw-row">
    <input required type={showPw ? "text" : "password"} minLength={6} placeholder={placeholder} data-testid="gate-password-input" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/>
    <button type="button" className="pw-toggle" data-testid="toggle-password-visibility" onClick={()=>setShowPw(!showPw)}>{showPw ? <EyeOff size={16}/> : <Eye size={16}/>}</button>
  </div>;
  return <div className="auth-gate" data-testid="auth-gate">
    <div className="scanline"/>
    <div className="gate-panel">
      <img className="gate-avatar" src="/twitch_avatar.png" alt="nethzzzzz"/>
      <h1>NETHZZZZ</h1>
      <small className="gate-sub">CUIUDOS DELICIOSOS FAN CLUB</small>
      <p className="muted gate-copy">{copy[view]}</p>
      {msg && <div className="ok-msg" data-testid="gate-success-message">{msg}</div>}
      <form className="form" onSubmit={submit}>
        {view === "signup" && <input required minLength={3} maxLength={24} placeholder="Nickname (3-24 caracteres)" data-testid="gate-nickname-input" value={form.nickname} onChange={e=>setForm({...form,nickname:e.target.value})}/>}
        {view !== "reset" && <input required type="email" placeholder="Email" data-testid="gate-email-input" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/>}
        {view === "reset" && <input required maxLength={6} placeholder="Código de 6 dígitos" data-testid="gate-code-input" value={form.code} onChange={e=>setForm({...form,code:e.target.value})}/>}
        {view !== "forgot" && pwField(view === "reset" ? "Nova senha (mínimo 6)" : "Senha (mínimo 6)")}
        {view === "login" && <div className="remember-row">
          <label><input type="checkbox" checked={form.remember} data-testid="remember-me-checkbox" onChange={e=>setForm({...form,remember:e.target.checked})}/> Lembrar de mim (30 dias)</label>
          <button type="button" className="forgot-link" data-testid="forgot-password-link" onClick={()=>swap("forgot")}>Esqueci minha senha</button>
        </div>}
        {err && <div className="err" data-testid="gate-error">{err}</div>}
        <button className="btn primary" disabled={busy} data-testid="gate-submit-button">
          {view === "login" && <><LogIn size={16}/> Entrar</>}
          {view === "signup" && <><UserPlus size={16}/> Criar conta</>}
          {view === "forgot" && <><Mail size={16}/> Enviar código</>}
          {view === "reset" && <><ShieldCheck size={16}/> Redefinir senha</>}
        </button>
      </form>
      <div className="auth-swap">
        {view === "login" && <>Novo por aqui? <button data-testid="gate-switch-signup" onClick={()=>swap("signup")}>Criar conta</button></>}
        {view === "signup" && <>Já é da tropa? <button data-testid="gate-switch-login" onClick={()=>swap("login")}>Fazer login</button></>}
        {(view === "forgot" || view === "reset") && <>Lembrou a senha? <button data-testid="gate-back-login" onClick={()=>swap("login")}>Voltar ao login</button></>}
      </div>
    </div>
  </div>;
}

function VerifyBanner() {
  const { user, updateUser } = useAuth();
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  if (!user || user.role === "admin" || user.is_verified) return null;
  const verify = async (e) => {
    e.preventDefault(); setErr(""); setMsg("");
    try { await client.post("/auth/verify", { code }); updateUser({ is_verified: true }); }
    catch (ex) { setErr(ex?.response?.data?.detail || "Código inválido."); }
  };
  const resendCode = async () => {
    setErr(""); setMsg("");
    try { await client.post("/auth/resend-verification"); setMsg("Código reenviado! Confira seu email."); }
    catch (ex) { setErr(ex?.response?.data?.detail || "Não foi possível reenviar."); }
  };
  return <div className="verify-banner" data-testid="verify-banner">
    <Mail size={16}/>
    <span>Verifique seu email pra confirmar sua conta na tropa.</span>
    <form onSubmit={verify}>
      <input maxLength={6} placeholder="Código de 6 dígitos" value={code} onChange={e=>setCode(e.target.value)} data-testid="verify-code-input"/>
      <button className="btn primary sm" data-testid="verify-submit-button"><ShieldCheck size={14}/> Verificar</button>
      <button type="button" className="btn outline sm" onClick={resendCode} data-testid="resend-verification-button">Reenviar</button>
    </form>
    {msg && <em className="ok" data-testid="verify-success">{msg}</em>}
    {err && <em className="bad" data-testid="verify-error">{err}</em>}
  </div>;
}

function useCommunity() {
  const [data, setData] = useState({ games: [], clips: [], polls: [], schedule: [], stats: { members: 0 }, ranking: [] });
  const [loading, setLoading] = useState(true);
  const refresh = async () => {
    try {
      const [games, clips, polls, schedule, stats, ranking] = await Promise.all(["games","clips","polls","schedule","stats","ranking"].map(x => client.get(`/${x}`)));
      setData({ games: games.data, clips: clips.data, polls: polls.data, schedule: schedule.data, stats: stats.data, ranking: ranking.data });
    } finally { setLoading(false); }
  };
  useEffect(() => { refresh(); }, []);
  return { ...data, loading, refresh };
}

function Nav() {
  const loc = useLocation();
  const { user, logout, setModal } = useAuth();
  const nav = useNavigate();
  const items = [["/","Arena",Gamepad2],["/clips","Clipes",Clapperboard],["/schedule","Agenda",CalendarDays],["/polls","Enquetes",Trophy]];
  return <header className="topbar">
    <Link to="/" className="brand" data-testid="brand-home">
      <img className="brand-avatar" src="/twitch_avatar.png" alt="nethzzzzz" data-testid="brand-avatar"/>
      <span><b>NETHZZZZ</b><small>CUIUDOS DELICIOSOS FAN CLUB</small></span>
    </Link>
    <nav>
      {items.map(([to, label, Icon]) => <Link key={to} data-testid={`nav-${label.toLowerCase()}`} className={loc.pathname === to ? "active" : ""} to={to}><Icon size={16}/>{label}</Link>)}
    </nav>
    <div className="auth-slot">
      {user ? <>
        <span className="chip" data-testid="user-chip"><span className="chip-dot"/> {user.nickname}</span>
        {user.role === "admin" && <button className="admin-link" data-testid="nav-admin" onClick={()=>nav("/admin")}><Shield size={16}/></button>}
        <button className="admin-link" data-testid="logout-button" onClick={logout}><LogOut size={16}/></button>
      </> : <>
        <button className="btn outline sm" data-testid="open-login-modal" onClick={()=>setModal("login")}><LogIn size={14}/> Entrar</button>
        <button className="btn primary sm" data-testid="open-signup-modal" onClick={()=>setModal("signup")}><UserPlus size={14}/> Criar conta</button>
      </>}
    </div>
  </header>;
}

function Layout({ children }) {
  return <><Nav/><VerifyBanner/><main>{children}</main><footer>
    <span>© 2026 NETHZZZZ HQ</span>
    <span className="live-dot"><i/> COMUNIDADE ONLINE</span>
    <span className="socials">
      <a href="https://twitch.tv/nethzzzzz" target="_blank" rel="noreferrer" data-testid="social-twitch"><Twitch size={16}/></a>
      <a href="https://youtube.com" target="_blank" rel="noreferrer" data-testid="social-youtube"><Youtube size={16}/></a>
      <a href="https://instagram.com" target="_blank" rel="noreferrer" data-testid="social-instagram"><Instagram size={16}/></a>
    </span>
  </footer></>;
}

function Hero({ members }) {
  const { setModal, user } = useAuth();
  return <section className="hero">
    <div className="hero-copy">
      <div className="eyebrow"><i/> TRANSMISSÃO EM BREVE <span>•</span> QUARTA 20:00</div>
      <h1>A Tropa<br/><em>Decide.</em></h1>
      <p>O quartel-general da comunidade do Neth. Sugira o próximo jogo, compartilhe aquele clipe absurdo e faça a live acontecer.</p>
      <div className="hero-actions">
        {!user && <button className="btn primary" onClick={()=>setModal("signup")} data-testid="hero-signup-button"><UserPlus size={17}/> Entrar na tropa</button>}
        <Link className="text-link" to="/clips" data-testid="hero-clips-link">Explorar clipes <ChevronRight size={16}/></Link>
      </div>
    </div>
    <div className="hero-art">
      <div className="scanline"/>
      <span className="avatar-ring"><img src="/twitch_avatar.png" alt="nethzzzzz" data-testid="hero-avatar"/></span>
      <div className="status-chip"><Radio size={16}/> TROPA <b data-testid="hero-members-count">{members}</b></div>
      <div className="hero-code">NETH//HQ<br/><span>PLAY. VOTE. REPEAT.</span></div>
    </div>
  </section>;
}

function Statbar({ games, clips, members }) {
  return <div className="statbar">
    <div><span className="stat-icon cyan"><Gamepad2/></span><b data-testid="stat-games-count">{games.length}</b><small>SUGESTÕES ATIVAS</small></div>
    <div><span className="stat-icon pink"><Clapperboard/></span><b data-testid="stat-clips-count">{clips.length}</b><small>CLIPES DA TROPA</small></div>
    <div><span className="stat-icon yellow"><Users/></span><b data-testid="stat-members-count">{members}</b><small>MEMBROS DA TROPA</small></div>
    <div className="quote">"O chat escolhe, o Neth sofre." <span>— regra #1</span></div>
  </div>;
}

const BADGE_ICONS = { verified: ShieldCheck, strategist: Gamepad2, curator: Trophy, director: Clapperboard, legend: Sparkles, voice: MessageCircle, elector: Check };

function Ranking({ ranking }) {
  return <section className="section">
    <div className="section-head">
      <div>
        <div className="eyebrow yellow-text">HALL DA FAMA</div>
        <h2>Ranking da Tropa</h2>
        <p className="subhead">Top 10 membros mais ativos. Sugira, vote e comente pra subir.</p>
      </div>
    </div>
    {ranking.length ? <div className="rank-list" data-testid="ranking-list">
      {ranking.map((r, i) => <Link to={`/perfil/${encodeURIComponent(r.nickname)}`} className={`rank-row ${i < 3 ? "top" : ""}`} key={r.nickname} data-testid={`rank-row-${i+1}`}>
        <span className="rank-pos">#{String(i+1).padStart(2,"0")}</span>
        <b className="rank-nick">{r.nickname} {r.is_verified && <ShieldCheck size={13}/>}</b>
        <span className="rank-break mono">{r.games} jogos • {r.clips} clipes • {r.comments} comentários • {r.votes} votos</span>
        <b className="rank-score">{r.score}<small>PTS</small></b>
      </Link>)}
    </div> : <div className="empty" data-testid="ranking-empty"><Trophy/> Ainda ninguém pontuou. Sugira um jogo e abra o ranking!</div>}
  </section>;
}

function ReportButton({ target_id, target_type }) {
  const { requireAuth } = useAuth();
  const [busy, setBusy] = useState(false);
  const report = async () => {
    if (!requireAuth(() => {})) return;
    const reason = window.prompt("Motivo da denúncia:");
    if (!reason) return;
    setBusy(true);
    try {
      await client.post("/reports", { target_id, target_type, reason });
      alert("Denúncia enviada. A tropa agradece!");
    } catch (ex) {
      alert(ex?.response?.data?.detail || "Não foi possível enviar a denúncia.");
    } finally { setBusy(false); }
  };
  return <button className="report-btn" disabled={busy} onClick={report} data-testid={`report-${target_type}-${target_id}`} title="Denunciar"><Flag size={13}/></button>;
}

function SuggestionCard({ game, onVote, onComment }) {
  return <article className="suggestion" data-testid={`suggestion-card-${game.id}`}>
    <div className="vote">
      <button onClick={() => onVote(game.id)} data-testid={`vote-game-${game.id}`}><ArrowUp size={18}/></button>
      <b>{game.votes}</b><small>VOTOS</small>
    </div>
    <div className="suggestion-body">
      <div className="card-top">
        <span className={`tag ${game.status === "Jogado" ? "green" : ""}`}>{game.status}</span>
        <span className="mono">{game.platform}</span>
      </div>
      <h3>{game.title}</h3>
      <p>{game.description}</p>
      <div className="meta">
        <span>por <Link className="nick-link" to={`/perfil/${encodeURIComponent(game.submitted_by)}`} data-testid={`profile-link-${game.id}`}>{game.submitted_by}</Link></span>
        <div className="meta-actions">
          <button className="comment-link" onClick={() => onComment(game)} data-testid={`comment-game-${game.id}`}><MessageCircle size={14}/> comentar</button>
          <ReportButton target_id={game.id} target_type="game"/>
        </div>
      </div>
    </div>
  </article>;
}

function SuggestPage({ community }) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState({ title: "", genre: "", description: "" });
  const [err, setErr] = useState("");
  const { requireAuth } = useAuth();
  const openModal = () => { if (requireAuth(() => setOpen(true))) setOpen(true); };
  const submit = async (e) => {
    e.preventDefault(); setErr("");
    try {
      await client.post("/games", form);
      setForm({ title: "", genre: "", description: "" });
      setOpen(false);
      community.refresh();
    } catch (ex) { setErr(ex?.response?.data?.detail || "Falha ao enviar."); }
  };
  const vote = async (id) => {
    if (!requireAuth(() => {})) return;
    try { await client.post(`/games/${id}/vote`); community.refresh(); }
    catch (ex) { alert(ex?.response?.data?.detail || "Não foi possível votar."); }
  };
  return <>
    <Hero members={community.stats.members}/>
    <Statbar games={community.games} clips={community.clips} members={community.stats.members}/>
    <section className="section" id="suggestions">
      <div className="section-head">
        <div>
          <div className="eyebrow cyan-text">01 / DECISÃO DO CHAT</div>
          <h2>Sugestões de jogos</h2>
        </div>
        <button className="btn outline" onClick={openModal} data-testid="open-suggestion-modal"><Plus size={16}/> Nova sugestão</button>
      </div>
      <div className="board-grid">
        {community.games.map((g) => <SuggestionCard key={g.id} game={g} onVote={vote} onComment={setSelected}/>)}
      </div>
      {!community.games.length && <div className="empty" data-testid="games-empty"><Gamepad2/> Nenhuma sugestão ainda. Seja o primeiro a colocar um jogo na fila!</div>}
    </section>
    <Ranking ranking={community.ranking}/>
    {selected && <Comments target={selected} target_type="game" onClose={() => setSelected(null)}/>}
    {open && <Modal title="Coloque um jogo na fila" onClose={() => setOpen(false)}>
      <form onSubmit={submit} className="form">
        <input required placeholder="Nome do jogo" data-testid="suggestion-title-input" value={form.title} onChange={e => setForm({...form, title: e.target.value})}/>
        <div className="form-row">
          <input required placeholder="Gênero" data-testid="suggestion-genre-input" value={form.genre} onChange={e => setForm({...form, genre: e.target.value})}/>
          <input placeholder="Plataforma (PC, PS5...)" data-testid="suggestion-platform-input" onChange={e => setForm({...form, platform: e.target.value})}/>
        </div>
        <textarea required placeholder="Por que o Neth deveria jogar?" data-testid="suggestion-description-input" value={form.description} onChange={e => setForm({...form, description: e.target.value})}/>
        {err && <div className="err">{err}</div>}
        <button className="btn primary" data-testid="submit-suggestion-button"><Check size={16}/> Enviar para a tropa</button>
      </form>
    </Modal>}
  </>;
}

function Clips({ community }) {
  const [form, setForm] = useState({ title: "", url: "" });
  const [err, setErr] = useState("");
  const [selected, setSelected] = useState(null);
  const { requireAuth } = useAuth();
  const add = async e => {
    e.preventDefault(); setErr("");
    if (!requireAuth(() => {})) return;
    try {
      await client.post("/clips", form);
      setForm({ title: "", url: "" });
      community.refresh();
    } catch (ex) { setErr(ex?.response?.data?.detail || "Falha ao enviar."); }
  };
  const like = async (id) => {
    if (!requireAuth(() => {})) return;
    try { await client.post(`/clips/${id}/like`); community.refresh(); }
    catch (ex) { alert(ex?.response?.data?.detail || "Não foi possível curtir."); }
  };
  return <section className="page-section">
    <div className="section-head">
      <div>
        <div className="eyebrow pink-text">02 / MOMENTOS IMORTAIS</div>
        <h2>Clip hub</h2>
        <p className="subhead">Os melhores momentos da live, direto da tropa.</p>
      </div>
    </div>
    <div className="clip-layout">
      <div className="clip-feed">
        {community.clips.map((clip, i) => <article className="clip-card" key={clip.id} data-testid={`clip-card-${clip.id}`}>
          <div className={`clip-thumb thumb-${i % 2}`}><Clapperboard size={30}/><span>CLIP {String(i+1).padStart(2,"0")}</span></div>
          <div className="clip-content">
            <div className="card-top">
              <span className="tag pink">EM DESTAQUE</span>
              <span className="mono">@nethzzzz</span>
            </div>
            <h3>{clip.title}</h3>
            <p>por <Link className="nick-link" to={`/perfil/${encodeURIComponent(clip.submitted_by)}`} data-testid={`clip-profile-link-${clip.id}`}>{clip.submitted_by}</Link></p>
            <div className="clip-actions">
              <a href={clip.url} target="_blank" rel="noreferrer" className="text-link" data-testid={`watch-clip-${clip.id}`}>Assistir agora <ChevronRight size={15}/></a>
              <div className="meta-actions">
                <button className="icon-btn" onClick={()=>setSelected(clip)} data-testid={`comment-clip-${clip.id}`}><MessageCircle size={16}/></button>
                <button className="icon-btn" data-testid={`like-clip-${clip.id}`} onClick={()=>like(clip.id)}><Heart size={16}/> {clip.likes}</button>
                <ReportButton target_id={clip.id} target_type="clip"/>
              </div>
            </div>
          </div>
        </article>)}
        {!community.clips.length && <div className="empty" data-testid="clips-empty"><Clapperboard/> Nenhum clipe ainda. Manda o primeiro momento lendário!</div>}
      </div>
      <form className="submit-clip" onSubmit={add}>
        <div className="eyebrow pink-text">COMPARTILHAR</div>
        <h3>Achou um momento lendário?</h3>
        <p>Cole o link do YouTube, Twitch ou Kick e deixe a tropa votar.</p>
        <input required placeholder="Título do clipe" data-testid="clip-title-input" value={form.title} onChange={e=>setForm({...form, title: e.target.value})}/>
        <input required type="url" placeholder="https://..." data-testid="clip-url-input" value={form.url} onChange={e=>setForm({...form, url: e.target.value})}/>
        {err && <div className="err">{err}</div>}
        <button className="btn primary" data-testid="submit-clip-button"><Plus size={16}/> Enviar clipe</button>
      </form>
    </div>
    {selected && <Comments target={selected} target_type="clip" onClose={()=>setSelected(null)}/>}
  </section>;
}

function Comments({ target, target_type, onClose }) {
  const [comments, setComments] = useState([]);
  const [content, setContent] = useState("");
  const [err, setErr] = useState("");
  const { user, setModal } = useAuth();
  const load = useCallback(async () => {
    const r = await client.get(`/comments/${target.id}`);
    setComments(r.data);
  }, [target.id]);
  useEffect(() => { load(); }, [load]);
  const add = async (e) => {
    e.preventDefault(); setErr("");
    if (!user) { setModal("login"); return; }
    try {
      await client.post("/comments", { target_id: target.id, target_type, content });
      setContent("");
      load();
    } catch (ex) { setErr(ex?.response?.data?.detail || "Falha ao comentar."); }
  };
  return <Modal title={`Comentários • ${target.title}`} onClose={onClose}>
    <div className="comments">
      {comments.map(c => <div className="comment" key={c.id}>
        <b>{c.author}</b>
        <p>{c.content}</p>
      </div>)}
      {!comments.length && <p className="muted">Seja o primeiro a comentar.</p>}
      <form onSubmit={add} className="comment-form">
        <input required maxLength={500} placeholder={user ? "Escreva para a tropa..." : "Faça login para comentar"} data-testid="comment-input" value={content} onChange={e => setContent(e.target.value)}/>
        <button className="icon-btn" data-testid="submit-comment-button"><MessageCircle size={17}/></button>
      </form>
      {err && <div className="err">{err}</div>}
    </div>
  </Modal>;
}

function Schedule({ community }) {
  return <section className="page-section">
    <div className="section-head">
      <div>
        <div className="eyebrow yellow-text">03 / PRÓXIMAS TRANSMISSÕES</div>
        <h2>Agenda da tropa</h2>
        <p className="subhead">Não perde a próxima call.</p>
      </div>
      <div className="live-badge"><i/> PRÓXIMA LIVE <b>QUARTA, 20:00</b></div>
    </div>
    <div className="schedule-list">
      {community.schedule.map((item) => <div className={`schedule-row ${item.is_special ? "special" : ""}`} key={item.id} data-testid={`schedule-item-${item.id}`}>
        <span className="day">{item.day}</span>
        <b className="time">{item.time}</b>
        <div>
          <h3>{item.game}</h3>
          <p>{item.description}</p>
        </div>
        {item.is_special && <span className="tag yellow">ESPECIAL</span>}
      </div>)}
    </div>
  </section>;
}

function Polls({ community }) {
  const [polls, setPolls] = useState(community.polls);
  const { requireAuth } = useAuth();
  useEffect(() => setPolls(community.polls), [community.polls]);
  const vote = async (id, i) => {
    if (!requireAuth(() => {})) return;
    try {
      await client.post(`/polls/${id}/vote?option_index=${i}`);
      const next = await client.get("/polls");
      setPolls(next.data);
    } catch (ex) { alert(ex?.response?.data?.detail || "Não foi possível votar."); }
  };
  return <section className="page-section">
    <div className="section-head">
      <div>
        <div className="eyebrow cyan-text">04 / VOZ DA COMUNIDADE</div>
        <h2>Enquetes ativas</h2>
        <p className="subhead">O voto é seu. O sofrimento é do Neth.</p>
      </div>
    </div>
    <div className="poll-grid">
      {polls.map(p => <article className="poll" key={p.id} data-testid={`poll-card-${p.id}`}>
        <div className="poll-icon"><Trophy/></div>
        <h3>{p.question}</h3>
        {p.options.map((o, i) => <button key={o.text} className="poll-option" onClick={() => vote(p.id, i)} data-testid={`poll-option-${p.id}-${i}`}>
          <span>{o.text}</span><b>{o.votes}</b>
        </button>)}
      </article>)}
    </div>
  </section>;
}

function Profile() {
  const { nickname } = useParams();
  const [p, setP] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    setP(null); setErr("");
    client.get(`/users/${encodeURIComponent(nickname)}/profile`).then(r => setP(r.data)).catch(() => setErr("Membro não encontrado."));
  }, [nickname]);
  if (err) return <section className="page-section"><div className="empty" data-testid="profile-not-found"><Users/> {err}</div></section>;
  if (!p) return <section className="page-section"><div className="empty">Carregando perfil...</div></section>;
  return <section className="page-section" data-testid="profile-page">
    <div className="profile-head">
      <span className="profile-avatar" data-testid="profile-avatar">{p.nickname[0].toUpperCase()}</span>
      <div>
        <h2 data-testid="profile-nickname">{p.nickname} {p.is_verified && <span className="tag green">VERIFICADO</span>}</h2>
        <p className="muted mono">na tropa desde {new Date(p.created_at).toLocaleDateString("pt-BR")}</p>
      </div>
    </div>
    <div className="admin-stats profile-stats">
      <div><b data-testid="profile-games-count">{p.stats.games}</b><span>jogos sugeridos</span></div>
      <div><b data-testid="profile-clips-count">{p.stats.clips}</b><span>clipes enviados</span></div>
      <div><b data-testid="profile-comments-count">{p.stats.comments}</b><span>comentários</span></div>
      <div><b data-testid="profile-votes-count">{p.stats.votes}</b><span>votos</span></div>
    </div>
    <h3 className="profile-sub"><Trophy size={16}/> Conquistas</h3>
    {p.badges.length ? <div className="badge-grid" data-testid="profile-badges">
      {p.badges.map(b => { const Icon = BADGE_ICONS[b.id] || Sparkles; return <div className="badge" key={b.id} data-testid={`badge-${b.id}`}>
        <Icon size={18}/>
        <div><b>{b.label}</b><p>{b.desc}</p></div>
      </div>; })}
    </div> : <p className="muted" data-testid="profile-no-badges">Nenhuma conquista ainda. Participa aí!</p>}
    <h3 className="profile-sub"><Gamepad2 size={16}/> Jogos sugeridos</h3>
    {p.games.length ? <div className="profile-list" data-testid="profile-games">
      {p.games.map(g => <div className="profile-item" key={g.id}>
        <span className={`tag ${g.status === "Jogado" ? "green" : ""}`}>{g.status}</span>
        <b>{g.title}</b>
        <span className="mono">{g.votes} votos</span>
      </div>)}
    </div> : <p className="muted">Nenhum jogo sugerido ainda.</p>}
    <h3 className="profile-sub"><Clapperboard size={16}/> Clipes enviados</h3>
    {p.clips.length ? <div className="profile-list" data-testid="profile-clips">
      {p.clips.map(c => <div className="profile-item" key={c.id}>
        <span className="tag pink">CLIPE</span>
        <a href={c.url} target="_blank" rel="noreferrer" className="nick-link">{c.title}</a>
        <span className="mono">{c.likes} curtidas</span>
      </div>)}
    </div> : <p className="muted">Nenhum clipe enviado ainda.</p>}
  </section>;
}

function Modal({ title, onClose, children }) {
  return <div className="modal-backdrop" onClick={onClose}>
    <div className="modal" onClick={e => e.stopPropagation()}>
      <button className="close" onClick={onClose} data-testid="close-modal"><X/></button>
      <div className="eyebrow cyan-text">NETH//HQ</div>
      <h2>{title}</h2>
      {children}
    </div>
  </div>;
}

function Admin() {
  const { user, setModal } = useAuth();
  const nav = useNavigate();
  const [tab, setTab] = useState("users");
  const [users, setUsers] = useState([]);
  const [reports, setReports] = useState([]);
  const load = async () => {
    try {
      const [u, r] = await Promise.all([client.get("/admin/users"), client.get("/reports")]);
      setUsers(u.data);
      setReports(r.data);
    } catch (ex) {
      if (ex?.response?.status === 401) setModal("login");
    }
  };
  useEffect(() => {
    if (!user) { setModal("login"); return; }
    if (user.role !== "admin") { nav("/"); return; }
    load();
  }, [user]);
  const download = (fmt) => {
    const token = localStorage.getItem("neth_token");
    const url = `${API}/admin/users/export?fmt=${fmt}`;
    fetch(url, { credentials: "include", headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(r => r.blob())
      .then(blob => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `nethzzzz-users.${fmt}`;
        a.click();
      });
  };
  const resolveReport = async (id, status) => {
    await client.patch(`/reports/${id}?status=${encodeURIComponent(status)}`);
    load();
  };
  if (!user || user.role !== "admin") return <section className="page-section"><div className="empty" data-testid="admin-locked"><Shield/> Faça login como streamer para acessar.</div></section>;
  return <section className="page-section">
    <div className="section-head">
      <div>
        <div className="eyebrow pink-text">05 / CENTRAL DE CONTROLE</div>
        <h2>Moderação</h2>
        <p className="subhead">Tudo sob controle, sem tirar o olho da live.</p>
      </div>
    </div>
    <div className="admin-stats">
      <div><b data-testid="stat-users">{users.length}</b><span>membros da tropa</span></div>
      <div><b data-testid="stat-reports">{reports.filter(r=>r.status==="Pendente").length}</b><span>denúncias pendentes</span></div>
      <div><b data-testid="stat-resolved">{reports.filter(r=>r.status!=="Pendente").length}</b><span>denúncias resolvidas</span></div>
    </div>
    <div className="admin-tabs">
      <button className={tab==="users"?"active":""} onClick={()=>setTab("users")} data-testid="tab-users"><Users size={15}/> Contas</button>
      <button className={tab==="reports"?"active":""} onClick={()=>setTab("reports")} data-testid="tab-reports"><Flag size={15}/> Denúncias</button>
    </div>
    {tab === "users" ? <>
      <div className="export-bar">
        <button className="btn outline sm" onClick={()=>download("csv")} data-testid="export-csv-button"><Download size={14}/> Exportar CSV</button>
        <button className="btn outline sm" onClick={()=>download("txt")} data-testid="export-txt-button"><Download size={14}/> Exportar TXT</button>
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Nickname</th><th>Email</th><th>Criação</th><th>IP criação</th><th>Último IP</th><th>Último login</th></tr></thead>
          <tbody>
            {users.map(u => <tr key={u.id} data-testid={`user-row-${u.id}`}>
              <td>{u.nickname}</td>
              <td>{u.email}</td>
              <td className="mono">{new Date(u.created_at).toLocaleString("pt-BR")}</td>
              <td className="mono">{u.creation_ip}</td>
              <td className="mono">{u.last_ip}</td>
              <td className="mono">{u.last_login ? new Date(u.last_login).toLocaleString("pt-BR") : "—"}</td>
            </tr>)}
            {!users.length && <tr><td colSpan="6" className="empty-row">Nenhum membro cadastrado ainda.</td></tr>}
          </tbody>
        </table>
      </div>
    </> : <div className="reports">
      {reports.map(r => <div className="report" key={r.id} data-testid={`report-row-${r.id}`}>
        <Flag size={18}/>
        <div>
          <b>{r.target_type} denunciado</b>
          <p>{r.reason}</p>
          <small className="mono">por {r.reported_by} • {new Date(r.created_at).toLocaleString("pt-BR")}</small>
        </div>
        <span className="tag">{r.status}</span>
        {r.status === "Pendente" && <>
          <button className="icon-btn" onClick={()=>resolveReport(r.id,"Resolvido")} data-testid={`resolve-report-${r.id}`}><Check size={14}/></button>
          <button className="icon-btn" onClick={()=>resolveReport(r.id,"Descartado")} data-testid={`dismiss-report-${r.id}`}><Trash2 size={14}/></button>
        </>}
      </div>)}
      {!reports.length && <div className="empty"><Sparkles/> Nenhuma denúncia. A tropa está tranquila.</div>}
    </div>}
  </section>;
}

function App() {
  const community = useCommunity();
  return <BrowserRouter>
    <AuthProvider>
      <Gate>
      <Layout>
        <Routes>
          <Route path="/" element={<SuggestPage community={community}/>}/>
          <Route path="/suggest" element={<SuggestPage community={community}/>}/>
          <Route path="/clips" element={<Clips community={community}/>}/>
          <Route path="/schedule" element={<Schedule community={community}/>}/>
          <Route path="/polls" element={<Polls community={community}/>}/>
          <Route path="/perfil/:nickname" element={<Profile/>}/>
          <Route path="/admin" element={<Admin/>}/>
        </Routes>
      </Layout>
      </Gate>
    </AuthProvider>
  </BrowserRouter>;
}
export default App;

import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  Activity,
  ArrowUpRight,
  BookOpen,
  Database,
  Filter,
  KeyRound,
  LayoutDashboard,
  LogOut,
  MonitorCog,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ApiError, ControllerApi, type Credentials } from "../application/api/client";
import { knowledgeDocuments } from "../application/knowledge/registry";
import {
  type Station,
  type StationRole,
  type StationStatus,
} from "../domain/station";
import { HelpHint, InfoNote, MetricCard, SectionHeading, StatusBadge } from "./components/ui";
import "./styles.css";

type Screen = "overview" | "stations" | "knowledge";

export function App() {
  const [credentials, setCredentials] = useState<Credentials | null>(null);
  if (!credentials) {
    return <LoginPage onAuthenticated={setCredentials} />;
  }
  return <ControllerShell credentials={credentials} onLogout={() => setCredentials(null)} />;
}

function LoginPage({ onAuthenticated }: { onAuthenticated: (credentials: Credentials) => void }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const candidate = { username, password };
    try {
      await new ControllerApi(candidate).health();
      onAuthenticated(candidate);
    } catch (caught) {
      setError(caught instanceof ApiError && caught.status === 401
        ? "Неверный логин или пароль."
        : "Controller API недоступен. Проверьте backend и Vite proxy.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <div className="login-grid">
        <section className="login-story">
          <div className="brand-mark large">TN</div>
          <p className="eyebrow">CONTROL ROOM / 01</p>
          <h1>Обновления игр под контролем.</h1>
          <p>Единая операторская для станций, Windows-агентов и безопасного preflight перед публикацией.</p>
          <div className="story-points">
            <span><b>01</b> Состояние станций и heartbeat</span>
            <span><b>02</b> Понятные блокирующие проверки</span>
            <span><b>03</b> Инструкции всегда под рукой</span>
          </div>
          <div className="login-signal"><span className="pulse-dot" /> Controller API · protected session</div>
        </section>
        <form className="login-card" onSubmit={submit}>
          <div className="login-card-heading"><div><p className="eyebrow">OPERATOR ACCESS</p><h2>Вход оператора</h2></div><span className="secure-badge"><KeyRound aria-hidden size={12} /> BASIC AUTH</span></div>
          <p className="muted">Данные авторизации остаются в памяти текущей вкладки.</p>
          <label>
            Логин
            <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
            <small>Текущий операторский пользователь: admin.</small>
          </label>
          <label>
            Пароль Basic Auth
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" />
            <small>Не сохраняется в localStorage, cookies или frontend build.</small>
          </label>
          {error && <p className="error-message">{error}</p>}
          <button className="primary-button" disabled={busy || !password} type="submit">
            <ShieldCheck aria-hidden size={17} /> {busy ? "Проверяем…" : "Войти в операторскую"}
          </button>
          <details className="help-box">
            <summary>Почему нужен backend?</summary>
            <p>Browser не видит процессы Windows и состояние диска D:. Эти данные сообщает агент через Controller API.</p>
          </details>
        </form>
      </div>
    </main>
  );
}

function ControllerShell({ credentials, onLogout }: { credentials: Credentials; onLogout: () => void }) {
  const [screen, setScreen] = useState<Screen>("overview");
  const api = useMemo(() => new ControllerApi(credentials), [credentials]);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark">TN</div>
          <div><strong>TrueNAS</strong><span>Controller</span></div>
        </div>
        <nav>
          <NavButton active={screen === "overview"} onClick={() => setScreen("overview")} icon={LayoutDashboard} label="Обзор" caption="Контроль системы" />
          <NavButton active={screen === "stations"} onClick={() => setScreen("stations")} icon={MonitorCog} label="Станции и агенты" caption="Heartbeat и enrollment" />
          <NavButton active={screen === "knowledge"} onClick={() => setScreen("knowledge")} icon={BookOpen} label="База знаний" caption="Инструкции оператора" />
        </nav>
        <div className="sidebar-footer">
          <div className="sidebar-status"><span className="pulse-dot" /><span><strong>Local workspace</strong><small>Безопасный режим</small></span></div>
          <button className="ghost-button" onClick={onLogout}><LogOut aria-hidden size={15} /> Выйти из сессии</button>
        </div>
      </aside>
      <main className="content">
        <div className="topbar"><span className="topbar-context">OPERATOR CONSOLE <b>/</b> {screen === "overview" ? "OVERVIEW" : screen === "stations" ? "STATIONS" : "KNOWLEDGE"}</span><span className="operator-chip"><span className="avatar">A</span> admin <span className="online-dot" /></span></div>
        {screen === "overview" && <OverviewPage api={api} onOpenStations={() => setScreen("stations")} onOpenKnowledge={() => setScreen("knowledge")} />}
        {screen === "stations" && <StationsPage api={api} />}
        {screen === "knowledge" && <KnowledgePage />}
      </main>
    </div>
  );
}

function OverviewPage({ api, onOpenStations, onOpenKnowledge }: { api: ControllerApi; onOpenStations: () => void; onOpenKnowledge: () => void }) {
  const [health, setHealth] = useState("Не проверено");
  const [stations, setStations] = useState<Station[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setError(null);
    try {
      const [healthResponse, stationResponse] = await Promise.all([api.health(), api.listStations()]);
      setHealth(healthResponse.status === "ok" ? "Controller online" : healthResponse.status);
      setStations(stationResponse);
    } catch (caught) {
      setHealth("Ошибка");
      setError(caught instanceof Error ? caught.message : "Неизвестная ошибка");
    }
  }

  return (
    <PageHeader title="Обзор" subtitle="Состояние контроллера и безопасные следующие шаги.">
      <section className="hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">RUNTIME CHECK</p>
          <div className="hero-title"><span className={health === "Ошибка" ? "pulse-dot danger" : "pulse-dot"} /><h2>{health}</h2></div>
          <p className="muted">Начните с проверки backend, затем зарегистрируйте station и агент.</p>
        </div>
        <div className="hero-action"><span>Последняя проверка вручную</span><button className="primary-button" onClick={refresh}><RefreshCw aria-hidden size={16} /> Проверить backend <ArrowUpRight aria-hidden size={16} /></button></div>
      </section>
      {error && <p className="error-message">{error}</p>}
      <div className="metric-grid">
        <Metric label="Всего станций" value={stations.length ? stations.length.toString().padStart(2, "0") : "—"} hint="Источник истины — Controller API." accent="blue" icon={Database} />
        <Metric label="Online сейчас" value={stations.length ? stations.filter((station) => station.status === "online").length.toString().padStart(2, "0") : "—"} hint="Только свежий heartbeat считается online." accent="green" icon={Activity} />
        <Metric label="Безопасный режим" value="DRY-RUN" hint="Опасные операции требуют preflight и подтверждения." accent="amber" icon={ShieldCheck} />
      </div>
      <InfoNote>Публикация обновлений пока не выполняется из UI: сначала проверяются backend, агент и preflight-политики.</InfoNote>
      <section className="info-grid">
        <InfoCard title="Следующий шаг" text="Откройте раздел «Станции и агенты», создайте station и используйте одноразовый enrollment token." action="Открыть станции" onClick={onOpenStations} />
        <InfoCard title="Нужна инструкция?" text="В базе знаний собраны запуск backend, установка агента и управление refresh-командами." action="Открыть базу знаний" onClick={onOpenKnowledge} />
      </section>
    </PageHeader>
  );
}

function StationsPage({ api }: { api: ControllerApi }) {
  const [stations, setStations] = useState<Station[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [createdToken, setCreatedToken] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StationStatus | "all">("all");
  const [form, setForm] = useState({ display_name: "", hostname: "", role: "client" as StationRole });

  useEffect(() => { void loadStations(); }, []);

  async function loadStations() {
    try {
      setStations(await api.listStations());
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось получить stations.");
    }
  }

  async function createStation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const result = await api.createStation(form);
      setCreatedToken(result.enrollment_token);
      setForm({ display_name: "", hostname: "", role: "client" });
      await loadStations();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось создать station.");
    }
  }

  const visibleStations = stations.filter((station) => {
    const matchesQuery = `${station.display_name} ${station.hostname}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery && (statusFilter === "all" || station.status === statusFilter);
  });
  const statusCounts = stations.reduce<Record<string, number>>((counts, station) => {
    counts[station.status] = (counts[station.status] ?? 0) + 1;
    return counts;
  }, {});

  return (
    <PageHeader title="Станции и агенты" subtitle="Серверное состояние станций, enrollment и следующий heartbeat.">
      <SectionHeading title="Реестр станций" description="Offline и stale никогда не считаются готовыми к publish." action={<button className="secondary-button" onClick={loadStations}><RefreshCw aria-hidden size={15} /> Обновить</button>} />
      {error && <p className="error-message">{error}</p>}
      <div className="station-toolbar"><label className="search-field"><span><Search aria-hidden size={13} /> Поиск</span><input placeholder="Имя или hostname" value={query} onChange={(event) => setQuery(event.target.value)} /></label><label className="filter-field"><span><Filter aria-hidden size={13} /> Статус</span><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StationStatus | "all")}><option value="all">Все ({stations.length})</option><option value="online">Online ({statusCounts.online ?? 0})</option><option value="stale">Stale ({statusCounts.stale ?? 0})</option><option value="offline">Offline ({statusCounts.offline ?? 0})</option></select></label><div className="toolbar-note"><span className="pulse-dot" /> {visibleStations.length} в текущем списке</div></div>
      <div className="table-card">
        <table><thead><tr><th>Станция</th><th>Роль</th><th>Статус</th><th>Пояснение</th></tr></thead>
          <tbody>{visibleStations.length === 0 ? <tr><td colSpan={4} className="empty-cell">{stations.length === 0 ? "Станций пока нет или backend ещё не ответил." : "По выбранному фильтру ничего не найдено."}</td></tr> : visibleStations.map((station) => <tr key={station.station_id}><td><strong>{station.display_name}</strong><span className="table-subtitle">{station.hostname}</span></td><td><span className="role-chip">{station.role}</span></td><td><StatusBadge status={station.status} /></td><td>{station.status === "online" ? "Heartbeat свежий." : station.status === "stale" ? "Heartbeat устарел." : station.status === "offline" ? "Heartbeat не получен." : "Станция отключена."}</td></tr>)}</tbody>
        </table>
      </div>
      <section className="form-card">
        <div className="section-heading"><div><h2>Добавить station</h2><p className="muted">Controller выдаст одноразовый token с ограниченным TTL.</p></div></div>
        <form className="station-form" onSubmit={createStation}>
          <label>Отображаемое имя<input required value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} /><HelpHint>Имя, которое оператор увидит в таблицах и wizard.</HelpHint></label>
          <label>Hostname<input required value={form.hostname} onChange={(event) => setForm({ ...form, hostname: event.target.value })} /><HelpHint>Фактическое имя Windows-ПК; это не стабильная identity.</HelpHint></label>
          <label>Роль<select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value as StationRole })}><option value="client">client — игровой ПК</option><option value="admin">admin — админский ПК</option></select><HelpHint>Роль влияет на preflight policy, а не на права Basic Auth.</HelpHint></label>
          <button className="primary-button" type="submit">Создать station</button>
        </form>
        {createdToken && <div className="secret-warning"><strong>Token показан один раз.</strong><p>Передайте его на клиентский ПК по защищённому каналу и не сохраняйте в UI. Token: <code>{createdToken}</code></p><button className="secondary-button" onClick={() => setCreatedToken(null)}>Скрыть token</button></div>}
      </section>
    </PageHeader>
  );
}

function KnowledgePage() {
  const [selectedId, setSelectedId] = useState(knowledgeDocuments[0].id);
  const [query, setQuery] = useState("");
  const documents = knowledgeDocuments.filter((document) => `${document.title} ${document.description} ${document.content}`.toLowerCase().includes(query.toLowerCase()));
  const selected = knowledgeDocuments.find((document) => document.id === selectedId) ?? documents[0] ?? knowledgeDocuments[0];
  return (
    <PageHeader title="База знаний" subtitle="Пошаговые инструкции с пояснениями для оператора и администраторов Windows.">
      <div className="knowledge-intro"><div><span className="eyebrow">FIELD MANUAL</span><h2>Инструкции без поиска по репозиторию</h2><p className="muted">Документы собраны в allowlist и доступны оператору в одной рабочей области.</p></div><div className="knowledge-count"><strong>{knowledgeDocuments.length}</strong><span>документа</span></div></div>
      <div className="knowledge-layout">
        <aside className="knowledge-nav"><input placeholder="Поиск по инструкциям" value={query} onChange={(event) => setQuery(event.target.value)} />{documents.map((document) => <button className={document.id === selected.id ? "knowledge-link selected" : "knowledge-link"} key={document.id} onClick={() => setSelectedId(document.id)}><strong>{document.title}</strong><span>{document.description}</span></button>)}</aside>
        <article className="markdown-card"><ReactMarkdown remarkPlugins={[remarkGfm]}>{selected.content}</ReactMarkdown></article>
      </div>
    </PageHeader>
  );
}

function PageHeader({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return <div className="page"><header className="page-header"><div><p className="eyebrow">OPERATOR CONSOLE</p><h1>{title}</h1><p className="muted">{subtitle}</p></div></header>{children}</div>;
}

function NavButton({ active, icon: Icon, label, caption, onClick }: { active: boolean; icon: LucideIcon; label: string; caption: string; onClick: () => void }) {
  return <button className={active ? "nav-button active" : "nav-button"} onClick={onClick}><span className="nav-icon"><Icon aria-hidden size={16} /></span><span className="nav-copy"><strong>{label}</strong><small>{caption}</small></span></button>;
}

function Metric({ label, value, hint, accent, icon }: { label: string; value: string; hint: string; accent: "blue" | "green" | "amber"; icon: LucideIcon }) {
  return <MetricCard label={label} value={value} hint={hint} accent={accent} icon={icon} />;
}

function InfoCard({ title, text, action, onClick }: { title: string; text: string; action: string; onClick: () => void }) {
  return <article className="info-card"><h3>{title}</h3><p>{text}</p><button className="text-button" onClick={onClick}>{action} <ArrowUpRight aria-hidden size={15} /></button></article>;
}

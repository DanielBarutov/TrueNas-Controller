import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ApiError, ControllerApi, type Credentials } from "../application/api/client";
import { knowledgeDocuments } from "../application/knowledge/registry";
import {
  statusDescription,
  statusLabel,
  type Station,
  type StationRole,
} from "../domain/station";
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

  async function submit(event: React.FormEvent<HTMLFormElement>) {
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
      <form className="login-card" onSubmit={submit}>
        <p className="eyebrow">TRUE NAS CONTROLLER</p>
        <h1>Вход оператора</h1>
        <p className="muted">Frontend обращается только к собственному Controller API.</p>
        <label>
          Логин
          <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
          <small>Для текущей конфигурации используется операторский пользователь admin.</small>
        </label>
        <label>
          Пароль Basic Auth
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" />
          <small>Credential хранится только в памяти этой вкладки и не записывается в localStorage.</small>
        </label>
        {error && <p className="error-message">{error}</p>}
        <button className="primary-button" disabled={busy || !password} type="submit">
          {busy ? "Проверяем…" : "Войти"}
        </button>
        <details className="help-box">
          <summary>Почему нужен backend?</summary>
          <p>Browser не видит процессы Windows и состояние диска D:. Эти данные сообщает агент через Controller API.</p>
        </details>
      </form>
    </main>
  );
}

function ControllerShell({ credentials, onLogout }: { credentials: Credentials; onLogout: () => void }) {
  const [screen, setScreen] = useState<Screen>("overview");
  const api = useMemo(() => new ControllerApi(credentials), [credentials]);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">TRUE NAS CONTROLLER</p>
          <h1>Операторская</h1>
        </div>
        <nav>
          <NavButton active={screen === "overview"} onClick={() => setScreen("overview")}>Обзор</NavButton>
          <NavButton active={screen === "stations"} onClick={() => setScreen("stations")}>Станции и агенты</NavButton>
          <NavButton active={screen === "knowledge"} onClick={() => setScreen("knowledge")}>База знаний</NavButton>
        </nav>
        <button className="ghost-button" onClick={onLogout}>Выйти</button>
      </aside>
      <main className="content">
        {screen === "overview" && <OverviewPage api={api} onOpenStations={() => setScreen("stations")} onOpenKnowledge={() => setScreen("knowledge")} />}
        {screen === "stations" && <StationsPage api={api} />}
        {screen === "knowledge" && <KnowledgePage />}
      </main>
    </div>
  );
}

function OverviewPage({ api, onOpenStations, onOpenKnowledge }: { api: ControllerApi; onOpenStations: () => void; onOpenKnowledge: () => void }) {
  const [health, setHealth] = useState("Не проверено");
  const [stationCount, setStationCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setError(null);
    try {
      const [, stations] = await Promise.all([api.health(), api.listStations()]);
      setHealth("Controller online");
      setStationCount(stations.length);
    } catch (caught) {
      setHealth("Ошибка");
      setError(caught instanceof Error ? caught.message : "Неизвестная ошибка");
    }
  }

  return (
    <PageHeader title="Обзор" subtitle="Состояние контроллера и безопасные следующие шаги.">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">RUNTIME CHECK</p>
          <h2>{health}</h2>
          <p className="muted">Начните с проверки backend, затем зарегистрируйте station и агент.</p>
        </div>
        <button className="primary-button" onClick={refresh}>Проверить backend</button>
      </section>
      {error && <p className="error-message">{error}</p>}
      <div className="metric-grid">
        <Metric label="Зарегистрировано станций" value={stationCount === null ? "—" : stationCount.toString()} hint="Источник истины — Controller API, а не состояние UI." />
        <Metric label="TrueNAS операции" value="Заблокированы" hint="Frontend не вызывает TrueNAS напрямую." />
        <Metric label="Режим публикации" value="Dry-run first" hint="Опасные операции требуют серверного preflight и подтверждения." />
      </div>
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
  const [form, setForm] = useState({ display_name: "", hostname: "", role: "client" as StationRole });

  async function loadStations() {
    try {
      setStations(await api.listStations());
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось получить stations.");
    }
  }

  async function createStation(event: React.FormEvent<HTMLFormElement>) {
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

  return (
    <PageHeader title="Станции и агенты" subtitle="Серверное состояние станций, enrollment и следующий heartbeat.">
      <div className="section-heading">
        <div><h2>Реестр станций</h2><p className="muted">Offline и stale никогда не считаются готовыми к publish.</p></div>
        <button className="secondary-button" onClick={loadStations}>Обновить</button>
      </div>
      {error && <p className="error-message">{error}</p>}
      <div className="table-card">
        <table><thead><tr><th>Станция</th><th>Роль</th><th>Статус</th><th>Пояснение</th></tr></thead>
          <tbody>{stations.length === 0 ? <tr><td colSpan={4} className="empty-cell">Нажмите «Обновить», чтобы загрузить станции.</td></tr> : stations.map((station) => <tr key={station.station_id}><td><strong>{station.display_name}</strong><span className="table-subtitle">{station.hostname}</span></td><td>{station.role}</td><td><span className={`status-badge status-${station.status}`}>{statusLabel[station.status]}</span></td><td>{statusDescription[station.status]}</td></tr>)}</tbody>
        </table>
      </div>
      <section className="form-card">
        <div className="section-heading"><div><h2>Добавить station</h2><p className="muted">Controller выдаст одноразовый token с ограниченным TTL.</p></div></div>
        <form className="station-form" onSubmit={createStation}>
          <label>Отображаемое имя<input required value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} /><small>Имя, которое оператор увидит в таблицах и wizard.</small></label>
          <label>Hostname<input required value={form.hostname} onChange={(event) => setForm({ ...form, hostname: event.target.value })} /><small>Фактическое имя Windows-ПК; это не стабильная identity.</small></label>
          <label>Роль<select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value as StationRole })}><option value="client">client — игровой ПК</option><option value="admin">admin — админский ПК</option></select><small>Роль влияет на preflight policy, а не на права Basic Auth.</small></label>
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
      <div className="knowledge-layout">
        <aside className="knowledge-nav"><input placeholder="Поиск по инструкциям" value={query} onChange={(event) => setQuery(event.target.value)} />{documents.map((document) => <button className={document.id === selected.id ? "knowledge-link selected" : "knowledge-link"} key={document.id} onClick={() => setSelectedId(document.id)}><strong>{document.title}</strong><span>{document.description}</span></button>)}</aside>
        <article className="markdown-card"><ReactMarkdown remarkPlugins={[remarkGfm]}>{selected.content}</ReactMarkdown></article>
      </div>
    </PageHeader>
  );
}

function PageHeader({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return <div className="page"><header className="page-header"><div><p className="eyebrow">OPERATOR CONSOLE</p><h1>{title}</h1><p className="muted">{subtitle}</p></div></header>{children}</div>;
}

function NavButton({ active, children, onClick }: { active: boolean; children: React.ReactNode; onClick: () => void }) {
  return <button className={active ? "nav-button active" : "nav-button"} onClick={onClick}>{children}</button>;
}

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return <article className="metric-card"><span>{label}</span><strong>{value}</strong><small>{hint}</small></article>;
}

function InfoCard({ title, text, action, onClick }: { title: string; text: string; action: string; onClick: () => void }) {
  return <article className="info-card"><h3>{title}</h3><p>{text}</p><button className="text-button" onClick={onClick}>{action} →</button></article>;
}

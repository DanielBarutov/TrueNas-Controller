import { useEffect, useState } from "react";
import { Plus, RefreshCw, ShieldAlert, Trash2 } from "lucide-react";
import type { ControllerApi, ProcessRule, ProcessRuleRole, ProcessRuleSeverity } from "../../application/api/client";
import { HelpHint, InfoNote, SectionHeading } from "../components/ui";

export function ProcessRulesPage({ api }: { api: ControllerApi }) {
  const [rules, setRules] = useState<ProcessRule[]>([]);
  const [name, setName] = useState("");
  const [role, setRole] = useState<ProcessRuleRole>("client");
  const [severity, setSeverity] = useState<ProcessRuleSeverity>("blocking");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      setRules(await api.listProcessRules());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить политику процессов.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function addRule() {
    const normalized = name.trim();
    if (!normalized) {
      setError("Укажите имя процесса, например steam.exe.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await api.createProcessRule({
        name: normalized,
        role,
        required_closed: true,
        severity,
        enabled: true,
        persistent_policy: false,
      });
      setRules((current) => [...current, created].sort((left, right) => left.name.localeCompare(right.name)));
      setName("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось добавить правило.");
    } finally {
      setBusy(false);
    }
  }

  async function removeRule(rule: ProcessRule) {
    if (!window.confirm(`Удалить правило ${rule.name}?`)) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteProcessRule(rule.id);
      setRules((current) => current.filter((item) => item.id !== rule.id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось удалить правило.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <p className="eyebrow">PREFLIGHT POLICY</p>
        <h1>Процессы перед обновлением</h1>
        <p className="muted">Агент присылает список процессов, а backend сравнивает его с этой политикой.</p>
      </header>
      {error && <p className="error-message">{error}</p>}
      <section className="form-card">
        <SectionHeading eyebrow="ADD RULE" title="Добавить процесс в проверку" description="Blocking остановит publish и потребует кнопки «Повторить проверку» после закрытия процесса." />
        <div className="station-form">
          <label>Имя процесса<input value={name} onChange={(event) => setName(event.target.value)} placeholder="steam.exe" /></label>
          <label>Роль<select value={role ?? "all"} onChange={(event) => setRole(event.target.value === "all" ? null : event.target.value as ProcessRuleRole)}><option value="client">client</option><option value="admin">admin</option><option value="all">все станции</option></select></label>
          <label>Реакция<select value={severity} onChange={(event) => setSeverity(event.target.value as ProcessRuleSeverity)}><option value="blocking">blocking — остановить publish</option><option value="warning">warning — показать предупреждение</option></select></label>
          <button className="primary-button" type="button" onClick={() => void addRule()} disabled={busy}><Plus aria-hidden size={16} /> Добавить правило</button>
        </div>
        <HelpHint>Имя сравнивается без учёта регистра. Процесс не завершается автоматически — оператор ждёт закрытия на клиентском ПК.</HelpHint>
      </section>
      <section className="form-card">
        <SectionHeading title="Активная политика" description="Удаление правила не удаляет историю heartbeat и уже выполненных обновлений." action={<button className="secondary-button" type="button" onClick={() => void load()} disabled={busy}><RefreshCw aria-hidden size={15} /> Обновить</button>} />
        {rules.length === 0 ? <InfoNote><ShieldAlert aria-hidden size={16} /> Правил пока нет. Добавьте лаунчеры и процессы игр, которые должны быть закрыты.</InfoNote> : <div className="table-card"><table><thead><tr><th>Процесс</th><th>Роль</th><th>Реакция</th><th>Закрыть перед publish</th><th /></tr></thead><tbody>{rules.map((rule) => <tr key={rule.id}><td><strong>{rule.name}</strong></td><td>{rule.role ?? "все"}</td><td><span className={rule.severity === "blocking" ? "role-chip" : "status-badge status-stale"}>{rule.severity}</span></td><td>{rule.required_closed ? "Да" : "Нет"}</td><td><button className="danger-button" type="button" onClick={() => void removeRule(rule)} disabled={busy}><Trash2 aria-hidden size={15} /> Удалить</button></td></tr>)}</tbody></table></div>}
      </section>
    </div>
  );
}

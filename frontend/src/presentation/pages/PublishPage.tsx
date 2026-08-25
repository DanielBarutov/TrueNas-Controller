import { Fragment, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Check,
  CircleAlert,
  CircleCheck,
  CircleHelp,
  CircleX,
  ClipboardCheck,
  LockKeyhole,
  RefreshCw,
  Rocket,
  Server,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ControllerApi } from "../../application/api/client";
import type { PreflightCheck, PreflightReport, PublishDispatchResponse, PublishGate, PublishHistoryItem, PublishJobDraft, PublishJobReadModel, PublishPrepareResponse, PublishTargetReadModel } from "../../domain/publish";
import { publishStatusLabel } from "../../domain/publish";
import { isStationSelectableForPublish, sortStations, type SortDirection, type Station, type StationSortField } from "../../domain/station";
import { StationSortControls } from "../components/StationSortControls";
import { HelpHint, InfoNote, SectionHeading, StatusBadge } from "../components/ui";

type WizardStep = 1 | 2 | 3 | 4;

const checkIcons: Record<PreflightCheck["status"], LucideIcon> = {
  pass: CircleCheck,
  block: CircleX,
  unknown: CircleHelp,
  warning: CircleAlert,
};

const reasonLabels: Record<string, string> = {
  admin_preflight_blocked: "Preflight админского ПК заблокирован.",
  operator_confirmation_required: "Нужно явное подтверждение оператора.",
  station_selection_required: "Нужно выбрать хотя бы одну клиентскую станцию.",
};

export function PublishPage({ api }: { api: ControllerApi }) {
  const [step, setStep] = useState<WizardStep>(1);
  const [stations, setStations] = useState<Station[]>([]);
  const [adminStationId, setAdminStationId] = useState("");
  const [selectedStationIds, setSelectedStationIds] = useState<string[]>([]);
  const [form, setForm] = useState({
    label: "",
    source_dataset: "games/master-games",
    description: "",
    dry_run: false,
    allow_hot_switch: false,
  });
  const [job, setJob] = useState<PublishJobDraft | null>(null);
  const [prepared, setPrepared] = useState<PublishPrepareResponse | null>(null);
  const [accepted, setAccepted] = useState<PublishDispatchResponse | null>(null);
  const [busy, setBusy] = useState<"loading" | "preparing" | "confirming" | "dispatching" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<PublishHistoryItem[]>([]);
  const [sortField, setSortField] = useState<StationSortField>("display_name");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const onlineAdminStations = useMemo(
    () => stations.filter((station) => station.role === "admin" && station.status === "online"),
    [stations],
  );
  const clientStations = useMemo(
    () => sortStations(stations.filter((station) => station.role === "client"), sortField, sortDirection),
    [sortDirection, sortField, stations],
  );
  const sortedAdminStations = useMemo(
    () => sortStations(onlineAdminStations, sortField, sortDirection),
    [onlineAdminStations, sortDirection, sortField],
  );

  useEffect(() => {
    void loadStations();
    void loadHistory();
  }, []);

  async function loadStations() {
    setBusy("loading");
    setError(null);
    try {
      const result = await api.listStations();
      setStations(result);
      const defaultAdmin = result.find(
        (station) => station.role === "admin" && station.status === "online",
      );
      if (!adminStationId && defaultAdmin) {
        setAdminStationId(defaultAdmin.station_id);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить станции.");
    } finally {
      setBusy(null);
    }
  }

  async function loadHistory() {
    try {
      setHistory(await api.listPublishJobs());
    } catch {
      // History is informative; the publish wizard remains usable if it is unavailable.
    }
  }

  function toggleStation(stationId: string) {
    setSelectedStationIds((current) =>
      current.includes(stationId)
        ? current.filter((id) => id !== stationId)
        : [...current, stationId],
    );
  }

  async function prepare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (selectedStationIds.length === 0) {
      setError("Выберите хотя бы одну online client station.");
      return;
    }
    setBusy("preparing");
    try {
      const draft = await api.createPublishJob({
        ...form,
        description: form.description || undefined,
        station_ids: selectedStationIds,
        idempotency_key: makeIdempotencyKey(),
      });
      const result = await api.preparePublishJob(draft.id, {
        admin_station_id: adminStationId || null,
        confirmation: null,
      });
      setJob(draft);
      setPrepared(result);
      setStep(2);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось подготовить publish job.");
    } finally {
      setBusy(null);
    }
  }

  async function confirmPreflight() {
    if (!job) {
      return;
    }
    setError(null);
    setBusy("confirming");
    try {
      const result = await api.preparePublishJob(job.id, {
        admin_station_id: adminStationId || null,
        confirmation: true,
      });
      setPrepared(result);
      if (result.gate.can_advance) {
        setStep(3);
      } else {
        setError("Сервер не разрешил переход: исправьте блокирующие проверки.");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось подтвердить preflight.");
    } finally {
      setBusy(null);
    }
  }

  async function retryPreflight() {
    if (!job) return;
    setError(null);
    setBusy("preparing");
    try {
      setPrepared(await api.preparePublishJob(job.id, {
        admin_station_id: adminStationId || null,
        confirmation: null,
      }));
      await loadStations();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось повторить preflight.");
    } finally {
      setBusy(null);
    }
  }

  async function dispatch() {
    if (!job || !prepared?.gate.can_advance) {
      return;
    }
    setError(null);
    setBusy("dispatching");
    try {
      const result = await api.dispatchPublishJob(job.id);
      setAccepted(result);
      setStep(4);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Сервер отклонил dispatch.");
    } finally {
      setBusy(null);
    }
  }

  function reset() {
    setStep(1);
    setJob(null);
    setPrepared(null);
    setAccepted(null);
    setSelectedStationIds([]);
    setError(null);
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">SAFE PUBLISH WIZARD</p>
          <h1>Публикация обновления</h1>
          <p className="muted">Серверный preflight, явное подтверждение и outbox-backed dispatch.</p>
        </div>
      </header>
      <WizardProgress current={step} />
      {error && <p className="error-message">{error}</p>}
      {step === 1 && (
        <ConfigurationStep
          form={form}
          setForm={setForm}
          stations={clientStations}
          adminStations={sortedAdminStations}
          sortField={sortField}
          sortDirection={sortDirection}
          setSortField={setSortField}
          setSortDirection={setSortDirection}
          adminStationId={adminStationId}
          setAdminStationId={setAdminStationId}
          selectedStationIds={selectedStationIds}
          toggleStation={toggleStation}
          onSubmit={prepare}
          onRefresh={loadStations}
          busy={busy}
        />
      )}
      {step === 2 && prepared && (
        <PreflightStep
          prepared={prepared}
          stations={stations}
          onBack={reset}
          onConfirm={confirmPreflight}
          onRetry={retryPreflight}
          busy={busy}
        />
      )}
      {step === 3 && prepared && (
        <ConfirmationStep
          prepared={prepared}
          stations={stations}
          dryRun={form.dry_run}
          allowHotSwitch={form.allow_hot_switch}
          onBack={() => setStep(2)}
          onDispatch={dispatch}
          busy={busy}
        />
      )}
      {step === 4 && accepted && (
        <JobProgressStep api={api} accepted={accepted} stations={stations} onReset={reset} />
      )}
      <PublishHistory api={api} items={history} onRefresh={loadHistory} />
    </div>
  );
}

function ConfigurationStep({
  form,
  setForm,
  stations,
  adminStations,
  sortField,
  sortDirection,
  setSortField,
  setSortDirection,
  adminStationId,
  setAdminStationId,
  selectedStationIds,
  toggleStation,
  onSubmit,
  onRefresh,
  busy,
}: {
  form: {
    label: string;
    source_dataset: string;
    description: string;
    dry_run: boolean;
    allow_hot_switch: boolean;
  };
  setForm: (value: typeof form) => void;
  stations: Station[];
  adminStations: Station[];
  sortField: StationSortField;
  sortDirection: SortDirection;
  setSortField: (value: StationSortField) => void;
  setSortDirection: (value: SortDirection) => void;
  adminStationId: string;
  setAdminStationId: (value: string) => void;
  selectedStationIds: string[];
  toggleStation: (stationId: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onRefresh: () => void;
  busy: "loading" | "preparing" | "confirming" | "dispatching" | null;
}) {
  return (
    <form className="publish-wizard" onSubmit={onSubmit}>
      <SectionHeading
        eyebrow="01 / CONFIGURE"
        title="Соберите безопасный draft"
        description="В этой точке меняются только параметры собственного API; storage mapping и TrueNAS остаются за backend."
        action={<button className="secondary-button" type="button" onClick={onRefresh} disabled={busy !== null}><RefreshCw aria-hidden size={15} /> Обновить станции</button>}
      />
      <div className="wizard-card form-card">
        <div className="wizard-form-grid">
          <label>
            Название публикации
            <input required value={form.label} onChange={(event) => setForm({ ...form, label: event.target.value })} placeholder="build-2026-08-23" />
            <HelpHint>Человекочитаемый label для job и аудита.</HelpHint>
          </label>
          <label>
            Исходный dataset
            <input required value={form.source_dataset} onChange={(event) => setForm({ ...form, source_dataset: event.target.value })} placeholder="games/master-games" />
            <HelpHint>Полный источник данных для snapshot: например, `games/master-games`. TrueNAS snapshot/clone работает со всем dataset, а не с отдельными играми.</HelpHint>
          </label>
          <label className="wide-field">
            Описание
            <textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Что меняется в этой публикации?" rows={3} />
            <HelpHint>Не добавляйте секреты, токены или mapping details.</HelpHint>
          </label>
        </div>
        <div className="option-grid">
          <label className="checkbox-option">
            <input type="checkbox" checked={form.dry_run} onChange={(event) => setForm({ ...form, dry_run: event.target.checked })} />
            <span><strong>dry_run</strong><small>Сначала только безопасная симуляция workflow.</small></span>
          </label>
          <label className="checkbox-option">
            <input type="checkbox" checked={form.allow_hot_switch} onChange={(event) => setForm({ ...form, allow_hot_switch: event.target.checked })} />
            <span><strong>allow_hot_switch</strong><small>Отключено по умолчанию; включайте только по отдельной policy.</small></span>
          </label>
        </div>
        {form.allow_hot_switch && <div className="option-warning"><AlertTriangle aria-hidden size={16} /> Hot switch не обходится server-side preflight и требует отдельного операционного согласования.</div>}
      </div>
      <div className="wizard-selection-grid">
        <section className="wizard-card form-card">
          <SectionHeading eyebrow="OPTIONAL ADMIN CHECK" title="Админский ПК не обязателен" description="Основная операция выполняется на TrueNAS: snapshot master dataset и clone в новый dataset." />
          <label>
            Админский ПК
            <select value={adminStationId} onChange={(event) => setAdminStationId(event.target.value)}>
              <option value="">Не использовать admin station</option>
              {adminStations.map((station) => <option key={station.station_id} value={station.station_id}>{station.display_name} · {station.hostname}</option>)}
            </select>
          </label>
          {adminStations.length === 0 && <InfoNote>Admin station не зарегистрирована — это допустимо для TrueNAS snapshot/clone workflow.</InfoNote>}
        </section>
        <section className="wizard-card form-card">
          <SectionHeading eyebrow="CLIENT TARGETS" title="Станции для публикации" description="Offline и stale недоступны для выбора." />
          <StationSortControls field={sortField} direction={sortDirection} onFieldChange={setSortField} onDirectionChange={setSortDirection} />
          <div className="station-choice-list">
            {stations.length === 0 && <p className="empty-cell">Нет зарегистрированных client stations.</p>}
            {stations.map((station) => (
              <StationChoice key={station.station_id} station={station} selected={selectedStationIds.includes(station.station_id)} onToggle={toggleStation} />
            ))}
          </div>
        </section>
      </div>
      <InfoNote><ShieldCheck aria-hidden size={16} /> Browser не вычисляет готовность самостоятельно: после создания draft backend повторно выполнит preflight и сохранит результат.</InfoNote>
      <div className="wizard-actions"><span className="muted">{selectedStationIds.length} client station выбрано</span><button className="primary-button" type="submit" disabled={busy !== null || selectedStationIds.length === 0}><ClipboardCheck aria-hidden size={16} /> {busy === "preparing" ? "Проверяем…" : "Создать draft и проверить" } <ArrowRight aria-hidden size={16} /></button></div>
    </form>
  );
}

function PreflightStep({
  prepared,
  stations,
  onBack,
  onConfirm,
  onRetry,
  busy,
}: {
  prepared: PublishPrepareResponse;
  stations: Station[];
  onBack: () => void;
  onConfirm: () => void;
  onRetry: () => void;
  busy: "loading" | "preparing" | "confirming" | "dispatching" | null;
}) {
  return (
    <section className="publish-wizard">
      <SectionHeading eyebrow="02 / SERVER PREFLIGHT" title="Проверки получены от backend" description="Каждый report привязан к station и snapshot. UNKNOWN не трактуется как PASS." />
      <GateBanner gate={prepared.gate} />
      <div className="report-grid">
        {prepared.admin_report && <ReportCard title="Admin station" report={prepared.admin_report} stationName={findStationName(stations, prepared.admin_report.station_id)} />}
        {prepared.client_reports.map((report) => <ReportCard key={report.station_id} title="Client station" report={report} stationName={findStationName(stations, report.station_id)} />)}
      </div>
      <div className="wizard-actions"><button className="ghost-button" type="button" onClick={onBack}><ArrowLeft aria-hidden size={15} /> Изменить draft</button><div className="wizard-actions"><button className="secondary-button" type="button" disabled={busy !== null} onClick={onRetry}><RefreshCw aria-hidden size={15} /> {busy === "preparing" ? "Проверяем…" : "Повторить проверку"}</button><button className="primary-button" type="button" disabled={busy !== null || !canRequestConfirmation(prepared.gate)} onClick={onConfirm}><ShieldCheck aria-hidden size={16} /> {busy === "confirming" ? "Подтверждаем…" : "Подтвердить preflight"} <ArrowRight aria-hidden size={16} /></button></div></div>
    </section>
  );
}

function PublishHistory({ api, items, onRefresh }: { api: ControllerApi; items: PublishHistoryItem[]; onRefresh: () => void }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<string, PublishJobReadModel>>({});
  const [loadingId, setLoadingId] = useState<string | null>(null);

  async function showDetails(jobId: string) {
    if (selectedId === jobId) {
      setSelectedId(null);
      return;
    }
    setSelectedId(jobId);
    if (details[jobId]) return;
    setLoadingId(jobId);
    try {
      const detail = await api.getPublishJob(jobId);
      setDetails((current) => ({ ...current, [jobId]: detail }));
    } finally {
      setLoadingId(null);
    }
  }

  return <section className="form-card publish-history"><SectionHeading eyebrow="UPDATE HISTORY" title="История обновлений" description="Последние 10 jobs. Кнопка «Подробнее» загружает сохранённый результат по станциям, mapping и timestamps." action={<button className="secondary-button" type="button" onClick={onRefresh}><RefreshCw aria-hidden size={15} /> Обновить историю</button>} />{items.length === 0 ? <p className="empty-cell">Заданий пока нет.</p> : <div className="table-card"><table><thead><tr><th>Время</th><th>Задание</th><th>Источник</th><th>Режим</th><th>Статус</th><th aria-label="Подробнее" /></tr></thead><tbody>{items.map((item) => <Fragment key={item.id}><tr><td>{item.created_at ? formatDate(item.created_at) : "—"}</td><td><strong>{item.label}</strong>{item.status_reason && <span className="table-subtitle">{item.status_reason}</span>}</td><td><code>{item.source_dataset}</code></td><td>{item.dry_run ? "DRY-RUN" : "APPLY"}</td><td><span className="role-chip">{publishStatusLabel[item.status]}</span></td><td><button className="text-button" type="button" onClick={() => void showDetails(item.id)}>{loadingId === item.id ? "Загрузка…" : selectedId === item.id ? "Скрыть" : "Подробнее"}</button></td></tr>{selectedId === item.id && <tr><td colSpan={6}><PublishJobDetails detail={details[item.id]} /></td></tr>}</Fragment>)}</tbody></table></div>}</section>;
}

function PublishJobDetails({ detail }: { detail?: PublishJobReadModel }) {
  if (!detail) return <p className="muted">Загружаем подробности…</p>;
  return <div className="history-details"><div className="history-detail-facts"><span><strong>Создано</strong>{formatOptionalDate(detail.created_at)}</span><span><strong>Завершено</strong>{formatOptionalDate(detail.completed_at)}</span><span><strong>Причина</strong>{detail.status_reason ?? "—"}</span></div>{detail.targets.map((target) => <div className="history-target" key={target.station_id}><strong>{target.station_id}</strong><span>preflight: {target.preflight_status ?? "—"} · switch: {target.switch_status ?? "—"} · verify: {target.verify_status ?? "—"}</span><span>старый mapping: <code>{target.old_mapping?.ref ?? "—"}</code></span><span>новый mapping: <code>{target.new_mapping?.ref ?? "—"}</code></span>{target.error_message && <span className="error-message">{target.error_code ?? "error"}: {target.error_message}</span>}</div>)}{detail.artifacts.length > 0 && <div className="history-artifacts"><strong>Созданные dataset</strong>{detail.artifacts.map((artifact) => <span key={artifact.id}><code>{artifact.dataset_name}</code> · {artifact.status}{artifact.is_current ? " · current" : ""} · {formatDate(artifact.created_at)}<small>snapshot: <code>{artifact.snapshot_ref}</code> · mapping: <code>{artifact.mapping_ref}</code></small></span>)}</div>}</div>;
}

function ConfirmationStep({
  prepared,
  stations,
  dryRun,
  allowHotSwitch,
  onBack,
  onDispatch,
  busy,
}: {
  prepared: PublishPrepareResponse;
  stations: Station[];
  dryRun: boolean;
  allowHotSwitch: boolean;
  onBack: () => void;
  onDispatch: () => void;
  busy: "loading" | "preparing" | "confirming" | "dispatching" | null;
}) {
  return (
    <section className="publish-wizard">
      <SectionHeading eyebrow="03 / OPERATOR CONFIRMATION" title="Проверки разрешили следующий шаг" description="Dispatch изменит persisted state и создаст минимальное outbox-событие для worker." />
      <GateBanner gate={prepared.gate} />
      <div className="confirmation-card">
        <div className="confirmation-icon"><LockKeyhole aria-hidden size={22} /></div>
        <div><h2>Подтвердить публикацию?</h2><p className="muted">Server preflight вернул ready. Следующий шаг не выполняет storage operation в browser.</p></div>
      </div>
      <div className="confirmation-facts">
        <span><strong>Режим</strong>{dryRun ? "DRY-RUN" : "LIVE policy"}</span>
        <span><strong>Hot switch</strong>{allowHotSwitch ? "Разрешён policy-флагом" : "Выключен"}</span>
        <span><strong>Станций</strong>{prepared.gate.selected_station_ids.length}</span>
      </div>
      <div className="report-grid compact-reports">
        {prepared.admin_report && <ReportCard title="Admin" report={prepared.admin_report} stationName={findStationName(stations, prepared.admin_report.station_id)} />}
        {prepared.client_reports.map((report) => <ReportCard key={report.station_id} title="Client" report={report} stationName={findStationName(stations, report.station_id)} />)}
      </div>
      <InfoNote><LockKeyhole aria-hidden size={16} /> После dispatch worker продолжит по durable outbox; UI не сообщает fake success о завершении TrueNAS workflow.</InfoNote>
      <div className="wizard-actions"><button className="ghost-button" type="button" onClick={onBack}><ArrowLeft aria-hidden size={15} /> Назад к проверкам</button><button className="primary-button" type="button" disabled={busy !== null || !prepared.gate.can_advance} onClick={onDispatch}><Rocket aria-hidden size={16} /> {busy === "dispatching" ? "Передаём worker…" : "Подтвердить и отправить"} <ArrowRight aria-hidden size={16} /></button></div>
    </section>
  );
}

function JobProgressStep({ api, accepted, stations, onReset }: { api: ControllerApi; accepted: PublishDispatchResponse; stations: Station[]; onReset: () => void }) {
  const [job, setJob] = useState<PublishJobReadModel | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [readError, setReadError] = useState<string | null>(null);

  async function refresh() {
    setRefreshing(true);
    try {
      setJob(await api.getPublishJob(accepted.job_id));
      setReadError(null);
    } catch (caught) {
      setReadError(caught instanceof Error ? caught.message : "Read model пока недоступен.");
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(interval);
  }, [api, accepted.job_id]);

  const status = job?.status ?? accepted.status;
  const progress = job ? overallProgress(job.targets) : 0;
  const terminal = status === "completed" || status === "partial_failure" || status === "failed";
  const simulationCompleted = terminal && status === "completed" && job?.dry_run === true;
  const statusTitle = simulationCompleted ? "Симуляция завершена" : publishStatusLabel[status];
  const statusDescription = simulationCompleted
    ? "Dry-run завершён; TrueNAS не изменялся."
    : job
      ? "Backend подтвердил текущее состояние job."
      : "Dispatch принят; ждём первый ответ read model.";
  const recoveryRequired = Boolean(job?.targets.some((target) => target.error_code === "recovery_required"));

  return (
    <section className="publish-wizard">
      <SectionHeading eyebrow="04 / JOB READ MODEL" title={terminal ? statusTitle : "Job выполняется"} description={terminal ? "Финальное состояние получено от backend read model." : "После accepted UI регулярно читает только собственный Controller API."} action={<button className="secondary-button" type="button" onClick={refresh} disabled={refreshing}><RefreshCw aria-hidden size={15} /> {refreshing ? "Обновляем…" : "Обновить"}</button>} />
      <div className={"job-status-panel job-status-" + status}><div className="job-status-icon">{terminal ? <Check aria-hidden size={24} /> : <RefreshCw aria-hidden size={24} className="spin-icon" />}</div><div><strong>{statusTitle}</strong><p>{statusDescription}</p></div><span className="job-status-percent">{progress}%</span></div>
      {readError && <p className="error-message">Read model: {readError}</p>}
      {recoveryRequired && <div className="recovery-banner"><CircleAlert aria-hidden size={19} /><span><strong>Требуется восстановление</strong><small>Один или несколько target получили recovery_required. Не повторяйте publish вслепую; сначала разберите error и mapping state на backend.</small></span></div>}
      <div className="progress-track"><span style={{ width: progress + "%" }} /></div>
      {job && <div className="target-progress-list">{job.targets.map((target) => <TargetProgress key={target.station_id} target={target} stationName={findStationName(stations, target.station_id)} />)}</div>}
      <InfoNote><LockKeyhole aria-hidden size={16} /> {simulationCompleted ? "Это только безопасная симуляция: storage switch не выполнялся." : "Accepted не означает completed. Только финальный status read model подтверждает результат worker."}</InfoNote>
      <div className="accepted-id"><span>Job ID</span><code>{accepted.job_id}</code></div>
      <div className="wizard-actions"><button className="secondary-button" type="button" onClick={onReset}><RefreshCw aria-hidden size={15} /> Создать ещё один draft</button></div>
    </section>
  );
}

function TargetProgress({ target, stationName }: { target: PublishTargetReadModel; stationName: string }) {
  const phase = target.verify_status ?? target.switch_status ?? target.preflight_status ?? "pending";
  const hasError = Boolean(target.error_code || target.error_message);
  return <article className={hasError ? "target-progress target-error" : "target-progress"}><div className="target-progress-heading"><div><strong>{stationName}</strong><small>{target.station_id}</small></div><span>{target.progress_percent}%</span></div><div className="target-progress-track"><span style={{ width: target.progress_percent + "%" }} /></div><div className="target-progress-meta"><span>Phase: {phase}</span>{target.error_code && <b>{target.error_code}</b>}</div>{target.error_message && <p>{target.error_message}</p>}</article>;
}

function overallProgress(targets: PublishTargetReadModel[]) {
  const selected = targets.filter((target) => target.selected);
  if (selected.length === 0) {
    return 0;
  }
  return Math.round(selected.reduce((sum, target) => sum + target.progress_percent, 0) / selected.length);
}

function WizardProgress({ current }: { current: WizardStep }) {
  const steps = [
    ["01", "Draft"],
    ["02", "Preflight"],
    ["03", "Confirm"],
    ["04", "Accepted"],
  ];
  return <div className="wizard-progress">{steps.map(([number, label], index) => <div className={current >= index + 1 ? "wizard-step active" : "wizard-step"} key={number}><span>{number}</span><small>{label}</small>{index < steps.length - 1 && <i />}</div>)}</div>;
}

function StationChoice({ station, selected, onToggle }: { station: Station; selected: boolean; onToggle: (stationId: string) => void }) {
  const disabled = !isStationSelectableForPublish(station);
  return <button className={selected ? "station-choice selected" : "station-choice"} type="button" disabled={disabled} onClick={() => onToggle(station.station_id)}><span className="choice-icon">{selected ? <Check aria-hidden size={15} /> : <Server aria-hidden size={15} />}</span><span className="choice-copy"><strong>{station.display_name}</strong><small>{station.hostname}</small></span><StatusBadge status={station.status} /></button>;
}

function ReportCard({ title, report, stationName }: { title: string; report: PreflightReport; stationName: string }) {
  return <article className={"report-card report-" + report.status}><div className="report-card-heading"><div><span className="eyebrow">{title}</span><h3>{stationName}</h3></div><span className={"report-status report-status-" + report.status}>{report.status.toUpperCase()}</span></div><p className="muted">Evaluated {formatDate(report.evaluated_at)}</p><div className="check-list">{report.checks.map((check) => <CheckRow check={check} key={check.code} />)}</div></article>;
}

function CheckRow({ check }: { check: PreflightCheck }) {
  const Icon = checkIcons[check.status];
  return <div className={"check-row check-" + check.status}><Icon aria-hidden size={16} /><span><strong>{check.code}</strong><small>{check.message}</small>{check.matched_processes.length > 0 && <span className="matched-processes"><b>Обнаружено:</b>{check.matched_processes.map((process) => <code key={`${process.name}-${process.pid ?? "unknown"}-${process.path ?? ""}`}>{process.name}{process.pid === null ? "" : ` · PID ${process.pid}`}{process.path ? ` · ${process.path}` : ""}</code>)}</span>}</span></div>;
}

function GateBanner({ gate }: { gate: PublishGate }) {
  return <div className={gate.can_advance ? "gate-banner ready" : "gate-banner blocked"}><div className="gate-icon">{gate.can_advance ? <CircleCheck aria-hidden size={20} /> : <CircleAlert aria-hidden size={20} />}</div><div><strong>{gate.can_advance ? "Server gate: READY" : "Server gate: BLOCKED"}</strong>{gate.reasons.length > 0 && <ul>{gate.reasons.map((reason) => <li key={reason}>{reasonLabels[reason] ?? (reason.startsWith("client_preflight_blocked:") ? "Одна из client stations заблокирована." : reason)}</li>)}</ul>}{gate.can_advance && <p>Все выбранные станции соответствуют текущей policy.</p>}</div></div>;
}

function canRequestConfirmation(gate: PublishGate) {
  return gate.can_advance || (
    gate.reasons.length === 1
    && gate.reasons[0] === "operator_confirmation_required"
  );
}

function findStationName(stations: Station[], stationId: string) {
  return stations.find((station) => station.station_id === stationId)?.display_name ?? stationId;
}

function formatDate(value: string) {
  return new Date(value).toLocaleString("ru-RU");
}

function formatOptionalDate(value: string | null) {
  return value ? formatDate(value) : "—";
}

function makeIdempotencyKey() {
  return "frontend-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
}

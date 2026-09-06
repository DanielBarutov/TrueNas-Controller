import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { CheckSquare, Database, RefreshCw, Trash2 } from "lucide-react";
import type { ControllerApi } from "../../application/api/client";
import type { Dataset } from "../../domain/dataset";
import { datasetStatusLabel } from "../../domain/dataset";
import type { Station } from "../../domain/station";
import { HelpHint, InfoNote, SectionHeading } from "../components/ui";

export function DatasetsPage({ api }: { api: ControllerApi }) {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [stations, setStations] = useState<Station[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const [datasetResponse, stationResponse] = await Promise.all([
        api.listDatasets(includeDeleted),
        api.listStations(),
      ]);
      setDatasets(datasetResponse);
      setStations(stationResponse);
      setSelectedIds([]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить датасеты.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(); }, [includeDeleted]);

  const stationNames = useMemo(
    () => new Map(stations.map((station) => [station.station_id, station.display_name])),
    [stations],
  );
  const selectableDatasets = datasets.filter(
    (dataset) => !dataset.is_current && dataset.status !== "deleted" && dataset.deleted_at === null,
  );
  const stationCount = new Set(datasets.map((dataset) => dataset.station_id)).size;
  const currentCount = datasets.filter((dataset) => dataset.is_current).length;

  function toggleDataset(datasetId: string) {
    setSelectedIds((current) => current.includes(datasetId)
      ? current.filter((id) => id !== datasetId)
      : [...current, datasetId]);
  }

  function toggleAll() {
    setSelectedIds((current) => current.length === selectableDatasets.length
      ? []
      : selectableDatasets.map((dataset) => dataset.id));
  }

  async function queueDeletion() {
    if (selectedIds.length === 0) return;
    if (!window.confirm(`Поставить в очередь удаление датасетов: ${selectedIds.length}?`)) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.deleteDatasets(selectedIds);
      setSelectedIds([]);
      setMessage(`В очередь worker передано датасетов: ${result.artifact_ids.length}. После выполнения обновите список.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось поставить удаление в очередь.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageSection>
      <SectionHeading
        eyebrow="STORAGE INVENTORY"
        title="Датасеты"
        description="История clone/dataset, созданных publish-задачами для игровых ПК."
        action={<button className="secondary-button" type="button" onClick={() => void load()} disabled={busy}><RefreshCw aria-hidden size={15} /> Обновить</button>}
      />
      {error && <p className="error-message">{error}</p>}
      {message && <p className="success-message">{message}</p>}
      <InfoNote><Database aria-hidden size={16} /> Удаление выполняет worker с TrueNAS-секретом. Датасет, который сейчас используется станцией, отмечен и не выбирается.</InfoNote>
      <section className="form-card dataset-card">
        <div className="dataset-toolbar">
          <label className="checkbox-row"><input type="checkbox" checked={includeDeleted} onChange={(event) => setIncludeDeleted(event.target.checked)} /> Показывать удалённые</label>
          <span className="muted">Записей истории: {datasets.length} · ПК: {stationCount} · активно: {currentCount} · к удалению: {selectableDatasets.length} · выбрано: {selectedIds.length}</span>
          <button className="danger-button" type="button" onClick={() => void queueDeletion()} disabled={busy || selectedIds.length === 0}><Trash2 aria-hidden size={15} /> Удалить выбранные</button>
        </div>
        <HelpHint>В списке отображаются только записи, которые контроллер знает по publish history. Если TrueNAS отклонит удаление, worker сохранит ошибку для повторной попытки.</HelpHint>
        <div className="table-card">
          <table>
            <thead><tr><th><input aria-label="Выбрать все доступные датасеты" type="checkbox" checked={selectableDatasets.length > 0 && selectedIds.length === selectableDatasets.length} onChange={toggleAll} /></th><th>Датасет</th><th>ПК</th><th>Статус</th><th>Создан</th><th>Описание</th></tr></thead>
            <tbody>{datasets.length === 0 ? <tr><td colSpan={6} className="empty-cell">Датасетов пока нет.</td></tr> : datasets.map((dataset) => {
              const selectable = !dataset.is_current && dataset.status !== "deleted" && dataset.deleted_at === null;
              return <tr key={dataset.id}>
                <td><input aria-label={`Выбрать ${dataset.dataset_name}`} type="checkbox" checked={selectedIds.includes(dataset.id)} disabled={!selectable || busy} onChange={() => toggleDataset(dataset.id)} /></td>
                <td><strong>{dataset.dataset_name}</strong><span className="table-subtitle">{dataset.source_dataset}</span></td>
                <td>{stationNames.get(dataset.station_id) ?? dataset.station_id}<span className="table-subtitle">{dataset.station_id}</span></td>
                <td><span className={`dataset-status dataset-status-${dataset.status}`}>{datasetStatusLabel[dataset.status]}</span></td>
                <td>{new Date(dataset.created_at).toLocaleString()}</td>
                <td>{dataset.last_error ?? (dataset.is_current ? "Используется текущим mapping станции." : "Можно поставить удаление в очередь.")}</td>
              </tr>;
            })}</tbody>
          </table>
        </div>
      </section>
    </PageSection>
  );
}

function PageSection({ children }: { children: ReactNode }) {
  return <div className="page"><header className="page-header"><p className="eyebrow">OPERATOR CONSOLE</p><h1>Управление датасетами</h1><p className="muted">Выберите завершившие работу версии и передайте их в worker cleanup.</p></header>{children}</div>;
}

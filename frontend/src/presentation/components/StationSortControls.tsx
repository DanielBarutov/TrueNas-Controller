import { ArrowDownAZ, ArrowDownUp, ArrowUpAZ } from "lucide-react";
import {
  stationSortFieldLabel,
  type SortDirection,
  type StationSortField,
} from "../../domain/station";

const sortFields: StationSortField[] = ["display_name", "hostname", "role", "status"];

export function StationSortControls({
  field,
  direction,
  onFieldChange,
  onDirectionChange,
}: {
  field: StationSortField;
  direction: SortDirection;
  onFieldChange: (value: StationSortField) => void;
  onDirectionChange: (value: SortDirection) => void;
}) {
  const DirectionIcon = direction === "asc" ? ArrowDownAZ : ArrowUpAZ;
  const directionLabel = direction === "asc" ? "По возрастанию" : "По убыванию";

  return (
    <div className="station-sort-controls">
      <label className="sort-field">
        <span><ArrowDownUp aria-hidden size={13} /> Сортировка</span>
        <select value={field} onChange={(event) => onFieldChange(event.target.value as StationSortField)}>
          {sortFields.map((sortField) => <option key={sortField} value={sortField}>{stationSortFieldLabel[sortField]}</option>)}
        </select>
      </label>
      <button
        className="sort-direction-button"
        type="button"
        title={directionLabel}
        aria-label={directionLabel}
        onClick={() => onDirectionChange(direction === "asc" ? "desc" : "asc")}
      >
        <DirectionIcon aria-hidden size={15} />
        <span>{direction === "asc" ? "А—Я" : "Я—А"}</span>
      </button>
    </div>
  );
}

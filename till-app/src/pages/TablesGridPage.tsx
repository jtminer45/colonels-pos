import AppHeader, { type AppMode } from "../components/AppHeader";
import TableTile from "../components/TableTile";
import { useTables } from "../hooks/useTables";

interface Props {
  mode: AppMode;
  onModeChange: (mode: AppMode) => void;
  onSelectTable: (tableId: number) => void;
}

export default function TablesGridPage({ mode, onModeChange, onSelectTable }: Props) {
  const { tables, loading, error, refetch } = useTables();

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden">
      <AppHeader mode={mode} onModeChange={onModeChange} />

      {error && (
        <div className="bg-brand-red/15 text-brand-red text-sm px-4 py-2 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={refetch} className="tap-target underline">
            Retry
          </button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <p className="text-white/40 text-center mt-10">Loading tables…</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 max-w-4xl mx-auto">
            {tables.map((t) => (
              <TableTile key={t.id} table={t} onSelect={() => onSelectTable(t.id)} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

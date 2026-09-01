import React from 'react';
import { Trash2 } from 'lucide-react';
import type { HistoryItem as HistoryItemType } from '../../types';
import { HistoryItem } from './HistoryItem';

interface HistoryListProps {
  items?: HistoryItemType[];
  onRestore: (item: HistoryItemType) => void;
  onDelete: (id: string) => void;
  onClearAll: () => void;
}

export const HistoryList: React.FC<HistoryListProps> = ({
  items = [],
  onRestore,
  onDelete,
  onClearAll,
}) => {
  if (!items || items.length === 0) {
    return null;
  }

  return (
    <section
      aria-label="Lịch sử chuẩn hóa gần đây"
      className="flex flex-col gap-2.5"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted">
          Lịch sử gần đây
        </span>
        <button
          type="button"
          onClick={onClearAll}
          className="inline-flex items-center gap-1 text-xs text-muted transition-colors hover:text-error focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-error"
        >
          <Trash2 className="size-3" aria-hidden="true" />
          <span>Xóa lịch sử</span>
        </button>
      </div>

      <div className="space-y-2">
        {items.map((item) => (
          <HistoryItem
            key={item.id}
            item={item}
            onRestore={onRestore}
            onDelete={onDelete}
          />
        ))}
      </div>
    </section>
  );
};

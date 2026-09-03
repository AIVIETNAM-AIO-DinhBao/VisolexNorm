import React, { useState } from 'react';
import { Copy, Check, RotateCcw, Trash2 } from 'lucide-react';
import type { HistoryItem as HistoryItemType } from '../../types';

interface HistoryItemProps {
  item: HistoryItemType;
  onRestore: (item: HistoryItemType) => void;
  onDelete: (id: string) => void;
}

export const HistoryItem: React.FC<HistoryItemProps> = ({
  item,
  onRestore,
  onDelete,
}) => {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = async () => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(item.output);
        setIsCopied(true);
        setTimeout(() => {
          setIsCopied(false);
        }, 1800);
      }
    } catch {
      // Fail gracefully
    }
  };

  const formattedTime = (() => {
    try {
      const date = new Date(item.createdAt);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  })();

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-hairline bg-white p-3.5 transition-colors sm:flex-row sm:items-center sm:justify-between sm:p-4">
      {/* Text preview */}
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-medium text-muted">Gốc:</span>
          <p className="line-clamp-1 font-mono text-xs text-body break-words">
            {item.input}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted">Chuẩn hóa:</span>
          <p className="line-clamp-1 text-sm font-medium text-ink break-words">
            {item.output}
          </p>
        </div>
      </div>

      {/* Actions & timestamp */}
      <div className="flex shrink-0 items-center justify-between gap-3 border-t border-hairline/40 pt-2 sm:border-t-0 sm:pt-0">
        {formattedTime && (
          <span className="text-xs text-muted-soft select-none sm:hidden">
            {formattedTime}
          </span>
        )}

        <div className="flex items-center gap-1.5 sm:ml-auto">
          {formattedTime && (
            <span className="mr-1 hidden text-xs text-muted-soft select-none sm:inline">
              {formattedTime}
            </span>
          )}

          <button
            type="button"
            onClick={() => onRestore(item)}
            className="inline-flex items-center gap-1 rounded-sm px-2 py-1 text-xs text-body transition-colors hover:bg-surface-soft hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            title="Khôi phục lại kết quả này"
          >
            <RotateCcw className="size-3" aria-hidden="true" />
            <span>Khôi phục</span>
          </button>

          <button
            type="button"
            onClick={handleCopy}
            className="inline-flex items-center gap-1 rounded-sm px-2 py-1 text-xs text-body transition-colors hover:bg-surface-soft hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            title="Sao chép kết quả chuẩn hóa"
          >
            {isCopied ? (
              <>
                <Check className="size-3 text-success" aria-hidden="true" />
                <span className="text-success">Đã sao chép</span>
              </>
            ) : (
              <>
                <Copy className="size-3" aria-hidden="true" />
                <span>Sao chép</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => onDelete(item.id)}
            className="inline-flex items-center justify-center rounded-sm p-1 text-muted transition-colors hover:bg-surface-soft hover:text-error focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-error"
            aria-label="Xóa mục lịch sử này"
            title="Xóa mục này"
          >
            <Trash2 className="size-3.5" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
  );
};

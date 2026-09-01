import React, { useState } from 'react';
import { Copy, Check, RotateCcw } from 'lucide-react';

interface OutputPanelProps {
  value: string;
  placeholder?: string;
  onEditAgain?: () => void;
  isLoading?: boolean;
  disabled?: boolean;
}

export const OutputPanel: React.FC<OutputPanelProps> = ({
  value,
  placeholder = 'Kết quả chuẩn hóa sẽ xuất hiện ở đây.',
  onEditAgain,
  isLoading = false,
  disabled = false,
}) => {
  const [isCopied, setIsCopied] = useState(false);
  const hasValue = Boolean(value && value.trim().length > 0);

  const handleCopy = async () => {
    if (!hasValue || disabled || isLoading) return;

    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
        setIsCopied(true);
        setTimeout(() => {
          setIsCopied(false);
        }, 1800);
      }
    } catch {
      // Fail gracefully without crashing UI
    }
  };

  return (
    <div className="flex flex-1 flex-col justify-between bg-surface-soft/30 p-4 sm:p-5">
      <div className="flex flex-col">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted">
          Văn bản chuẩn hóa
        </span>
        <div className="mt-2 min-h-[144px] w-full text-base leading-relaxed">
          {isLoading ? (
            <p className="select-none text-muted-soft">Đang chuẩn hóa văn bản...</p>
          ) : hasValue ? (
            <p className="whitespace-pre-wrap text-ink">{value}</p>
          ) : (
            <p className="select-none text-muted-soft">{placeholder}</p>
          )}
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-hairline/60 pt-3 text-xs text-muted">
        <div>
          {!isLoading && hasValue && onEditAgain && (
            <button
              type="button"
              onClick={onEditAgain}
              disabled={disabled}
              className="inline-flex items-center gap-1 rounded-sm px-1.5 py-1 text-muted transition-colors hover:text-ink disabled:opacity-40 disabled:hover:text-muted"
            >
              <RotateCcw className="size-3.5" aria-hidden="true" />
              <span>Chỉnh sửa lại</span>
            </button>
          )}
        </div>

        <button
          type="button"
          onClick={handleCopy}
          disabled={disabled || isLoading || !hasValue}
          className="inline-flex items-center gap-1.5 rounded-sm px-1.5 py-1 font-medium transition-colors hover:text-ink disabled:opacity-40 disabled:hover:text-muted"
          aria-label="Sao chép kết quả chuẩn hóa"
        >
          {isCopied ? (
            <>
              <Check className="size-3.5 text-success" aria-hidden="true" />
              <span className="text-success">Đã sao chép</span>
            </>
          ) : (
            <>
              <Copy className="size-3.5" aria-hidden="true" />
              <span>Sao chép</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};

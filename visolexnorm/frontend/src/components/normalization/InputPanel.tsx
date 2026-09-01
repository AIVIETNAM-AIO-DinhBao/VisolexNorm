import React from 'react';
import { Trash2 } from 'lucide-react';

interface InputPanelProps {
  value: string;
  onChange: (value: string) => void;
  onClear: () => void;
  onSubmit?: () => void;
  maxLength?: number;
  disabled?: boolean;
  inputRef?: React.RefObject<HTMLTextAreaElement | null>;
}

export const InputPanel: React.FC<InputPanelProps> = ({
  value,
  onChange,
  onClear,
  onSubmit,
  maxLength = 500,
  disabled = false,
  inputRef,
}) => {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      onSubmit?.();
    }
  };

  return (
    <div className="flex flex-1 flex-col justify-between p-4 sm:p-5">
      <div className="flex flex-col">
        <label
          htmlFor="normalization-input"
          className="text-xs font-semibold uppercase tracking-wider text-muted"
        >
          Văn bản gốc
        </label>
        <textarea
          ref={inputRef}
          id="normalization-input"
          name="normalization-input"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Nhập văn bản cần chuẩn hóa..."
          disabled={disabled}
          maxLength={maxLength}
          rows={6}
          className="mt-2 w-full resize-none border-none bg-transparent p-0 text-base leading-relaxed text-ink placeholder:text-muted-soft focus:outline-none"
        />
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-hairline/60 pt-3 text-xs text-muted">
        <span>
          {value.length} / {maxLength}
        </span>
        <button
          type="button"
          onClick={onClear}
          disabled={disabled || value.length === 0}
          className="inline-flex items-center gap-1 rounded-sm px-1.5 py-1 text-muted transition-colors hover:text-ink disabled:opacity-40 disabled:hover:text-muted"
          aria-label="Xóa nội dung nhập"
        >
          <Trash2 className="size-3.5" aria-hidden="true" />
          <span>Xóa</span>
        </button>
      </div>
    </div>
  );
};

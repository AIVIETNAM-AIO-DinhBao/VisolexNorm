import React from 'react';
import { EXAMPLE_INPUTS } from '../../constants/examples';

interface ExampleInputsProps {
  onSelectExample?: (example: string) => void;
  disabled?: boolean;
}

export const ExampleInputs: React.FC<ExampleInputsProps> = ({
  onSelectExample,
  disabled = false,
}) => {
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-xs font-semibold uppercase tracking-wider text-muted">
        Thử với ví dụ
      </span>
      <div className="flex flex-wrap gap-2">
        {EXAMPLE_INPUTS.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => onSelectExample?.(example)}
            disabled={disabled}
            className="rounded-md border border-hairline bg-surface-card px-3 py-1.5 font-mono text-xs text-body transition-colors hover:border-hairline hover:bg-surface-cream-strong active:bg-surface-cream-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:opacity-50 sm:text-sm"
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
};

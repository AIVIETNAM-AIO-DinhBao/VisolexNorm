import React from 'react';
import { InputPanel } from './InputPanel';
import { OutputPanel } from './OutputPanel';

interface NormalizationWorkspaceProps {
  inputValue: string;
  outputValue: string;
  onInputChange: (value: string) => void;
  onInputClear: () => void;
  onSubmit?: () => void;
  onEditAgain?: () => void;
  isLoading?: boolean;
  inputRef?: React.RefObject<HTMLTextAreaElement | null>;
}

export const NormalizationWorkspace: React.FC<NormalizationWorkspaceProps> = ({
  inputValue,
  outputValue,
  onInputChange,
  onInputClear,
  onSubmit,
  onEditAgain,
  isLoading = false,
  inputRef,
}) => {
  return (
    <section
      aria-label="Khu vực chuẩn hóa văn bản"
      className="w-full overflow-hidden rounded-lg border border-hairline bg-white shadow-xs"
    >
      <div className="flex flex-col md:grid md:grid-cols-2">
        <InputPanel
          value={inputValue}
          onChange={onInputChange}
          onClear={onInputClear}
          onSubmit={onSubmit}
          disabled={isLoading}
          inputRef={inputRef}
        />
        <div className="border-t border-hairline md:border-t-0 md:border-l">
          <OutputPanel
            value={outputValue}
            onEditAgain={onEditAgain}
            isLoading={isLoading}
            disabled={isLoading}
          />
        </div>
      </div>
    </section>
  );
};

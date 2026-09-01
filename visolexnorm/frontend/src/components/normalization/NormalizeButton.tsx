import React from 'react';
import { Sparkles, LoaderCircle } from 'lucide-react';

interface NormalizeButtonProps {
  onClick?: () => void;
  disabled?: boolean;
  isLoading?: boolean;
}

export const NormalizeButton: React.FC<NormalizeButtonProps> = ({
  onClick,
  disabled = false,
  isLoading = false,
}) => {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || isLoading}
      className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-primary px-6 text-sm font-medium text-on-primary transition-colors hover:bg-primary-active active:bg-primary-active focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:bg-primary-disabled disabled:text-muted"
      aria-busy={isLoading}
    >
      {isLoading ? (
        <>
          <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
          <span>Đang chuẩn hóa...</span>
        </>
      ) : (
        <>
          <Sparkles className="size-4" aria-hidden="true" />
          <span>Chuẩn hóa</span>
        </>
      )}
    </button>
  );
};

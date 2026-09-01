import React from 'react';
import { AlertCircle, RotateCcw } from 'lucide-react';

interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({ message, onRetry }) => {
  return (
    <div
      role="alert"
      className="flex items-center justify-between rounded-md border border-error/20 bg-error/5 px-4 py-3 text-sm text-error"
    >
      <div className="flex items-center gap-2">
        <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
        <span>{message}</span>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1 font-medium underline underline-offset-2 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-error"
        >
          <RotateCcw className="size-3.5" aria-hidden="true" />
          <span>Thử lại</span>
        </button>
      )}
    </div>
  );
};

import React, { useState, useRef } from 'react';
import { NormalizationWorkspace } from '../components/normalization/NormalizationWorkspace';
import { NormalizeButton } from '../components/normalization/NormalizeButton';
import { ExampleInputs } from '../components/normalization/ExampleInputs';
import { DifferenceBox } from '../components/normalization/DifferenceBox';
import { HistoryList } from '../components/history/HistoryList';
import { ErrorMessage } from '../components/common/ErrorMessage';
import { normalizeText } from '../services/normalizeApi';
import { useNormalizationHistory } from '../hooks/useNormalizationHistory';
import type { HistoryItem } from '../types';

export const HomePage: React.FC = () => {
  const [inputText, setInputText] = useState('');
  const [outputText, setOutputText] = useState('');
  const [lastNormalizedInput, setLastNormalizedInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { history, addHistoryItem, removeHistoryItem, clearHistory } = useNormalizationHistory();

  const isValid = inputText.trim().length > 0;

  const handleInputChange = (value: string) => {
    setInputText(value);
    if (error) setError(null);
  };

  const handleInputClear = () => {
    setInputText('');
    if (error) setError(null);
    inputRef.current?.focus();
  };

  const handleSelectExample = (example: string) => {
    setInputText(example);
    if (error) setError(null);
    inputRef.current?.focus();
  };

  const handleEditAgain = () => {
    if (!outputText) return;
    setInputText(outputText);
    if (error) setError(null);
    inputRef.current?.focus();
  };

  const handleRestoreHistory = (item: HistoryItem) => {
    setInputText(item.input);
    setLastNormalizedInput(item.input);
    setOutputText(item.output);
    if (error) setError(null);
    inputRef.current?.focus();
  };

  const handleNormalize = async () => {
    const trimmed = inputText.trim();
    if (!trimmed || isLoading) return;

    // Snapshot exact submitted input to prevent async race conditions
    const submittedSource = inputText;
    setIsLoading(true);
    setError(null);

    try {
      const result = await normalizeText(submittedSource);
      setLastNormalizedInput(submittedSource);
      setOutputText(result);
      addHistoryItem(submittedSource, result);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Không thể chuẩn hóa văn bản. Vui lòng thử lại.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-8 px-4 py-8 sm:px-6 sm:py-12">
      {/* 1. Intro Section */}
      <section className="text-center">
        <h1 className="font-serif text-3xl font-normal tracking-tight text-ink sm:text-4xl">
          Chuẩn hóa văn bản tiếng Việt
        </h1>
        <p className="mt-2.5 text-sm leading-relaxed text-muted sm:text-base">
          Chuyển teen code và văn bản không chuẩn thành tiếng Việt tự nhiên, đúng chuẩn.
        </p>
      </section>

      {/* 2. Normalization Workspace */}
      <div className="flex flex-col gap-4">
        <NormalizationWorkspace
          inputValue={inputText}
          outputValue={outputText}
          onInputChange={handleInputChange}
          onInputClear={handleInputClear}
          onSubmit={handleNormalize}
          onEditAgain={handleEditAgain}
          isLoading={isLoading}
          inputRef={inputRef}
        />

        {error && (
          <ErrorMessage message={error} onRetry={handleNormalize} />
        )}
      </div>

      {/* 3. Normalize Action Button */}
      <div className="flex justify-center">
        <NormalizeButton
          onClick={handleNormalize}
          disabled={!isValid || isLoading}
          isLoading={isLoading}
        />
      </div>

      {/* 4. Example Inputs */}
      <ExampleInputs
        onSelectExample={handleSelectExample}
        disabled={isLoading}
      />

      {/* 5. Difference Section Area */}
      <DifferenceBox
        originalText={lastNormalizedInput}
        normalizedText={outputText}
        visible={Boolean(lastNormalizedInput && outputText && outputText.trim().length > 0)}
      />

      {/* 6. Recent History Section Area */}
      <HistoryList
        items={history}
        onRestore={handleRestoreHistory}
        onDelete={removeHistoryItem}
        onClearAll={clearHistory}
      />
    </main>
  );
};

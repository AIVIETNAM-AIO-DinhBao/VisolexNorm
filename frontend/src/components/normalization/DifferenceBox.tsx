import React, { useMemo } from 'react';
import { computeTextDiff, type DiffSegment } from '../../utils/textDiff';

interface DifferenceBoxProps {
  originalText?: string;
  normalizedText?: string;
  visible?: boolean;
}

// Subtle, warm highlight styles matching DESIGN.md color palette
const HIGHLIGHT_STYLES = [
  'bg-[#f4dfd6] text-[#6e2b17] border-b-2 border-[#cc785c] rounded-xs px-0.5', // Warm Coral
  'bg-[#f5ebd7] text-[#5c4314] border-b-2 border-[#d99748] rounded-xs px-0.5', // Warm Amber/Sand
  'bg-[#dcefe9] text-[#1c4d43] border-b-2 border-[#5db8a6] rounded-xs px-0.5', // Muted Sage/Teal
  'bg-[#e3e8f4] text-[#243356] border-b-2 border-[#829cd0] rounded-xs px-0.5', // Soft Slate/Indigo
];

function getHighlightClass(segment: DiffSegment): string {
  if (segment.type === 'equal' || !segment.groupId) {
    return '';
  }

  const baseStyle = HIGHLIGHT_STYLES[(segment.groupId - 1) % HIGHLIGHT_STYLES.length];

  if (segment.type === 'deleted') {
    return `${baseStyle} line-through decoration-[#6e2b17]/60`;
  }

  return baseStyle;
}

export const DifferenceBox: React.FC<DifferenceBoxProps> = ({
  originalText = '',
  normalizedText = '',
  visible = true,
}) => {
  const diff = useMemo(() => {
    if (!originalText || !normalizedText) {
      return null;
    }
    return computeTextDiff(originalText, normalizedText);
  }, [originalText, normalizedText]);

  if (!visible || !originalText || !normalizedText || !diff) {
    return null;
  }

  return (
    <section
      aria-label="So sánh thay đổi"
      className="flex flex-col gap-2.5"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted">
          So sánh thay đổi
        </span>
        {!diff.hasChanges && (
          <span className="text-xs text-muted">Văn bản không có thay đổi</span>
        )}
      </div>

      <div className="rounded-lg border border-hairline bg-surface-card p-4 sm:p-5 text-sm leading-relaxed shadow-xs">
        <div className="space-y-3">
          {/* Row 1: Original text */}
          <div className="flex flex-col sm:flex-row sm:gap-3">
            <span className="w-24 shrink-0 font-medium text-muted">Gốc:</span>
            <div className="min-w-0 flex-1 whitespace-pre-wrap break-words font-mono text-ink">
              {diff.originalSegments.map((segment, index) => (
                <span
                  key={`orig-${index}-${segment.groupId ?? 'eq'}`}
                  className={getHighlightClass(segment)}
                >
                  {segment.text}
                </span>
              ))}
            </div>
          </div>

          <div className="border-t border-hairline/60 pt-3 flex flex-col sm:flex-row sm:gap-3">
            {/* Row 2: Normalized text */}
            <span className="w-24 shrink-0 font-medium text-muted">Chuẩn hóa:</span>
            <div className="min-w-0 flex-1 whitespace-pre-wrap break-words font-mono text-ink">
              {diff.normalizedSegments.map((segment, index) => (
                <span
                  key={`norm-${index}-${segment.groupId ?? 'eq'}`}
                  className={getHighlightClass(segment)}
                >
                  {segment.text}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

import { useCallback, useState, type RefObject } from 'react';
import { detectContentType } from '../utils/contentDetector';
import type { ContentType } from '../types';

/**
 * Hook for smart paste detection (Mogan-inspired Magic Paste).
 */
export function useMagicPaste() {
  const [detectedType, setDetectedType] = useState<ContentType>('plain');

  const handlePaste = useCallback(
    (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
      const pastedText = e.clipboardData.getData('text');
      if (!pastedText) return;

      const detection = detectContentType(pastedText);
      setDetectedType(detection.type);

      // Let the default paste behavior happen
      // The detection result can be used by the component to show a badge
    },
    []
  );

  return { handlePaste, detectedType };
}
import type { ContentType, ContentDetectionResult, LatexRegion } from '../types';

/**
 * Detect the content type of a text string.
 * Inspired by MoganLab/mogan's paste-widget.scm format detection.
 */
export function detectContentType(text: string): ContentDetectionResult {
  if (!text || !text.trim()) {
    return { type: 'plain', confidence: 1.0, latexRegions: [] };
  }

  const latexRegions = detectLatexDelimiters(text);
  const hasLatex = latexRegions.length > 0;
  const hasMarkdown = detectMarkdown(text);
  const hasHtml = detectHtml(text);
  const hasCode = detectCode(text);

  // Mixed: multiple content types detected
  const types = [hasLatex, hasMarkdown, hasHtml, hasCode].filter(Boolean);
  if (types.length >= 2) {
    return { type: 'mixed', confidence: 0.8, latexRegions };
  }

  if (hasLatex) return { type: 'latex', confidence: 0.9, latexRegions };
  if (hasHtml) return { type: 'html', confidence: 0.8, latexRegions };
  if (hasCode) return { type: 'code', confidence: 0.8, latexRegions };
  if (hasMarkdown) return { type: 'markdown', confidence: 0.7, latexRegions };

  return { type: 'plain', confidence: 0.9, latexRegions };
}

/**
 * Detect LaTeX delimiters in text.
 */
export function detectLatexDelimiters(text: string): LatexRegion[] {
  const regions: LatexRegion[] = [];

  // Display math: $$ ... $$ or \[ ... \]
  const displayPatterns = [
    /\$\$([\s\S]*?)\$\$/g,
    /\\\[([\s\S]*?)\\\]/g,
  ];

  for (const pattern of displayPatterns) {
    let match;
    while ((match = pattern.exec(text)) !== null) {
      regions.push({
        start: match.index,
        end: match.index + match[0].length,
        content: match[1].trim(),
        displayMode: true,
      });
    }
  }

  // Inline math: $ ... $ or \( ... \)
  const inlinePatterns = [
    /(?<!\$)\$(?!\$)(.*?)\$(?!\$)/g,
    /\\\((.*?)\\\)/g,
  ];

  for (const pattern of inlinePatterns) {
    let match;
    while ((match = pattern.exec(text)) !== null) {
      // Skip if inside a display math region
      const isInsideDisplay = regions.some(
        (r) => match!.index >= r.start && match!.index < r.end
      );
      if (!isInsideDisplay) {
        regions.push({
          start: match.index,
          end: match.index + match[0].length,
          content: match[1].trim(),
          displayMode: false,
        });
      }
    }
  }

  return regions.sort((a, b) => a.start - b.start);
}

function detectMarkdown(text: string): boolean {
  const mdPatterns = [
    /^#{1,6}\s+/m,     // Headers
    /\*\*.*?\*\*/,       // Bold
    /\*[^*]+\*/,         // Italic
    /^\s*[-*+]\s+/m,    // Unordered list
    /^\s*\d+\.\s+/m,    // Ordered list
    /```[\s\S]*?```/,   // Code block
    /\[.*?\]\(.*?\)/,   // Link
    /^\s*>\s+/m,        // Blockquote
  ];
  return mdPatterns.filter((p) => p.test(text)).length >= 2;
}

function detectHtml(text: string): boolean {
  return /<\/?[a-z][\s\S]*>/i.test(text);
}

function detectCode(text: string): boolean {
  const codePatterns = [
    /^(import|from|def|class|function|const|let|var|if|for|while)\s/m,
    /[{}\[\]];?\s*$/m,
    /=>|->|::/,
  ];
  return codePatterns.filter((p) => p.test(text)).length >= 2;
}
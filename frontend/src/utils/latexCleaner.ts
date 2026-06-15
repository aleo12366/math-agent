/**
 * LaTeX sanitization for KaTeX compatibility.
 * Cleans and normalizes LaTeX expressions from LLM output.
 */

/**
 * Clean LaTeX text for KaTeX rendering.
 */
export function cleanLatex(text: string): string {
  if (!text) return '';
  let result = text;
  result = normalizeDelimiters(result);
  result = fixCommonErrors(result);
  result = removeUnsupportedCommands(result);
  return result;
}

/**
 * Normalize delimiters: \[ \] → $$, \( \) → $
 */
export function normalizeDelimiters(text: string | undefined): string {
  if (!text) return '';
  let result = text;
  // \[ ... \] → $$ ... $$
  result = result.replace(/\\\[/g, '$$');
  result = result.replace(/\\\]/g, '$$');
  // \( ... \) → $ ... $
  result = result.replace(/\\\(/g, '$');
  result = result.replace(/\\\)/g, '$');
  return result;
}

/**
 * Fix common LaTeX errors from LLM output.
 */
export function fixCommonErrors(text: string): string {
  let result = text;
  // Fix double-escaped backslashes (common LLM issue)
  result = result.replace(/\\\\(frac|sqrt|sum|int|prod|lim|sin|cos|tan|log|ln|exp|det|vec|hat|bar|dot|ddot|alpha|beta|gamma|delta|epsilon|theta|lambda|mu|sigma|omega|pi|phi|psi|rho|tau|xi|zeta|eta|kappa|nu|varphi|varepsilon)/g, '\\$1');
  // Fix \text{ } → \text{ } (no-op but removes extra spaces)
  // Fix \left( \right) spacing
  result = result.replace(/\\left\s*\(/g, '\\left(');
  result = result.replace(/\\right\s*\)/g, '\\right)');
  result = result.replace(/\\left\s*\[/g, '\\left[');
  result = result.replace(/\\right\s*\]/g, '\\right]');
  // Fix \begin{aligned} to \begin{aligned} (ensure proper environment)
  result = result.replace(/\\begin\{align\*\}/g, '\\begin{aligned}');
  result = result.replace(/\\end\{align\*\}/g, '\\end{aligned}');
  // Remove \displaystyle (KaTeX handles this)
  // Actually keep it, KaTeX supports it
  return result;
}

/**
 * Remove LaTeX commands not supported by KaTeX.
 */
export function removeUnsupportedCommands(text: string): string {
  let result = text;
  // \boxed is supported by KaTeX natively — no replacement needed
  return result;
}

/**
 * Wrap bare LaTeX expressions in delimiters if needed.
 */
export function ensureDelimiters(text: string): string {
  // If text contains LaTeX commands but no delimiters
  if (/[\\][a-zA-Z]+/.test(text) && !text.includes('$')) {
    return `$${text}$`;
  }
  return text;
}
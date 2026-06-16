"""Normalizer + Constraint Graph — zero-LLM local preprocessing for math problems."""

from __future__ import annotations

import re
from typing import Any


# ── Unicode / text cleaning ─────────────────────────────────────────

_FULLWIDTH_MAP = {
    chr(0xFF10 + i): str(i) for i in range(10)  # ０-９ → 0-9
}
_FULLWIDTH_MAP.update({
    chr(0xFF01 + i): chr(0x21 + i) for i in range(94)  # ！-～ → !-~
})

_PROOF_KEYWORDS_ZH = {"证明", "求证", "验证", "论证"}
_PROOF_KEYWORDS_EN = {"prove", "show that", "demonstrate", "verify that"}


def clean_unicode(text: str) -> str:
    text = text.replace("\u00a0", " ")  # nbsp → space
    text = text.replace("\u200b", "")   # zero-width space
    out = []
    for ch in text:
        out.append(_FULLWIDTH_MAP.get(ch, ch))
    return "".join(out)


# ── LaTeX extraction ────────────────────────────────────────────────

_LATEX_PATTERNS = [
    re.compile(r"\$\$(.+?)\$\$", re.DOTALL),
    re.compile(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)"),
    re.compile(r"\\begin\{(\w+)\}(.+?)\\end\{\1\}", re.DOTALL),
    re.compile(r"\\\((.+?)\\\)"),
    re.compile(r"\\\[(.+?)\\\]"),
]


def extract_latex(text: str) -> list[str]:
    blocks: list[str] = []
    for pat in _LATEX_PATTERNS:
        for m in pat.finditer(text):
            body = m.group(m.lastindex) if m.lastindex else m.group(0)
            blocks.append(body.strip())
    return blocks


# ── Symbol extraction ───────────────────────────────────────────────

_SYMBOL_RE = re.compile(
    r"[a-zA-Z](?:_\w+)?(?:\{[^}]+\})?"   # variable names, possibly subscripted
    r"|\\[a-zA-Z]+"                         # LaTeX commands
    r"|α|β|γ|δ|ε|ζ|η|θ|ι|κ|λ|μ|ν|ξ|π|ρ|σ|τ|υ|φ|χ|ψ|ω"
    r"|∂|∇|∑|∏|∫"
)


def extract_symbols(text: str, latex_blocks: list[str]) -> list[str]:
    combined = text + " " + " ".join(latex_blocks)
    return sorted(set(_SYMBOL_RE.findall(combined)))


# ── Keyword extraction ──────────────────────────────────────────────

_KEYWORD_PATTERNS = [
    "微分方程", "偏微分方程", "常微分方程", "积分", "求导", "极限",
    "级数", "矩阵", "行列式", "特征值", "特征向量", "概率",
    "期望", "方差", "分布", "不等式", "方程", "方程组",
    "微分", "偏导", "梯度", "散度", "旋度",
    "求解", "计算", "证明", "讨论", "判断",
    "differential", "integral", "derivative", "limit",
    "matrix", "determinant", "eigenvalue", "probability",
    "inequality", "equation", "solve", "compute", "prove",
]


def extract_keywords(text: str) -> list[str]:
    lower = text.lower()
    return [kw for kw in _KEYWORD_PATTERNS if kw in lower or kw in text]


# ── Answer type prediction ──────────────────────────────────────────

def detect_proof_intent(text: str) -> bool:
    lower = text.lower()
    for kw in _PROOF_KEYWORDS_ZH:
        if kw in text:
            return True
    for kw in _PROOF_KEYWORDS_EN:
        if kw in lower:
            return True
    return False


def predict_answer_type(text: str, is_proof: bool) -> str:
    if is_proof:
        return "proof"
    lower = text.lower()
    if any(kw in text for kw in ("计算", "compute", "calculate")):
        return "computation"
    if any(kw in text for kw in ("求解", "solve")):
        return "expression"
    if any(kw in text for kw in ("判断", "是否", "whether")):
        return "judgment"
    if any(kw in text for kw in ("讨论", "discuss", "参数")):
        return "parametric"
    return "expression"


# ── normalize_problem ───────────────────────────────────────────────

def normalize_problem(raw: str) -> dict[str, Any]:
    clean = clean_unicode(raw)
    latex_blocks = extract_latex(clean)
    symbols = extract_symbols(clean, latex_blocks)
    keywords = extract_keywords(clean)
    is_proof = detect_proof_intent(clean)
    answer_type = predict_answer_type(clean, is_proof)
    return {
        "clean_text": clean,
        "latex_blocks": latex_blocks,
        "symbols": symbols,
        "keywords": keywords,
        "answer_type": answer_type,
        "is_proof": is_proof,
    }


# ── Constraint graph helpers ────────────────────────────────────────

_SINGLE_LETTER_VAR_RE = re.compile(r"(?<![a-zA-Z])([a-zA-Z])(?![a-zA-Z_\{])")
_KNOWN_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_EQUALITY_RE = re.compile(r"[^=!<>]=[^=]")
_INEQUALITY_RE = re.compile(r"[<>≤≥]|\\leq|\\geq|\\lt|\\gt")
_BOUNDARY_RE = re.compile(
    r"[yYuU]\s*\(\s*[^)]+\s*\)\s*="
)
_INITIAL_RE = re.compile(
    r"[yY]\s*\(\s*0\s*\)\s*="
    r"|[yY]'\s*\(\s*0\s*\)\s*="
    r"|[uU]\s*\(\s*0[^)]*\)\s*="
)
_DOMAIN_RE = re.compile(
    r"(?:区间|在|on)\s*[\[（(]\s*([^\]）)]+)\s*[\]）)]"
    r"|x\s*∈\s*([^\s,]+)"
)
_PDE_SYMBOLS = {"∂", "\\partial", "偏微分", "PDE", "pde"}
_CASE_SPLIT_KW = {"讨论", "参数", "parameter", "parametric", "cases", "分情况"}
_TOOL_KW = {"数值", "近似", "numerical", "approximate", "数值积分", "数值解"}


def extract_variables(text: str, latex_blocks: list[str]) -> list[str]:
    combined = text + " " + " ".join(latex_blocks)
    raw = _SINGLE_LETTER_VAR_RE.findall(combined)
    return sorted(set(raw))


def extract_unknowns(text: str, variables: list[str]) -> list[str]:
    return [v for v in variables if re.search(rf"\b{v}\b", text)]


def extract_knowns(text: str) -> list[str]:
    return _KNOWN_NUMBER_RE.findall(text)


def extract_domain(text: str) -> list[str]:
    return [m.group(0) for m in _DOMAIN_RE.finditer(text)]


def extract_equalities(text: str) -> list[str]:
    return [m.group(0) for m in _EQUALITY_RE.finditer(text)]


def extract_inequalities(text: str) -> list[str]:
    return [m.group(0) for m in _INEQUALITY_RE.finditer(text)]


def extract_boundary(text: str) -> list[str]:
    return [m.group(0) for m in _BOUNDARY_RE.finditer(text)]


def extract_initial(text: str) -> list[str]:
    return [m.group(0) for m in _INITIAL_RE.finditer(text)]


def extract_target(text: str) -> str | None:
    m = re.search(r"求\s*(.+?)(?:的|。|$)", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"(?:find|solve|compute)\s+(.+?)(?:\.|$)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def predict_answer_shape(text: str, is_proof: bool) -> str:
    if is_proof:
        return "proof"
    if any(kw in text for kw in ("方程组", "system")):
        return "set"
    if any(kw in text for kw in ("矩阵", "matrix")):
        return "matrix"
    if any(kw in text for kw in ("不等式", "inequality")):
        return "inequality"
    if any(kw in text for kw in ("区间", "interval")):
        return "interval"
    return "expression"


def detect_pde(text: str) -> bool:
    for sym in _PDE_SYMBOLS:
        if sym in text:
            return True
    return "偏微分" in text


def detect_case_split(text: str) -> bool:
    for kw in _CASE_SPLIT_KW:
        if kw in text:
            return True
    return False


def detect_tool_need(text: str) -> bool:
    lower = text.lower()
    for kw in _TOOL_KW:
        if kw in lower or kw in text:
            return True
    return False


# ── build_constraint_graph ──────────────────────────────────────────

def build_constraint_graph(norm: dict[str, Any]) -> dict[str, Any]:
    text = norm.get("clean_text", "")
    latex = norm.get("latex_blocks", [])
    is_proof = norm.get("is_proof", False)

    variables = extract_variables(text, latex)
    unknowns = extract_unknowns(text, variables)
    knowns = extract_knowns(text)
    domain_constraints = extract_domain(text)
    equality_constraints = extract_equalities(text)
    inequality_constraints = extract_inequalities(text)
    boundary_constraints = extract_boundary(text)
    initial_constraints = extract_initial(text)
    target = extract_target(text)
    answer_shape = predict_answer_shape(text, is_proof)
    has_pde = detect_pde(text)
    requires_case_split = detect_case_split(text)
    requires_tool = detect_tool_need(text)

    return {
        "variables": variables,
        "unknowns": unknowns,
        "knowns": knowns,
        "domain_constraints": domain_constraints,
        "equality_constraints": equality_constraints,
        "inequality_constraints": inequality_constraints,
        "boundary_constraints": boundary_constraints,
        "initial_constraints": initial_constraints,
        "target": target,
        "answer_shape": answer_shape,
        "has_pde": has_pde,
        "has_proof": is_proof,
        "requires_case_split": requires_case_split,
        "requires_tool": requires_tool,
    }

"""JSON extraction and validation utilities for LLM output."""

import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def extract_json_from_text(text: str) -> Optional[dict]:
    """Extract JSON object from LLM text output.

    Handles cases where JSON is embedded in markdown code blocks,
    mixed with explanatory text, or contains minor formatting issues.

    Args:
        text: Raw LLM output text that may contain JSON.

    Returns:
        Parsed JSON dict or None if extraction fails.
    """
    if not text or not text.strip():
        return None

    # Strategy 1: Try parsing the entire text as JSON
    try:
        result = json.loads(text.strip())
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code blocks (```json ... ```)
    code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    code_blocks = re.findall(code_block_pattern, text, re.DOTALL)
    for block in code_blocks:
        try:
            result = json.loads(block.strip())
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            continue

    # Strategy 3: Find the outermost { ... } using bracket matching
    start_idx = text.find("{")
    if start_idx == -1:
        logger.warning("No JSON object found in text")
        return None

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start_idx, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start_idx : i + 1]
                try:
                    result = json.loads(candidate)
                    if isinstance(result, dict):
                        return result
                except json.JSONDecodeError:
                    # Try fixing common issues
                    fixed = _try_fix_json(candidate)
                    if fixed:
                        return fixed
                break

    # Strategy 4: Try finding [ ... ] for array results
    start_idx = text.find("[")
    if start_idx != -1:
        depth = 0
        in_string = False
        escape_next = False
        for i in range(start_idx, len(text)):
            char = text[i]
            if escape_next:
                escape_next = False
                continue
            if char == "\\":
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    candidate = text[start_idx : i + 1]
                    try:
                        result = json.loads(candidate)
                        if isinstance(result, (dict, list)):
                            return result if isinstance(result, dict) else {"_array": result}
                    except json.JSONDecodeError:
                        pass
                    break

    logger.warning("Failed to extract JSON from text (first 200 chars): %s", text[:200])
    return None


def _try_fix_json(text: str) -> Optional[dict]:
    """Attempt to fix common JSON formatting issues from LLM output."""
    fixes = [
        # Remove trailing commas before } or ]
        (re.sub(r",\s*([\]}])", r"\1", text), "trailing comma fix"),
        # Fix single-quoted JSON keys only (not values)
        (re.sub(r"(?<!\\)'([A-Za-z_][A-Za-z0-9_]*)'\s*:", r'"\1":', text), "single quote key fix"),
        # Add missing closing braces
        (text + "}" * (text.count("{") - text.count("}")), "missing brace fix"),
    ]

    for fixed_text, fix_name in fixes:
        try:
            result = json.loads(fixed_text)
            if isinstance(result, dict):
                logger.info("JSON fixed with: %s", fix_name)
                return result
        except json.JSONDecodeError:
            continue

    return None


def validate_output(data: dict, required_fields: Optional[list[str]] = None) -> tuple[bool, list[str]]:
    """Validate extracted JSON against expected schema fields.

    Args:
        data: Parsed JSON dict to validate.
        required_fields: List of required field names. If None, uses default schema fields.

    Returns:
        Tuple of (is_valid, list_of_error_messages).
    """
    if required_fields is None:
        required_fields = [
            "domain",
            "problem_type",
            "difficulty",
            "difficulty_score",
            "reasoning_plan",
            "key_steps",
            "final_answer",
            "answer_format",
            "confidence",
            "verification_status",
            "verification_details",
            "educational_explanation",
            "token_usage_estimate",
            "processing_time_ms",
        ]

    errors = []

    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Type checks
    if "difficulty_score" in data:
        val = data["difficulty_score"]
        if not isinstance(val, (int, float)) or not (0.0 <= val <= 1.0):
            errors.append(f"difficulty_score must be float 0-1, got: {val}")

    if "confidence" in data:
        val = data["confidence"]
        if not isinstance(val, (int, float)) or not (0.0 <= val <= 1.0):
            errors.append(f"confidence must be float 0-1, got: {val}")

    if "reasoning_plan" in data:
        if not isinstance(data["reasoning_plan"], list):
            errors.append("reasoning_plan must be a list")

    if "key_steps" in data:
        if not isinstance(data["key_steps"], list):
            errors.append("key_steps must be a list")

    if "verification_details" in data:
        vd = data["verification_details"]
        if not isinstance(vd, dict):
            errors.append("verification_details must be a dict")
        else:
            for check in [
                "formula_consistency",
                "boundary_conditions",
                "logical_consistency",
                "special_cases",
                "dimension_check",
                "completeness",
            ]:
                if check not in vd:
                    errors.append(f"verification_details missing: {check}")

    is_valid = len(errors) == 0
    return is_valid, errors
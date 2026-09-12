#!/usr/bin/env python3
"""Token counting and API cost estimation for the conversation-api-cost plugin."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


PRICING_SOURCE = "https://developers.openai.com/api/docs/models/compare"
PRICING_CHECKED = "2026-09-10"
DEFAULT_MODEL = "gpt-5.6-sol"
MILLION = 1_000_000

# Reference rates per one million text tokens. They are intentionally kept in
# code so the server works offline; callers can always override them.
DEFAULT_PRICING: dict[str, dict[str, float | None]] = {
    "gpt-6-astra": {
        "input_per_million": 10.0,
        "cached_input_per_million": 1.0,
        "output_per_million": 50.0,
    },
    "gpt-5.6-sol": {
        "input_per_million": 4.0,
        "cached_input_per_million": 0.40,
        "output_per_million": 20.0,
    },
    "gpt-5.6-terra": {
        "input_per_million": 2.0,
        "cached_input_per_million": 0.20,
        "output_per_million": 12.0,
    },
    "gpt-5.6-luna": {
        "input_per_million": 0.20,
        "cached_input_per_million": 0.02,
        "output_per_million": 1.20,
    },
    "chat-latest": {
        "input_per_million": 5.0,
        "cached_input_per_million": 0.50,
        "output_per_million": 30.0,
    },
    "gpt-5-chat-latest": {
        "input_per_million": 1.25,
        "cached_input_per_million": 0.125,
        "output_per_million": 10.0,
    },
}

MODEL_ALIASES = {
    "gpt-5.6": "gpt-5.6-sol",
}


def _nonnegative_int(value: Any, field: str) -> int:
    """Validate a token count and return it as an integer."""
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a non-negative integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a non-negative integer") from exc
    if number < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return number


def content_to_text(content: Any) -> str:
    """Convert common chat message content shapes to countable text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text_value = item.get("text")
                if isinstance(text_value, str):
                    parts.append(text_value)
                elif isinstance(item.get("type"), str) and item["type"].endswith("image"):
                    parts.append("[image]")
                else:
                    parts.append(json.dumps(item, ensure_ascii=False, sort_keys=True))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if isinstance(content, (dict, int, float, bool)):
        return json.dumps(content, ensure_ascii=False, sort_keys=True)
    return str(content)


def _approximate_tokens(text: str) -> int:
    """A documented fallback: roughly one token per four characters."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def _tiktoken_count(text: str, model: str) -> int:
    try:
        import tiktoken  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "tiktoken is not installed; use count_method='approx' or install tiktoken"
        ) from exc

    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # New or custom model names may not be in tiktoken's model map. The
        # o200k encoding is the closest general-purpose fallback for modern
        # OpenAI models.
        try:
            encoding = tiktoken.get_encoding("o200k_base")
        except Exception:  # pragma: no cover - depends on local tiktoken data
            encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text, disallowed_special=()))


def count_tokens(
    text: str,
    model: str = DEFAULT_MODEL,
    method: str = "auto",
) -> tuple[int, str]:
    """Return (token_count, method_used)."""
    if method not in {"auto", "tiktoken", "approx"}:
        raise ValueError("count_method must be one of: auto, tiktoken, approx")
    if method == "approx":
        return _approximate_tokens(text), "approx-4chars"
    try:
        return _tiktoken_count(text, model), "tiktoken"
    except RuntimeError:
        if method == "tiktoken":
            raise
        return _approximate_tokens(text), "approx-4chars"


def resolve_model(model: str | None) -> str:
    selected = (model or DEFAULT_MODEL).strip()
    return MODEL_ALIASES.get(selected, selected)


def get_pricing(
    model: str | None = None,
    override: dict[str, Any] | None = None,
) -> tuple[str, dict[str, float]]:
    """Return canonical model and normalized prices."""
    if override is not None and not isinstance(override, dict):
        raise ValueError("pricing must be an object")
    canonical_model = resolve_model(model)
    base = DEFAULT_PRICING.get(canonical_model)
    if base is None and not override:
        supported = ", ".join(sorted(DEFAULT_PRICING))
        raise ValueError(
            f"No price configured for model '{canonical_model}'. "
            f"Pass pricing (input_per_million, cached_input_per_million, output_per_million). "
            f"Supported reference models: {supported}"
        )

    merged: dict[str, Any] = dict(base or {})
    if override:
        # Accept the shorter names too, because they are convenient in JSON.
        aliases = {
            "input": "input_per_million",
            "cached_input": "cached_input_per_million",
            "output": "output_per_million",
        }
        for key, value in override.items():
            merged[aliases.get(key, key)] = value

    required = ("input_per_million", "output_per_million")
    for key in required:
        if key not in merged:
            raise ValueError(f"pricing.{key} is required")
        try:
            merged[key] = float(merged[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"pricing.{key} must be a non-negative number") from exc
        if merged[key] < 0:
            raise ValueError(f"pricing.{key} must be a non-negative number")

    cached_key = "cached_input_per_million"
    if merged.get(cached_key) is None:
        merged[cached_key] = merged["input_per_million"]
    else:
        try:
            merged[cached_key] = float(merged[cached_key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"pricing.{cached_key} must be a non-negative number") from exc
        if merged[cached_key] < 0:
            raise ValueError(f"pricing.{cached_key} must be a non-negative number")

    return canonical_model, {
        "input_per_million": float(merged["input_per_million"]),
        "cached_input_per_million": float(merged[cached_key]),
        "output_per_million": float(merged["output_per_million"]),
    }


def calculate_token_cost(
    *,
    input_tokens: Any,
    output_tokens: Any,
    cached_input_tokens: Any = 0,
    model: str | None = None,
    pricing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate USD cost from billable token counts."""
    input_count = _nonnegative_int(input_tokens, "input_tokens")
    output_count = _nonnegative_int(output_tokens, "output_tokens")
    cached_count = _nonnegative_int(cached_input_tokens, "cached_input_tokens")
    if cached_count > input_count:
        raise ValueError("cached_input_tokens cannot exceed input_tokens")

    canonical_model, rates = get_pricing(model, pricing)
    regular_input_count = input_count - cached_count
    input_cost = regular_input_count / MILLION * rates["input_per_million"]
    cached_cost = cached_count / MILLION * rates["cached_input_per_million"]
    output_cost = output_count / MILLION * rates["output_per_million"]
    total = input_cost + cached_cost + output_cost

    return {
        "model": canonical_model,
        "pricing": rates,
        "tokens": {
            "input": input_count,
            "cached_input": cached_count,
            "uncached_input": regular_input_count,
            "output": output_count,
            "total": input_count + output_count,
        },
        "cost_usd": {
            "input": round(input_cost, 12),
            "cached_input": round(cached_cost, 12),
            "output": round(output_cost, 12),
            "total": round(total, 12),
        },
        "pricing_source": PRICING_SOURCE,
        "pricing_checked": PRICING_CHECKED,
    }


def _validate_messages(messages: Any) -> list[dict[str, Any]]:
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty array")
    validated: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError(f"messages[{index}] must be an object")
        role = message.get("role")
        if not isinstance(role, str) or not role.strip():
            raise ValueError(f"messages[{index}].role must be a non-empty string")
        validated.append(message)
    return validated


def _count_message_list(
    messages: list[dict[str, Any]],
    *,
    model: str,
    method: str,
    include_overhead: bool,
    message_overhead_tokens: int,
    request_overhead_tokens: int,
) -> tuple[int, str]:
    total = 0
    methods: set[str] = set()
    for message in messages:
        count, used_method = count_tokens(
            content_to_text(message.get("content")), model, method
        )
        total += count
        methods.add(used_method)
    if include_overhead:
        total += len(messages) * message_overhead_tokens + request_overhead_tokens
    return total, "+".join(sorted(methods)) if methods else "none"


def estimate_conversation_cost(
    *,
    messages: Any,
    model: str | None = None,
    cached_input_tokens: Any = 0,
    count_method: str = "auto",
    include_overhead: bool = True,
    message_overhead_tokens: Any = 4,
    request_overhead_tokens: Any = 2,
    pricing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Estimate cost by replaying visible messages across user turns."""
    validated = _validate_messages(messages)
    canonical_model, rates = get_pricing(model, pricing)
    message_overhead = _nonnegative_int(message_overhead_tokens, "message_overhead_tokens")
    request_overhead = _nonnegative_int(request_overhead_tokens, "request_overhead_tokens")

    user_indices = [
        index for index, message in enumerate(validated) if message["role"].lower() == "user"
    ]
    # A conversation without a user message is still useful as a one-request
    # estimate (for example, a system prompt supplied by a caller).
    request_indices = user_indices or [len(validated) - 1]

    turns: list[dict[str, Any]] = []
    total_input = 0
    total_output = 0
    methods: set[str] = set()

    for turn_number, user_index in enumerate(request_indices, start=1):
        next_user_index = (
            request_indices[turn_number] if turn_number < len(request_indices) else len(validated)
        )
        request_messages = validated[: user_index + 1]
        input_count, input_method = _count_message_list(
            request_messages,
            model=canonical_model,
            method=count_method,
            include_overhead=include_overhead,
            message_overhead_tokens=message_overhead,
            request_overhead_tokens=request_overhead,
        )
        output_count = 0
        output_methods: set[str] = set()
        for message in validated[user_index + 1 : next_user_index]:
            if message["role"].lower() != "assistant":
                continue
            count, output_method = count_tokens(
                content_to_text(message.get("content")), canonical_model, count_method
            )
            output_count += count
            output_methods.add(output_method)
        methods.update(filter(None, input_method.split("+")))
        methods.update(output_methods)
        total_input += input_count
        total_output += output_count
        turns.append(
            {
                "turn": turn_number,
                "user_message_index": user_index,
                "input_tokens": input_count,
                "output_tokens": output_count,
                "messages_sent": len(request_messages),
                "count_method": "+".join(sorted(set(filter(None, input_method.split("+"))) | output_methods)),
            }
        )

    cost = calculate_token_cost(
        input_tokens=total_input,
        output_tokens=total_output,
        cached_input_tokens=cached_input_tokens,
        model=canonical_model,
        pricing=rates,
    )
    cost["estimate"] = {
        "messages_received": len(validated),
        "turns_counted": len(turns),
        "turns": turns,
        "count_method": "+".join(sorted(methods)) if methods else "none",
        "include_overhead": include_overhead,
        "message_overhead_tokens": message_overhead if include_overhead else 0,
        "request_overhead_tokens": request_overhead if include_overhead else 0,
        "scope": "visible message content only",
        "note": "This is an estimate, not an invoice. Hidden prompts, tools, multimodal payloads, reasoning, and provider-specific serialization may change the real usage.",
    }
    return cost


def list_pricing() -> dict[str, Any]:
    return {
        "default_model": DEFAULT_MODEL,
        "pricing_checked": PRICING_CHECKED,
        "pricing_source": PRICING_SOURCE,
        "models": DEFAULT_PRICING,
        "aliases": MODEL_ALIASES,
        "note": "Override prices for models not listed or after a pricing change.",
    }


def _read_json_argument(raw: str | None, file_path: str | None) -> Any:
    if raw is not None and file_path is not None:
        raise ValueError("use only one of --json and --file")
    if file_path:
        text = sys.stdin.read() if file_path == "-" else Path(file_path).read_text(encoding="utf-8")
    elif raw is not None:
        text = raw
    else:
        raise ValueError("provide --json or --file")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc


def _add_pricing_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--input-price", type=float, help="USD per one million input tokens")
    parser.add_argument(
        "--cached-input-price", type=float, help="USD per one million cached input tokens"
    )
    parser.add_argument("--output-price", type=float, help="USD per one million output tokens")


def _pricing_from_args(args: argparse.Namespace) -> dict[str, float] | None:
    values = {
        "input_per_million": args.input_price,
        "cached_input_per_million": args.cached_input_price,
        "output_per_million": args.output_price,
    }
    supplied = {key: value for key, value in values.items() if value is not None}
    return supplied or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    cost_parser = subparsers.add_parser("cost", help="calculate from explicit token counts")
    _add_pricing_options(cost_parser)
    cost_parser.add_argument("--input-tokens", type=int, required=True)
    cost_parser.add_argument("--output-tokens", type=int, required=True)
    cost_parser.add_argument("--cached-input-tokens", type=int, default=0)

    conversation_parser = subparsers.add_parser(
        "conversation", help="estimate from a JSON array of messages"
    )
    _add_pricing_options(conversation_parser)
    conversation_parser.add_argument("--json", help="JSON array or object with a messages array")
    conversation_parser.add_argument("--file", help="read JSON from a file, or '-' for stdin")
    conversation_parser.add_argument("--cached-input-tokens", type=int, default=0)
    conversation_parser.add_argument(
        "--count-method", choices=("auto", "tiktoken", "approx"), default="auto"
    )
    conversation_parser.add_argument("--no-overhead", action="store_true")

    subparsers.add_parser("pricing", help="list built-in reference prices")
    return parser


def cli_main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "pricing":
            result = list_pricing()
        elif args.command == "cost":
            result = calculate_token_cost(
                input_tokens=args.input_tokens,
                output_tokens=args.output_tokens,
                cached_input_tokens=args.cached_input_tokens,
                model=args.model,
                pricing=_pricing_from_args(args),
            )
        else:
            payload = _read_json_argument(args.json, args.file)
            if isinstance(payload, dict) and "messages" in payload:
                payload = payload["messages"]
            result = estimate_conversation_cost(
                messages=payload,
                model=args.model,
                cached_input_tokens=args.cached_input_tokens,
                count_method=args.count_method,
                include_overhead=not args.no_overhead,
                pricing=_pricing_from_args(args),
            )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli_main())

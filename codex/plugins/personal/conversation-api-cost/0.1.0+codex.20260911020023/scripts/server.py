#!/usr/bin/env python3
"""Minimal stdio MCP server for conversation-api-cost."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from calculate_cost import (  # noqa: E402
    DEFAULT_MODEL,
    calculate_token_cost,
    estimate_conversation_cost,
    list_pricing,
)


SERVER_NAME = "conversation-api-cost"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"


def _tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "calculate_token_cost",
            "description": "Calcula o custo em USD usando contagens explícitas de tokens da API.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "default": DEFAULT_MODEL},
                    "input_tokens": {"type": "integer", "minimum": 0},
                    "cached_input_tokens": {"type": "integer", "minimum": 0, "default": 0},
                    "output_tokens": {"type": "integer", "minimum": 0},
                    "pricing": {
                        "type": "object",
                        "description": "Opcional: tarifas por um milhão de tokens.",
                        "properties": {
                            "input_per_million": {"type": "number", "minimum": 0},
                            "cached_input_per_million": {"type": "number", "minimum": 0},
                            "output_per_million": {"type": "number", "minimum": 0},
                        },
                    },
                },
                "required": ["input_tokens", "output_tokens"],
            },
        },
        {
            "name": "estimate_conversation_cost",
            "description": "Estima o custo de uma conversa visível, recontando o contexto enviado em cada rodada.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "default": DEFAULT_MODEL},
                    "messages": {
                        "type": "array",
                        "description": "Mensagens visíveis no formato [{role, content}].",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {"type": "string"},
                                "content": {},
                            },
                            "required": ["role", "content"],
                        },
                    },
                    "cached_input_tokens": {"type": "integer", "minimum": 0, "default": 0},
                    "count_method": {
                        "type": "string",
                        "enum": ["auto", "tiktoken", "approx"],
                        "default": "auto",
                    },
                    "include_overhead": {"type": "boolean", "default": True},
                    "message_overhead_tokens": {"type": "integer", "minimum": 0, "default": 4},
                    "request_overhead_tokens": {"type": "integer", "minimum": 0, "default": 2},
                    "pricing": {
                        "type": "object",
                        "description": "Opcional: tarifas por um milhão de tokens.",
                        "properties": {
                            "input_per_million": {"type": "number", "minimum": 0},
                            "cached_input_per_million": {"type": "number", "minimum": 0},
                            "output_per_million": {"type": "number", "minimum": 0},
                        },
                    },
                },
                "required": ["messages"],
            },
        },
        {
            "name": "list_pricing",
            "description": "Lista os modelos e tarifas de referência embutidos no plugin.",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_result(value: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(value, ensure_ascii=False, indent=2),
            }
        ],
        "isError": is_error,
    }


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "calculate_token_cost":
        return _tool_result(calculate_token_cost(**arguments))
    if name == "estimate_conversation_cost":
        return _tool_result(estimate_conversation_cost(**arguments))
    if name == "list_pricing":
        return _tool_result(list_pricing())
    raise ValueError(f"unknown tool: {name}")


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}

    # Notifications do not receive a JSON-RPC response.
    if request_id is None and method in {"notifications/initialized", "notifications/cancelled"}:
        return None
    if not isinstance(method, str):
        return _jsonrpc_error(request_id, -32600, "Invalid Request")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": _tool_definitions()}}
    if method == "tools/call":
        if not isinstance(params, dict):
            return _jsonrpc_error(request_id, -32602, "params must be an object")
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return _jsonrpc_error(request_id, -32602, "tools/call requires name and object arguments")
        try:
            result = _call_tool(name, arguments)
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            result = _tool_result({"error": str(exc)}, is_error=True)
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")


def main() -> int:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                response = _jsonrpc_error(None, -32600, "Invalid Request")
            else:
                response = handle_request(request)
        except json.JSONDecodeError as exc:
            response = _jsonrpc_error(None, -32700, f"Parse error: {exc}")
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

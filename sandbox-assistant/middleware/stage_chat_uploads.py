"""Stage chat file attachments into the per-thread LangSmith sandbox.

There is no separate upload HTTP endpoint. The browser attaches a file in the
chat UI (`src/components/chat-app.tsx`), encodes it as base64, and submits a
multimodal human message via `useStream` / LangGraph.

This middleware runs before the model sees that message:

1. **`awrap_model_call` / `wrap_model_call`** — find allowed `file` blocks on the
   latest human message, invoke harness `write_file` to
   `/workspace/uploads/<safe-name>`.
   - **Text files** (`.txt`, `.md`, `.py`, …): decode base64 → UTF-8 and pass
     plain text (sandbox `write` treats text MIME as UTF-8).
   - **PDFs**: pass base64 as-is (sandbox `write` decodes base64 for
     `application/pdf`).
2. Replace heavy file blocks with a short text note listing sandbox paths.
3. **`after_model`** — persist the rewritten human message into graph state
   (`additional_kwargs.mda_staged_uploads` holds the staged paths).

Idempotency: in-process `staged_keys` avoids re-uploading the same message
across model calls in one turn; `mda_staged_uploads` skips once state is
rewritten.

Wire this in `agent.py` via `middleware=[stage_chat_uploads_middleware()]`.
"""

from __future__ import annotations

import base64
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal
from uuid import uuid4

from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
)
from langchain.tools import ToolRuntime
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)

UPLOAD_DIR = "/workspace/uploads"
STAGED_KWARG = "mda_staged_uploads"

_staged_keys: set[str] = set()
_pending_rewrites: dict[str, HumanMessage] = {}

TEXT_EXTENSIONS = frozenset(
    {
        ".txt",
        ".md",
        ".markdown",
        ".csv",
        ".tsv",
        ".json",
        ".jsonl",
        ".xml",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".log",
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".css",
        ".html",
        ".htm",
        ".sql",
        ".sh",
        ".bash",
        ".zsh",
        ".rs",
        ".go",
        ".java",
        ".rb",
        ".php",
        ".env",
    }
)

UploadKind = Literal["text", "pdf"]

_DATA_URL_RE = re.compile(r"^data:([^;,]+)?(;base64)?,([\s\S]+)$", re.IGNORECASE)


@dataclass(frozen=True)
class _StagedUpload:
    file_name: str
    write_content: str
    path: str
    kind: UploadKind


def _ext_of(name: str | None) -> str:
    if not name:
        return ""
    i = name.rfind(".")
    return name[i:].lower() if i >= 0 else ""


def _is_pdf_mime(mime: str | None) -> bool:
    if not mime:
        return False
    normalized = mime.lower()
    return normalized == "application/pdf" or normalized.endswith("/pdf")


def _is_text_mime(mime: str | None) -> bool:
    if not mime:
        return False
    normalized = mime.lower()
    return (
        normalized.startswith("text/")
        or normalized == "application/json"
        or normalized == "application/javascript"
        or normalized == "application/xml"
        or normalized == "application/x-yaml"
        or normalized == "application/toml"
    )


def _classify_upload(mime: str | None, file_name: str | None) -> UploadKind | None:
    ext = _ext_of(file_name)
    if _is_pdf_mime(mime) or ext == ".pdf":
        return "pdf"
    if _is_text_mime(mime) or ext in TEXT_EXTENSIONS:
        return "text"
    return None


def _safe_file_name(raw: str, index: int, kind: UploadKind) -> str:
    fallback = f"upload-{index + 1}.pdf" if kind == "pdf" else f"upload-{index + 1}.txt"
    base = re.sub(r"[^a-zA-Z0-9._-]+", "_", raw).lstrip(".")
    name = base or fallback
    if kind == "pdf" and not name.lower().endswith(".pdf"):
        return f"{name}.pdf"[:120]
    return name[:120]


def _parse_data_url(url: str) -> tuple[str | None, str] | None:
    match = _DATA_URL_RE.match(url)
    if not match:
        return None
    if not match.group(2):
        return None
    return match.group(1), match.group(3)


def _decode_base64_utf8(data: str) -> str:
    return base64.b64decode(data).decode("utf-8")


def _collect_uploads(content: object) -> list[_StagedUpload]:
    if not isinstance(content, list):
        return []

    uploads: list[_StagedUpload] = []
    index = 0

    for block in content:
        if not isinstance(block, dict) or block.get("type") != "file":
            continue

        mime = (
            block.get("mime_type")
            if isinstance(block.get("mime_type"), str)
            else block.get("mimeType")
            if isinstance(block.get("mimeType"), str)
            else block.get("mediaType")
            if isinstance(block.get("mediaType"), str)
            else None
        )

        meta = block.get("metadata") if isinstance(block.get("metadata"), dict) else None
        file_name_candidate = (
            block.get("name")
            if isinstance(block.get("name"), str)
            else block.get("filename")
            if isinstance(block.get("filename"), str)
            else meta.get("filename")
            if meta and isinstance(meta.get("filename"), str)
            else meta.get("name")
            if meta and isinstance(meta.get("name"), str)
            else None
        )

        b64: str | None = None
        data_url_mime: str | None = None
        data = block.get("data")
        if isinstance(data, str) and data:
            b64 = data
        else:
            url = block.get("url")
            if isinstance(url, str) and url.startswith("data:"):
                parsed = _parse_data_url(url)
                if parsed:
                    data_url_mime, b64 = parsed

        if not b64:
            continue

        effective_mime = mime or data_url_mime
        kind = _classify_upload(
            effective_mime if isinstance(effective_mime, str) else None,
            file_name_candidate if isinstance(file_name_candidate, str) else None,
        )
        if not kind:
            continue

        file_name = _safe_file_name(
            file_name_candidate
            if isinstance(file_name_candidate, str)
            else (f"upload-{index + 1}.pdf" if kind == "pdf" else f"upload-{index + 1}.txt"),
            index,
            kind,
        )
        uploads.append(
            _StagedUpload(
                file_name=file_name,
                path=f"{UPLOAD_DIR}/{file_name}",
                kind=kind,
                write_content=_decode_base64_utf8(b64) if kind == "text" else b64,
            )
        )
        index += 1

    return uploads


def _staging_note(uploads: list[_StagedUpload]) -> str:
    lines: list[str] = []
    for u in uploads:
        if u.kind == "pdf":
            lines.append(
                f"- `{u.path}` (PDF — extract with pypdf via execute, then read the sibling .txt)"
            )
        else:
            lines.append(f"- `{u.path}` (text — read_file / grep directly)")
    header = (
        "Attached file staged in the sandbox:"
        if len(uploads) == 1
        else "Attached files staged in the sandbox:"
    )
    return f"{header}\n" + "\n".join(lines)


def _rewrite_content(content: object, uploads: list[_StagedUpload]) -> str:
    note = _staging_note(uploads)
    text_parts: list[str] = []

    if isinstance(content, str) and content.strip():
        text_parts.append(content.strip())
    elif isinstance(content, list):
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "text"
                and isinstance(block.get("text"), str)
            ):
                t = block["text"].strip()
                if t:
                    text_parts.append(t)

    text_parts.append(note)
    return "\n\n".join(text_parts)


def _message_key(message: BaseMessage) -> str:
    if isinstance(message.id, str) and message.id:
        return message.id
    text = message.content[:80] if isinstance(message.content, str) else "human"
    length = len(message.content) if isinstance(message.content, list) else 0
    return f"anon:{text}:{length}"


def _already_staged(message: BaseMessage) -> bool:
    kwargs = message.additional_kwargs or {}
    staged = kwargs.get(STAGED_KWARG) or kwargs.get("mda_staged_pdfs")
    return isinstance(staged, list) and len(staged) > 0


def _find_write_file_tool(tools: list[BaseTool | dict[str, Any]]) -> BaseTool | None:
    for tool in tools:
        if isinstance(tool, BaseTool) and tool.name == "write_file":
            return tool
    return None


def _tool_runtime_for(request: ModelRequest[Any]) -> ToolRuntime[Any, Any]:
    lg_runtime = request.runtime
    tools = [t for t in request.tools if isinstance(t, BaseTool)]
    return ToolRuntime(
        state=request.state,
        context=getattr(lg_runtime, "context", None),
        config={},
        stream_writer=getattr(lg_runtime, "stream_writer", lambda _x: None),
        tool_call_id=f"stage-upload-{uuid4().hex[:12]}",
        store=getattr(lg_runtime, "store", None),
        tools=tools,
        execution_info=getattr(lg_runtime, "execution_info", None),
        server_info=getattr(lg_runtime, "server_info", None),
    )


async def _stage_uploads(
    request: ModelRequest[Any],
) -> ModelRequest[Any] | None:
    """Return an overridden request with staged uploads, or None if unchanged."""
    messages = request.messages
    if not messages:
        return None

    last_human_index = -1
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            last_human_index = i
            break
    if last_human_index < 0:
        return None

    human = messages[last_human_index]
    if _already_staged(human):
        return None

    uploads = _collect_uploads(human.content)
    if not uploads:
        return None

    key = _message_key(human)
    write_file = _find_write_file_tool(request.tools)
    if write_file is None:
        logger.warning(
            "[stageChatUploads] write_file tool unavailable; leaving file blocks in the message"
        )
        return None

    if key not in _staged_keys:
        tool_runtime = _tool_runtime_for(request)
        for upload in uploads:
            try:
                await write_file.ainvoke(
                    {
                        "file_path": upload.path,
                        "content": upload.write_content,
                        "runtime": tool_runtime,
                    }
                )
            except Exception:
                logger.exception("[stageChatUploads] failed to stage %s", upload.path)
                return None
        _staged_keys.add(key)

    rewritten = HumanMessage(
        id=human.id,
        content=_rewrite_content(human.content, uploads),
        additional_kwargs={
            **(human.additional_kwargs or {}),
            STAGED_KWARG: [u.path for u in uploads],
        },
        response_metadata=human.response_metadata,
    )
    _pending_rewrites[key] = rewritten

    next_messages = list(messages)
    next_messages[last_human_index] = rewritten
    return request.override(messages=next_messages)


def _after_model_updates(state: AgentState[Any]) -> dict[str, Any] | None:
    if not _pending_rewrites:
        return None
    messages = state.get("messages")
    if not messages:
        return None

    changed = False
    next_messages: list[Any] = []
    for message in messages:
        if not isinstance(message, HumanMessage):
            next_messages.append(message)
            continue
        key = _message_key(message)
        rewritten = _pending_rewrites.pop(key, None)
        if rewritten is None:
            next_messages.append(message)
            continue
        changed = True
        next_messages.append(rewritten)

    return {"messages": next_messages} if changed else None


class _StageChatUploadsMiddleware(AgentMiddleware[AgentState[Any], Any]):
    """Stages chat file attachments onto the sandbox filesystem."""

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        next_request = await _stage_uploads(request)
        return await handler(next_request if next_request is not None else request)

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        # Sync path: stage via asyncio when an event loop is not running is awkward;
        # prefer awrap_model_call. Still implement a best-effort sync stage using
        # tool.invoke for environments that call the graph synchronously.
        messages = request.messages
        if not messages:
            return handler(request)

        last_human_index = -1
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], HumanMessage):
                last_human_index = i
                break
        if last_human_index < 0:
            return handler(request)

        human = messages[last_human_index]
        if _already_staged(human):
            return handler(request)

        uploads = _collect_uploads(human.content)
        if not uploads:
            return handler(request)

        key = _message_key(human)
        write_file = _find_write_file_tool(request.tools)
        if write_file is None:
            logger.warning(
                "[stageChatUploads] write_file tool unavailable; leaving file blocks in the message"
            )
            return handler(request)

        if key not in _staged_keys:
            tool_runtime = _tool_runtime_for(request)
            for upload in uploads:
                try:
                    write_file.invoke(
                        {
                            "file_path": upload.path,
                            "content": upload.write_content,
                            "runtime": tool_runtime,
                        }
                    )
                except Exception:
                    logger.exception("[stageChatUploads] failed to stage %s", upload.path)
                    return handler(request)
            _staged_keys.add(key)

        rewritten = HumanMessage(
            id=human.id,
            content=_rewrite_content(human.content, uploads),
            additional_kwargs={
                **(human.additional_kwargs or {}),
                STAGED_KWARG: [u.path for u in uploads],
            },
            response_metadata=human.response_metadata,
        )
        _pending_rewrites[key] = rewritten
        next_messages = list(messages)
        next_messages[last_human_index] = rewritten
        return handler(request.override(messages=next_messages))

    def after_model(
        self,
        state: AgentState[Any],
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del runtime
        return _after_model_updates(state)


def stage_chat_uploads_middleware() -> AgentMiddleware[AgentState[Any], Any]:
    """Return Deep Agents middleware that stages chat file attachments."""
    return _StageChatUploadsMiddleware()

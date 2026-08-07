"""Stage chat file attachments into the per-thread LangSmith sandbox.

There is no separate upload HTTP endpoint. The browser attaches a file in the
chat UI (`src/components/chat-app.tsx`), encodes it as base64, and submits a
multimodal human message via `useStream` / LangGraph.

This middleware runs before the model sees that message:

1. **`awrap_model_call` / `wrap_model_call`** — find allowed `file` blocks on the
   latest human message and seed them with sandbox ``aupload_files`` /
   ``upload_files`` (HTTP dataplane), **not** harness ``write_file``.
   ``write_file`` → ``awrite`` runs an ``execute`` mkdir preflight over the
   websocket command stream; cold LangSmith boxes often never emit ``started``,
   so staging hangs/fails. File-transfer upload avoids that path.
   - **Text files**: decode base64 → raw UTF-8 bytes.
   - **PDFs**: decode base64 → PDF bytes, also extract text with ``pypdf`` on the
     host and upload a sibling ``.txt`` so the agent need not ``execute``.
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
from io import BytesIO
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

# Seed under /home/user (exists on LangSmith images) so HTTP upload need not
# mkdir via websocket execute — cold boxes often never ready the command stream.
UPLOAD_DIR = "/home/user"
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
    path: str
    kind: UploadKind
    data: bytes
    text_path: str | None = None
    text_data: bytes | None = None


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


def _extract_pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


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
        raw = base64.b64decode(b64)
        text_path: str | None = None
        text_data: bytes | None = None
        if kind == "pdf":
            try:
                extracted = _extract_pdf_text(raw)
            except Exception:
                logger.exception("[stageChatUploads] pypdf extract failed for %s", file_name)
                extracted = ""
            if file_name.lower().endswith(".pdf"):
                text_name = f"{file_name[:-4]}.txt"
            else:
                text_name = f"{file_name}.txt"
            text_path = f"{UPLOAD_DIR}/{text_name}"
            text_data = extracted.encode("utf-8")
        elif kind == "text":
            # Reject non-UTF-8 early so we don't seed binary as "text".
            raw.decode("utf-8")

        uploads.append(
            _StagedUpload(
                file_name=file_name,
                path=f"{UPLOAD_DIR}/{file_name}",
                kind=kind,
                data=raw,
                text_path=text_path,
                text_data=text_data,
            )
        )
        index += 1

    return uploads


def _staging_note(uploads: list[_StagedUpload]) -> str:
    lines: list[str] = []
    for u in uploads:
        if u.kind == "pdf":
            if u.text_path:
                lines.append(
                    f"- `{u.path}` (PDF) — extracted text is at `{u.text_path}` "
                    "(read_file / grep that .txt; do not re-extract)"
                )
            else:
                lines.append(f"- `{u.path}` (PDF — extraction failed; tell the user)")
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


def _filesystem_middleware_owner(tool: BaseTool) -> Any | None:
    """Pull the FilesystemMiddleware instance out of a harness tool closure."""
    for attr in ("coroutine", "func"):
        fn = getattr(tool, attr, None)
        closure = getattr(fn, "__closure__", None)
        if not closure:
            continue
        for cell in closure:
            owner = cell.cell_contents
            if callable(getattr(owner, "_get_backend", None)):
                return owner
    return None


def _tool_runtime_for(request: ModelRequest[Any]) -> ToolRuntime[Any, Any]:
    lg_runtime = request.runtime
    tools = [t for t in request.tools if isinstance(t, BaseTool)]
    config: dict[str, Any] = {}
    try:
        from langgraph.config import get_config

        ambient = get_config()
        if isinstance(ambient, dict):
            config = ambient
    except Exception:
        config = {}
    return ToolRuntime(
        state=request.state,
        context=getattr(lg_runtime, "context", None),
        config=config,
        stream_writer=getattr(lg_runtime, "stream_writer", lambda _x: None),
        tool_call_id=f"stage-upload-{uuid4().hex[:12]}",
        store=getattr(lg_runtime, "store", None),
        tools=tools,
        execution_info=getattr(lg_runtime, "execution_info", None),
        server_info=getattr(lg_runtime, "server_info", None),
    )


def _resolve_backend(request: ModelRequest[Any]) -> Any | None:
    write_file = _find_write_file_tool(request.tools)
    if write_file is None:
        return None
    owner = _filesystem_middleware_owner(write_file)
    if owner is None:
        return None
    return owner._get_backend(_tool_runtime_for(request))


def _files_to_upload(uploads: list[_StagedUpload]) -> list[tuple[str, bytes]]:
    files: list[tuple[str, bytes]] = []
    for upload in uploads:
        files.append((upload.path, upload.data))
        if upload.text_path is not None and upload.text_data is not None:
            files.append((upload.text_path, upload.text_data))
    return files


def _assert_upload_ok(responses: list[Any], files: list[tuple[str, bytes]]) -> None:
    if len(responses) != len(files):
        msg = f"expected {len(files)} upload response(s), got {len(responses)}"
        raise RuntimeError(msg)
    for response, (path, _) in zip(responses, files, strict=True):
        error = getattr(response, "error", None)
        if error:
            raise RuntimeError(f"failed to upload {path}: {error}")


async def _aupload(backend: Any, files: list[tuple[str, bytes]]) -> None:
    aupload = getattr(backend, "aupload_files", None)
    if callable(aupload):
        responses = await aupload(files)
        _assert_upload_ok(list(responses), files)
        return
    upload = getattr(backend, "upload_files", None)
    if callable(upload):
        responses = upload(files)
        _assert_upload_ok(list(responses), files)
        return
    msg = "sandbox backend has no upload_files / aupload_files"
    raise RuntimeError(msg)


def _upload(backend: Any, files: list[tuple[str, bytes]]) -> None:
    upload = getattr(backend, "upload_files", None)
    if callable(upload):
        responses = upload(files)
        _assert_upload_ok(list(responses), files)
        return
    msg = "sandbox backend has no upload_files"
    raise RuntimeError(msg)


def _rewritten_human(human: HumanMessage, uploads: list[_StagedUpload]) -> HumanMessage:
    return HumanMessage(
        id=human.id,
        content=_rewrite_content(human.content, uploads),
        additional_kwargs={
            **(human.additional_kwargs or {}),
            STAGED_KWARG: [
                path
                for u in uploads
                for path in ((u.path, u.text_path) if u.text_path else (u.path,))
                if path
            ],
        },
        response_metadata=human.response_metadata,
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
    backend = _resolve_backend(request)
    if backend is None:
        logger.warning(
            "[stageChatUploads] sandbox backend unavailable; leaving file blocks in the message"
        )
        return None

    if key not in _staged_keys:
        files = _files_to_upload(uploads)
        try:
            await _aupload(backend, files)
        except Exception:
            logger.exception(
                "[stageChatUploads] failed to stage %s",
                ", ".join(u.path for u in uploads),
            )
            return None
        _staged_keys.add(key)

    rewritten = _rewritten_human(human, uploads)
    _pending_rewrites[key] = rewritten

    next_messages = list(messages)
    next_messages[last_human_index] = rewritten
    return request.override(messages=next_messages)


def _stage_uploads_sync(request: ModelRequest[Any]) -> ModelRequest[Any] | None:
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
    backend = _resolve_backend(request)
    if backend is None:
        logger.warning(
            "[stageChatUploads] sandbox backend unavailable; leaving file blocks in the message"
        )
        return None

    if key not in _staged_keys:
        files = _files_to_upload(uploads)
        try:
            _upload(backend, files)
        except Exception:
            logger.exception(
                "[stageChatUploads] failed to stage %s",
                ", ".join(u.path for u in uploads),
            )
            return None
        _staged_keys.add(key)

    rewritten = _rewritten_human(human, uploads)
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
        next_request = _stage_uploads_sync(request)
        return handler(next_request if next_request is not None else request)

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

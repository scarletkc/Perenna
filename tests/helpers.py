from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).parents[1]


class EmbeddingServer:
    def __init__(self) -> None:
        self.requests: list[list[str]] = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                size = int(self.headers.get("content-length", "0"))
                payload = json.loads(self.rfile.read(size))
                raw_inputs = payload["input"]
                inputs = [raw_inputs] if isinstance(raw_inputs, str) else list(raw_inputs)
                owner.requests.append(inputs)
                data = [
                    {
                        "object": "embedding",
                        "embedding": _embedding(text),
                        "index": index,
                    }
                    for index, text in enumerate(inputs)
                ]
                response = json.dumps(
                    {
                        "object": "list",
                        "data": data,
                        "model": payload.get("model", "perenna-test"),
                        "usage": {"prompt_tokens": 0, "total_tokens": 0},
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, _format: str, *args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}/v1"

    def environment(self) -> dict[str, str]:
        return {
            "VEXOR_CONFIG_JSON": json.dumps(
                {
                    "provider": "custom",
                    "model": "perenna-test",
                    "base_url": self.base_url,
                    "batch_size": 16,
                    "embed_concurrency": 1,
                    "embedding_dimensions": None,
                }
            ),
            "VEXOR_API_KEY": "offline-test-key",
        }

    def __enter__(self) -> EmbeddingServer:
        self._thread.start()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


class CapturedStderr:
    def __init__(self) -> None:
        self._file = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        self._closed_text: str | None = None

    def fileno(self) -> int:
        return self._file.fileno()

    def write(self, value: str) -> int:
        return self._file.write(value)

    def flush(self) -> None:
        self._file.flush()

    def getvalue(self) -> str:
        if self._closed_text is not None:
            return self._closed_text
        self._file.flush()
        position = self._file.tell()
        self._file.seek(0)
        value = self._file.read()
        self._file.seek(position)
        return value

    def close(self) -> None:
        if self._closed_text is None:
            self._closed_text = self.getvalue()
            self._file.close()


@asynccontextmanager
async def perenna_session(
    home: Path,
    *,
    embedding_server: EmbeddingServer | None = None,
) -> AsyncIterator[tuple[ClientSession, Any, CapturedStderr]]:
    environment = os.environ.copy()
    environment["PERENNA_GIT_REMOTE"] = ""
    environment.pop("PERENNA_HOME", None)
    if embedding_server is not None:
        environment.update(embedding_server.environment())
    stderr = CapturedStderr()
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "perenna",
            "mcp",
            "--home",
            os.fspath(home),
        ],
        env=environment,
        cwd=PROJECT_ROOT,
    )
    try:
        async with stdio_client(parameters, errlog=stderr) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                initialized = await session.initialize()
                yield session, initialized, stderr
    finally:
        stderr.close()


def result_text(result: Any) -> str:
    return "\n".join(block.text for block in result.content if block.type == "text")


def _embedding(text: str) -> list[float]:
    values = [0.0] * 16
    lowered = text.casefold()
    for index, character in enumerate(lowered):
        values[(ord(character) + index * 7) % len(values)] += 1.0
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]

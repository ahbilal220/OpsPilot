import asyncio
import os
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.evidence.models import EvidenceType
from app.tools.contracts import (
    AdapterResult,
    EvidenceDraft,
    ToolContext,
    ToolDefinition,
    ToolRisk,
)

DENIED_PARTS = frozenset({".env", ".git", ".ssh", "credentials", "secrets"})
TEXT_SUFFIXES = frozenset(
    {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".go",
        ".rs",
        ".java",
        ".sql",
        ".md",
        ".toml",
        ".yaml",
        ".yml",
    }
)


def safe_relative_path(value: str | None) -> Path:
    candidate = Path(value or ".")
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("path must remain inside the configured repository")
    if any(part.casefold() in DENIED_PARTS for part in candidate.parts):
        raise ValueError("path is denied")
    return candidate


class CodeSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=2, max_length=120)
    path: str | None = Field(default=None, max_length=500)
    limit: int = Field(default=50, ge=1, le=100)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str | None) -> str | None:
        safe_relative_path(value)
        return value


class CodeMatch(BaseModel):
    path: str
    line: int
    text: str


class CodeSearchOutput(BaseModel):
    matches: list[CodeMatch]
    truncated: bool


class RepositorySearchTool:
    input_model = CodeSearchInput

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self.definition = ToolDefinition(
            name="repository.search",
            description="Search text files in the fixed read-only demo repository.",
            risk=ToolRisk.read,
            read_only=True,
            timeout_seconds=8,
            input_schema=CodeSearchInput.model_json_schema(),
            output_schema=CodeSearchOutput.model_json_schema(),
        )

    def _search(self, query: CodeSearchInput) -> CodeSearchOutput:
        target = (self._root / safe_relative_path(query.path)).resolve()
        if not target.is_relative_to(self._root):
            raise ValueError("path escaped configured repository")
        candidates = [target] if target.is_file() else target.rglob("*")
        matches: list[CodeMatch] = []
        truncated = False
        for path in candidates:
            if (
                path.is_symlink()
                or not path.resolve().is_relative_to(self._root)
                or not path.is_file()
                or path.suffix.casefold() not in TEXT_SUFFIXES
            ):
                continue
            relative = path.relative_to(self._root)
            if any(part.casefold() in DENIED_PARTS for part in relative.parts):
                continue
            if path.stat().st_size > 1_000_000:
                continue
            for number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if query.query.casefold() in line.casefold():
                    matches.append(CodeMatch(path=str(relative), line=number, text=line[:500]))
                    if len(matches) >= query.limit:
                        truncated = True
                        return CodeSearchOutput(matches=matches, truncated=truncated)
        return CodeSearchOutput(matches=matches, truncated=truncated)

    async def execute(self, context: ToolContext, arguments: BaseModel) -> AdapterResult:
        query = CodeSearchInput.model_validate(arguments)
        output = await asyncio.to_thread(self._search, query)
        return AdapterResult(
            summary=f"Found {len(output.matches)} code matches for the literal query.",
            data=output.model_dump(mode="json"),
            evidence=[
                EvidenceDraft(
                    type=EvidenceType.code,
                    source="demo-repository",
                    source_reference=f"repo://{query.path or '.'}",
                    summary=f"{len(output.matches)} code locations matched {query.query!r}.",
                    content=output.model_dump(mode="json"),
                )
            ],
        )


class GitHistoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str | None = Field(default=None, max_length=500)
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str | None) -> str | None:
        safe_relative_path(value)
        return value


class GitCommit(BaseModel):
    sha: str
    authored_at: str
    author: str
    subject: str


class GitHistoryOutput(BaseModel):
    commits: list[GitCommit]


class GitHistoryTool:
    input_model = GitHistoryInput

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self.definition = ToolDefinition(
            name="repository.history",
            description="Read commit history from the fixed demo Git repository.",
            risk=ToolRisk.read,
            read_only=True,
            timeout_seconds=8,
            input_schema=GitHistoryInput.model_json_schema(),
            output_schema=GitHistoryOutput.model_json_schema(),
        )

    def _history(self, query: GitHistoryInput) -> GitHistoryOutput:
        command = [
            "git",
            "-c",
            f"safe.directory={self._root}",
            "-C",
            str(self._root),
            "log",
            "--no-decorate",
            f"--max-count={query.limit}",
            "--format=%H%x1f%aI%x1f%an%x1f%s%x1e",
        ]
        if query.path:
            command.extend(["--", str(safe_relative_path(query.path))])
        environment = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"}
        completed = subprocess.run(
            command,
            cwd=self._root,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=6,
        )
        commits = []
        for record in completed.stdout.strip("\n\x1e").split("\x1e"):
            if not record.strip():
                continue
            fields = record.strip().split("\x1f", 3)
            if len(fields) == 4:
                commits.append(
                    GitCommit(
                        sha=fields[0], authored_at=fields[1], author=fields[2], subject=fields[3]
                    )
                )
        return GitHistoryOutput(commits=commits)

    async def execute(self, context: ToolContext, arguments: BaseModel) -> AdapterResult:
        query = GitHistoryInput.model_validate(arguments)
        output = await asyncio.to_thread(self._history, query)
        return AdapterResult(
            summary=f"Read {len(output.commits)} commits from the demo repository.",
            data=output.model_dump(mode="json"),
            evidence=[
                EvidenceDraft(
                    type=EvidenceType.git,
                    source="demo-repository",
                    source_reference=f"git://history/{query.path or ''}",
                    summary=f"{len(output.commits)} recent commits were inspected.",
                    content=output.model_dump(mode="json"),
                )
            ],
        )

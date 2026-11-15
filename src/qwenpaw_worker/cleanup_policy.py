"""Recognize simple cleanup confined to an agent's private directories."""

from pathlib import Path
import re
import shlex


def is_private_cleanup(
    command: str, workspace: Path, scratch: Path | None, cwd: Path | None = None,
) -> bool:
    # qwen-code-bridge injects this literal session binding before every shell
    # tool call. It changes neither the cwd nor the cleanup target expansion.
    command = re.sub(r"^export QWENPAW_SESSION_ID='[^'\r\n]*' && ", "", command, count=1)
    # Compound programs, globbing and arbitrary expansion keep native approval.
    command = command.replace("${TMPDIR}", "$TMPDIR")
    if re.search(r"[;&|()<>`\n\r*?\[\]{}]", command):
        return False
    if "$" in command.replace("$TMPDIR/", ""):
        return False
    try:
        if cwd is not None and not Path(cwd).is_absolute():
            return False
        words = shlex.split(command)
        if not words or words.pop(0) not in {"rm", "/bin/rm", "/usr/bin/rm"}:
            return False
        workspace = workspace.resolve()
        scratch = scratch.resolve() if scratch is not None else None
        base = Path(cwd).resolve() if cwd is not None else workspace
        roots = [workspace] + ([scratch] if scratch is not None else [])
        targets = []
        options = True
        for word in words:
            if options and word == "--":
                options = False
                continue
            if options and word.startswith("-"):
                if not re.fullmatch(r"-[rfRv]+|--recursive|--force|--verbose", word):
                    return False
                continue
            if word.startswith("$TMPDIR/"):
                if scratch is None:
                    return False
                target = scratch / word[len("$TMPDIR/"):]
            else:
                target = Path(word)
                if not target.is_absolute():
                    target = base / target
            target = target.resolve()
            if not any(target != root and target.is_relative_to(root) for root in roots):
                return False
            targets.append(target)
        return bool(targets)
    except (OSError, RuntimeError, ValueError):
        return False

"""Keep QwenPaw's rm approval for unverified targets, allow private cleanup."""

from importlib.metadata import distribution

MARKER = "# AgentTeams: private workspace cleanup is already authorized."
ANCHOR = """    for rule in detection_rules:
        # Check if rule applies to this tool
"""
REPLACEMENT = """    for rule in detection_rules:
        # AgentTeams: private workspace cleanup is already authorized.
        if rule.id == "TOOL_CMD_DANGEROUS_RM" and guard_tool_name == "execute_shell_command":
            from qwenpaw.config.context import get_current_workspace_dir, get_tool_base_dir
            from qwenpaw_worker.cleanup_policy import is_private_cleanup
            workspace = get_current_workspace_dir()
            scratch = os.environ.get("AGENTTEAMS_PRIVATE_TMPDIR")
            params = raw_params or {}
            if workspace is not None and not params.get("sandbox_config") and is_private_cleanup(
                params.get("command", target), Path(workspace),
                Path(scratch) if scratch else None,
                params.get("cwd") or get_tool_base_dir(),
            ):
                continue
        # Check if rule applies to this tool
"""


def apply_patch(source: str) -> str:
    if MARKER in source:
        return source
    if source.count(ANCHOR) != 1:
        raise RuntimeError("Unexpected QwenPaw governance detector; review private cleanup patch")
    return source.replace(ANCHOR, REPLACEMENT)


def main():
    package = distribution("qwenpaw")
    if package.version != "2.2.2.post1":
        raise RuntimeError("Review private cleanup policy for QwenPaw " + package.version)
    path = package.locate_file("qwenpaw/governance/detectors.py")
    source = path.read_text(encoding="utf-8")
    patched = apply_patch(source)
    if patched != source:
        path.write_text(patched, encoding="utf-8")


if __name__ == "__main__":
    main()

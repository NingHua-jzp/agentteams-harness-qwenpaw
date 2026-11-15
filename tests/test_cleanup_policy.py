from pathlib import Path

import pytest

from qwenpaw_worker.cleanup_policy import is_private_cleanup


@pytest.fixture
def roots(tmp_path: Path):
    workspace = tmp_path / "agent" / "workspace"
    scratch = tmp_path / "private-tmp"
    workspace.mkdir(parents=True)
    scratch.mkdir(mode=0o700)
    return workspace, scratch


@pytest.mark.parametrize("command", [
    "rm -rf build/cache", "rm -- 'temporary file.txt'", "/bin/rm -f out.json",
    'rm -rf "$TMPDIR/patchwork" "${TMPDIR}/rehearsal"',
    'rm -f "${TMPDIR:-/tmp}/ut-1900.out"',
    'export QWENPAW_SESSION_ID=\'matrix:!task:test\' && rm -rf "$TMPDIR/rehearsal"',
])
def test_private_cleanup_does_not_need_approval(roots, command):
    assert is_private_cleanup(command, *roots)


def test_absolute_private_paths(roots):
    workspace, scratch = roots
    assert is_private_cleanup(f"rm -rf {workspace}/cache {scratch}/rehearsal", *roots)


@pytest.mark.parametrize("command", [
    "rm -rf /", "rm -rf /tmp", "rm -rf /tmp/patchwork", "rm -rf .", "rm -rf ..",
    "rm -rf ../another-task", "rm -rf /shared/tasks/other", "rm -rf cache /etc/config",
    "rm -rf *", 'rm -rf "$OTHER/cache"', 'rm -rf "$(pwd)/cache"',
    "rm -rf cache; rm -rf /shared", "cd /shared && rm -rf cache", "rm -rf cache\nrm /etc/config",
    "env TMPDIR=/shared rm -rf $TMPDIR/cache", "sudo rm -rf cache", "rm -rf $TMPDIR",
    "rm -rf --interactive=never cache", "echo rm cache", "rm -rf cache > /shared/file",
    'rm -rf "${TMPDIR:-/tmp}/../../public"', 'rm -rf "${TMPDIR:-/shared}/other"',
    "export QWENPAW_SESSION_ID='matrix:!task:test' && rm -rf /shared/tasks/other",
    "export QWENPAW_SESSION_ID='x' && export TMPDIR=/shared && rm -rf $TMPDIR/other",
    "export QWENPAW_SESSION_ID=$(pwd) && rm -rf cache",
])
def test_unverified_or_outside_cleanup_still_requires_approval(roots, command):
    assert not is_private_cleanup(command, *roots)


def test_workspace_symlink_into_shared_directory_is_not_private(roots, tmp_path):
    workspace, _ = roots
    shared = tmp_path / "team-shared"
    shared.mkdir()
    (workspace / "shared").symlink_to(shared, target_is_directory=True)
    assert not is_private_cleanup("rm -rf shared/other-task/cache", *roots)


def test_symlink_inside_scratch_cannot_escape(roots, tmp_path):
    _, scratch = roots
    (scratch / "outside").symlink_to(tmp_path, target_is_directory=True)
    assert not is_private_cleanup('rm -rf "$TMPDIR/outside/public"', *roots)


def test_missing_private_scratch_does_not_grant_tmpdir(roots):
    assert not is_private_cleanup('rm -rf "$TMPDIR/cache"', roots[0], None)
    assert not is_private_cleanup('rm -f "${TMPDIR:-/tmp}/ut-1900.out"', roots[0], None)


def test_relative_paths_use_the_shell_cwd(roots, tmp_path):
    assert not is_private_cleanup("rm -rf cache", *roots, cwd=tmp_path)
    assert not is_private_cleanup("rm -rf cache", *roots, cwd=Path("../shared"))
    assert is_private_cleanup("rm -rf cache", *roots, cwd=roots[0] / "build")


def test_patch_is_idempotent_and_refuses_unknown_native_source():
    import importlib.util
    path = Path(__file__).parents[1] / "scripts/patch-qwenpaw-private-cleanup.py"
    spec = importlib.util.spec_from_file_location("cleanup_patch", path)
    patch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(patch)
    patched = patch.apply_patch(patch.ANCHOR)
    assert patch.apply_patch(patched) == patched
    with pytest.raises(RuntimeError):
        patch.apply_patch("different upstream code")


def test_native_guard_retains_shared_and_catastrophic_checks(roots, monkeypatch):
    import importlib.util
    native = pytest.importorskip("qwenpaw.governance.detectors")
    policy = pytest.importorskip("qwenpaw.governance.policy")
    context = pytest.importorskip("qwenpaw.config.context")
    path = Path(__file__).parents[1] / "scripts/patch-qwenpaw-private-cleanup.py"
    spec = importlib.util.spec_from_file_location("native_cleanup_patch", path)
    patch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(patch)
    namespace = dict(native.__dict__)
    exec(compile(patch.apply_patch(Path(native.__file__).read_text()), native.__file__, "exec"), namespace)
    workspace, scratch = roots
    monkeypatch.setenv("AGENTTEAMS_PRIVATE_TMPDIR", str(scratch))
    monkeypatch.setattr(context, "get_current_workspace_dir", lambda: workspace)
    monkeypatch.setattr(context, "get_tool_base_dir", lambda: workspace)
    def scan(command):
        return namespace["run_deep_scan"](
            tool_name="Bash", target=command, tool_type="shell",
            sensitive_paths=[str(workspace / "sessions") + "/"],
            detection_rules=policy._get_default_detection_rules(),
            shell_evasion_checks={}, raw_params={"command": command},
        )
    assert not scan("rm -rf cache")
    assert not scan('rm -rf "$TMPDIR/cache"')
    assert scan("rm -rf /shared/tasks/other")
    assert scan(f"rm -rf {workspace}/sessions/private.json")
    # A bound Project directory is not private workspace ownership.
    monkeypatch.setattr(context, "get_tool_base_dir", lambda: workspace.parent / "shared-project")
    assert scan("rm -rf cache")
    assert scan("rm -rf /")

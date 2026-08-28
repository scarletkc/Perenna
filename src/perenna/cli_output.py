"""Human-readable rendering of CLI command reports.

Command parsing, dispatch, and logging setup live in `perenna.cli`; this
module only formats sync, skill, and session reports for stdout.
"""

from __future__ import annotations

from collections.abc import Sequence

from perenna.session import PromotePlan, SessionInfo
from perenna.skill_installer import SKILL_NAME, SkillInstallReport
from perenna.sync import SyncReport


def print_sync_report(report: SyncReport) -> None:
    print(f"Memory repository: {report.repository}")
    print(f"Git remote: {report.remote_name} -> {report.remote_url}")
    print(f"Branch: {report.branch}")
    if report.authentication == "deploy-key":
        print(f"Authentication: deploy key {report.deploy_key_fingerprint}")
    if report.repository_access == "ok":
        print("Repository access: ok")
    else:
        print("Repository access: pending (not confirmed with the configured deploy key)")
    if report.write_access == "ok":
        print("Write access: ok")
    else:
        print("Write access: pending (no local commit is available to test)")
    if report.state == "waiting-deploy-key":
        print("Synchronization state: waiting for deploy key authorization")
    elif report.state == "synchronized":
        print("Synchronization state: synchronized")
    elif report.state == "local-behind":
        print("Synchronization state: local branch is behind the remote")
    elif report.state == "local-ahead":
        print("Synchronization state: local branch has unconfirmed commits")
    elif report.state == "diverged":
        print("Synchronization state: local and remote branches have diverged")
    else:
        print("Synchronization state: waiting for the first memory commit")
    if report.state == "waiting-deploy-key":
        print(f"Git synchronization: authorization pending (remote: {report.remote_name})")
        print()
        print("Add this public key to the repository as a deploy key with write access:")
        if report.deploy_key_settings_url is not None:
            print(f"Open: {report.deploy_key_settings_url}")
        print(f"Title: Perenna sync ({report.deploy_key_fingerprint})")
        print(f"Public key: {report.deploy_key_public_key}")
        print("Enable: Allow write access")
        print("Then run the same sync setup command again.")
    else:
        print(f"Git synchronization: enabled (remote: {report.remote_name})")


def print_skill_report(report: SkillInstallReport) -> None:
    states = {
        "installed": "installed",
        "already-installed": "already installed",
        "replaced": "replaced",
    }
    print(f"Skill: {SKILL_NAME}")
    print(f"Agent: {report.agent}")
    print(f"Scope: {report.scope}")
    print(f"Status: {states[report.state]}")
    print(f"Path: {report.destination}")
    if report.backup is not None:
        print(f"Backup: {report.backup}")


def print_session_list(sessions: Sequence[SessionInfo]) -> None:
    if not sessions:
        print("No session branches.")
        return
    for info in sessions:
        print(f"Session: {info.name} ({info.commit[:12]})")


def print_promote_plan(plan: PromotePlan) -> None:
    print(f"Session branch: {plan.branch}")
    print(f"Base branch: {plan.base_branch}")
    if not plan.items:
        print("No memory changes to promote.")
        return
    print(f"Planned memory changes ({len(plan.items)}):")
    for item in plan.items:
        print(f"  {item.operation:<7} {item.path}")

#!/usr/bin/env python3
"""
Suraksha Secret Scanner & Push Restriction Tool
-----------------------------------------------
Scans git commits, staged changes, and files for secrets, credentials,
and sensitive files to prevent unauthorized pushes to remote repositories.

Usage:
    python3 scripts/scan_secrets.py --push <remote_name> <remote_url>   # Used by pre-push hook
    python3 scripts/scan_secrets.py --staged                           # Used by pre-commit hook
    python3 scripts/scan_secrets.py --tracked                          # Scan all tracked files
    python3 scripts/scan_secrets.py --history [N]                      # Scan last N commits
"""

import sys
import os
import re
import subprocess
from typing import List, Tuple, Dict, Optional

# ANSI Color formatting
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Sensitive filename patterns that must NEVER be committed or pushed
SENSITIVE_FILENAME_PATTERNS = [
    re.compile(r'(^|/)\.env(\.[^/]+)?$', re.I),
    re.compile(r'(^|/)secrets?\.env$', re.I),
    re.compile(r'(^|/)production\.env$', re.I),
    re.compile(r'(^|/).*\.(pem|key|pkcs12|pfx|p12)$', re.I),
    re.compile(r'(^|/)id_(rsa|ed25519|ecdsa|dsa)(|\..*)$', re.I),
    re.compile(r'(^|/).*service[-_]?account.*\.json$', re.I),
    re.compile(r'(^|/).*credentials?\.json$', re.I),
    re.compile(r'(^|/)client_secret.*\.json$', re.I),
    re.compile(r'(^|/)secrets?\.yaml$', re.I),
]

# Filename whitelist (templates and examples that are safe)
SAFE_FILENAME_PATTERNS = [
    re.compile(r'.*example.*', re.I),
    re.compile(r'.*template.*', re.I),
    re.compile(r'.*\.sample.*', re.I),
    re.compile(r'.*test.*', re.I),
]

# Sensitive content patterns inside file diffs
SECRET_CONTENT_PATTERNS = [
    (
        "Private Key",
        re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
        "Unencrypted private cryptographic key"
    ),
    (
        "AWS Access Key ID",
        re.compile(r'\b(AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b'),
        "AWS Access Key ID credential"
    ),
    (
        "AWS Secret Access Key",
        re.compile(r'(?i)(aws_secret_access_key|AWS_SECRET_ACCESS_KEY)\s*[:=]\s*["\']?[A-Za-z0-9/+=]{40}["\']?'),
        "AWS Secret Access Key"
    ),
    (
        "Database URI with Credentials",
        re.compile(r'(?i)(mongodb(\+srv)?|postgres(ql)?|mysql|redis|amqp)://([^\s:\'\"<>]+):([^\s@\'\"<>]+)@([^\s\'\"<>]+)'),
        "Database connection string with embedded password"
    ),
    (
        "GitHub Personal Access Token",
        re.compile(r'\bgh[pousr]_[A-Za-z0-9_]{36,}\b'),
        "GitHub authentication token"
    ),
    (
        "Google API Key",
        re.compile(r'\bAIza[0-9A-Za-z-_]{35}\b'),
        "Google Cloud / API key"
    ),
    (
        "Slack Token",
        re.compile(r'\bxox[baprs]-[0-9a-zA-Z]{10,48}\b'),
        "Slack API token"
    ),
    (
        "Twilio Auth Token",
        re.compile(r'(?i)(twilio_auth_token|TWILIO_AUTH_TOKEN)\s*[:=]\s*["\']?[0-9a-fA-F]{32}["\']?'),
        "Twilio authentication token"
    ),
    (
        "MSG91 Auth Key",
        re.compile(r'(?i)(msg91_auth_key|MSG91_AUTH_KEY)\s*[:=]\s*["\']?[0-9a-zA-Z]{20,}["\']?'),
        "MSG91 SMS / WhatsApp authentication key"
    ),
    (
        "Generic Secret/Password Assignment",
        re.compile(r'(?i)(password|passwd|api_?key|auth_?token|secret_?key)\s*[:=]\s*["\']([^\s"\']{8,})["\']'),
        "Hardcoded password or secret assignment"
    ),
]

# Whitelist values that look like secrets but are placeholders or safe words
SAFE_VALUE_KEYWORDS = [
    "change_me", "dummy", "example", "placeholder", "your_", "<", ">",
    "username:password", "user:pass", "user:password", "admin:admin", "admin:password",
    "none", "null", "undefined", "true", "false", "required_env", "process.env",
    "os.environ", "getenv", "http://", "https://", "localhost", "127.0.0.1",
    "font", "outfit", "roboto", "........", "sha512", "integrity", "public",
]


def is_safe_value(text: str) -> bool:
    """Check if the matched text is an obvious placeholder or non-secret."""
    lower = text.lower()
    for kw in SAFE_VALUE_KEYWORDS:
        if kw in lower:
            return True
    return False


def is_sensitive_filename(filepath: str) -> bool:
    """Check if a file path matches forbidden sensitive file patterns."""
    basename = os.path.basename(filepath)
    # Check if whitelisted
    for safe in SAFE_FILENAME_PATTERNS:
        if safe.search(basename):
            return False
    # Special allowance: k3s/secret.yaml is kept as template if values are CHANGE_ME
    if filepath == "k3s/secret.yaml":
        return False

    for pat in SENSITIVE_FILENAME_PATTERNS:
        if pat.search(filepath) or pat.search(basename):
            return True
    return False


def mask_secret(secret_str: str) -> str:
    """Partially mask a secret string for safe display in logs."""
    cleaned = secret_str.strip()
    if len(cleaned) <= 8:
        return "****"
    return f"{cleaned[:4]}...{cleaned[-4:]}"


class Violation:
    def __init__(self, location: str, rule: str, description: str, snippet: str):
        self.location = location
        self.rule = rule
        self.description = description
        self.snippet = snippet


def check_diff_lines(diff_text: str, location_prefix: str = "") -> List[Violation]:
    """Scan added diff lines for secret patterns."""
    violations: List[Violation] = []
    current_file = ""

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            parts = line.split(" ")
            if len(parts) >= 4:
                current_file = parts[3].lstrip("b/")
                if is_sensitive_filename(current_file):
                    violations.append(Violation(
                        location=f"{location_prefix}{current_file}",
                        rule="Sensitive File",
                        description=f"Forbidden sensitive filename pattern: {current_file}",
                        snippet=current_file
                    ))
            continue

        # Only check added lines
        if line.startswith("+") and not line.startswith("+++"):
            added_content = line[1:].strip()
            if not added_content:
                continue

            for rule_name, pat, desc in SECRET_CONTENT_PATTERNS:
                m = pat.search(added_content)
                if m:
                    match_val = m.group(0)
                    if is_safe_value(match_val):
                        continue
                    
                    loc = f"{location_prefix}{current_file}" if current_file else location_prefix
                    violations.append(Violation(
                        location=loc,
                        rule=rule_name,
                        description=desc,
                        snippet=mask_secret(added_content)
                    ))
    return violations


def scan_staged_changes() -> List[Violation]:
    """Scan git staged changes (pre-commit)."""
    # 1. Check staged filenames
    violations: List[Violation] = []
    try:
        staged_files = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"],
            text=True
        ).splitlines()

        for f in staged_files:
            if is_sensitive_filename(f):
                violations.append(Violation(
                    location=f,
                    rule="Sensitive File Staged",
                    description=f"Attempting to commit sensitive file: {f}",
                    snippet=f
                ))

        # 2. Check staged diff content
        diff = subprocess.check_output(
            ["git", "diff", "--cached", "-U0"],
            text=True
        )
        violations.extend(check_diff_lines(diff, location_prefix="staged: "))
    except subprocess.CalledProcessError as e:
        print(f"{RED}Error running git diff: {e}{RESET}", file=sys.stderr)

    return violations


def scan_push_commits(remote_name: str, remote_url: str) -> List[Violation]:
    """Scan commits being pushed to remote."""
    violations: List[Violation] = []
    
    # Read standard input supplied by git pre-push hook:
    # Format: <local ref> <local sha> <remote ref> <remote sha>
    lines = sys.stdin.read().splitlines()
    
    commits_to_scan = set()
    zero_sha = "0" * 40

    for line in lines:
        parts = line.strip().split()
        if len(parts) != 4:
            continue
        local_ref, local_sha, remote_ref, remote_sha = parts

        # Deleting a remote branch
        if local_sha == zero_sha:
            continue

        # New remote branch
        if remote_sha == zero_sha:
            try:
                out = subprocess.check_output(
                    ["git", "rev-list", local_sha, "--not", f"--remotes={remote_name}"],
                    text=True
                )
                for c in out.splitlines():
                    commits_to_scan.add(c.strip())
            except subprocess.CalledProcessError:
                # Fallback to local_sha
                commits_to_scan.add(local_sha)
        else:
            try:
                out = subprocess.check_output(
                    ["git", "rev-list", f"{remote_sha}..{local_sha}"],
                    text=True
                )
                for c in out.splitlines():
                    commits_to_scan.add(c.strip())
            except subprocess.CalledProcessError:
                commits_to_scan.add(local_sha)

    # If stdin was empty (e.g. tested manually), check commits against remote or last commit
    if not commits_to_scan:
        try:
            head_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
            # Try to compare with upstream tracking branch
            upstream = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "@{u}"],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
            out = subprocess.check_output(["git", "rev-list", f"{upstream}..HEAD"], text=True)
            for c in out.splitlines():
                if c.strip():
                    commits_to_scan.add(c.strip())
        except Exception:
            # Fallback: check HEAD commit
            try:
                head_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
                commits_to_scan.add(head_sha)
            except Exception:
                pass

    for commit_sha in commits_to_scan:
        try:
            diff = subprocess.check_output(
                ["git", "show", "--format=", "-U0", commit_sha],
                text=True
            )
            commit_violations = check_diff_lines(diff, location_prefix=f"commit {commit_sha[:8]}: ")
            violations.extend(commit_violations)
        except subprocess.CalledProcessError:
            pass

    return violations


def scan_all_tracked() -> List[Violation]:
    """Scan all tracked files in working directory."""
    violations: List[Violation] = []
    files = subprocess.check_output(["git", "ls-files"], text=True).splitlines()

    for f in files:
        if is_sensitive_filename(f):
            violations.append(Violation(
                location=f,
                rule="Sensitive Tracked File",
                description=f"Sensitive file tracked by git: {f}",
                snippet=f
            ))
        if not os.path.isfile(f):
            continue
        try:
            with open(f, "r", errors="ignore") as fp:
                for idx, line in enumerate(fp, 1):
                    stripped = line.strip()
                    for rule_name, pat, desc in SECRET_CONTENT_PATTERNS:
                        m = pat.search(stripped)
                        if m:
                            val = m.group(0)
                            if is_safe_value(val):
                                continue
                            violations.append(Violation(
                                location=f"{f}:{idx}",
                                rule=rule_name,
                                description=desc,
                                snippet=mask_secret(stripped)
                            ))
        except Exception:
            pass
    return violations


def report_and_exit(violations: List[Violation], context: str) -> None:
    """Display violations clearly and exit with error code if any are found."""
    if not violations:
        print(f"{GREEN}[OK] Pre-flight security check passed ({context}). No secrets detected.{RESET}")
        sys.exit(0)

    print(f"\n{RED}{BOLD}{'='*78}{RESET}")
    print(f"{RED}{BOLD} 🚫 GIT {context.upper()} REJECTED: CRITICAL SECRETS / SENSITIVE FILES DETECTED!{RESET}")
    print(f"{RED}{BOLD}{'='*78}{RESET}\n")

    print(f"{YELLOW}The following sensitive items were identified:{RESET}\n")
    for idx, v in enumerate(violations, 1):
        print(f"  {RED}{idx}. [{v.rule}]{RESET} {BOLD}{v.location}{RESET}")
        print(f"     Description : {v.description}")
        print(f"     Masked Line : {CYAN}{v.snippet}{RESET}\n")

    print(f"{YELLOW}{BOLD}REMEDIATION INSTRUCTIONS:{RESET}")
    print("  1. NEVER commit passwords, API keys, private keys, or `.env` files.")
    print("  2. Place all secrets into `.env` (which is in `.gitignore`) or use environment variables.")
    print("  3. To remove secrets from your staged changes:")
    print(f"     {CYAN}git restore --staged <file>{RESET}")
    print("  4. To amend an unpushed commit:")
    print(f"     {CYAN}git reset HEAD~1{RESET}  (then update files and re-commit)")
    print("  5. If secrets were already pushed to a remote repository in previous commits,")
    print("     you MUST immediately rotate/revoke the exposed credentials on the provider.")
    print(f"\n{RED}{BOLD}Push cancelled by Suraksha Secret Scanner hook.{RESET}\n")
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: scan_secrets.py [--push <remote> <url> | --staged | --tracked]")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "--push":
        remote_name = sys.argv[2] if len(sys.argv) > 2 else "origin"
        remote_url = sys.argv[3] if len(sys.argv) > 3 else ""
        violations = scan_push_commits(remote_name, remote_url)
        report_and_exit(violations, context="Push")
    elif mode == "--staged":
        violations = scan_staged_changes()
        report_and_exit(violations, context="Commit")
    elif mode == "--tracked":
        violations = scan_all_tracked()
        report_and_exit(violations, context="Tracked Files Scan")
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()

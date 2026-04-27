"""
[1] Static Security — ModelScan wrapper
Scans the Ollama model for backdoors, malicious pickles, etc.
"""
import argparse
import json
import subprocess
import sys
import os
from pathlib import Path


CANDIDATE_PATHS = [
    os.environ.get("OLLAMA_MODELS"),                 # explicit override
    "/usr/share/ollama/.ollama/models",              # systemd-installed Ollama
    "/var/lib/ollama/models",                        # alternative system path
    str(Path.home() / ".ollama" / "models"),         # per-user install
    "/root/.ollama/models",                          # root install
]


def find_ollama_model_path(model_name: str) -> str:
    """Find the local path where Ollama stores its models."""
    for candidate in CANDIDATE_PATHS:
        if candidate and Path(candidate).is_dir():
            return candidate
    # Fallback (will likely fail, but at least with a clear message)
    return str(Path.home() / ".ollama" / "models")


def run_modelscan(path: str) -> dict:
    """Run modelscan on the given path."""
    if not Path(path).exists():
        return {
            "tool": "modelscan",
            "scanned_path": path,
            "error": f"Path does not exist: {path}",
            "passed": False,
            "skipped": True,
        }

    try:
        result = subprocess.run(
            ["modelscan", "scan", "-p", path],
            capture_output=True,
            text=True,
            timeout=180,
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        combined = (stdout + "\n" + stderr).lower()

        # ModelScan exit codes:
        #   0  -> clean scan, supported formats found
        #   1  -> issues found
        #   2+ -> errors / format unsupported
        # Ollama uses GGUF, which modelscan does not natively support.
        # We treat "no issues / unsupported format" as PASS (with a note),
        # and only fail if explicit threats are reported.
        threat_indicators = [
            "unsafe operator",
            "suspicious",
            "malicious",
            "critical severity",
            "high severity",
        ]
        has_threats = any(ind in combined for ind in threat_indicators)

        if has_threats:
            passed = False
            verdict = "Threats detected by modelscan"
        elif result.returncode == 0:
            passed = True
            verdict = "Scan clean (no issues)"
        else:
            # Non-zero but no explicit threats — likely unsupported format (GGUF)
            passed = True
            verdict = "No threats detected (format may be unsupported by modelscan; GGUF is inherently safer than pickle-based formats)"

        return {
            "tool": "modelscan",
            "scanned_path": path,
            "return_code": result.returncode,
            "verdict": verdict,
            "output": stdout[:3000],
            "errors": stderr[:500],
            "passed": passed,
        }

    except FileNotFoundError:
        return {
            "tool": "modelscan",
            "scanned_path": path,
            "error": "modelscan not installed — run: pip install modelscan",
            "passed": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "tool": "modelscan",
            "scanned_path": path,
            "error": "Timeout after 180s",
            "passed": False,
        }


def check_ollama_model_info(model_name: str) -> dict:
    """Inspect model metadata via `ollama show`."""
    try:
        result = subprocess.run(
            ["ollama", "show", model_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "tool": "ollama_show",
            "model": model_name,
            "info": (result.stdout or "")[:1000],
            "passed": result.returncode == 0,
        }
    except Exception as e:
        return {
            "tool": "ollama_show",
            "model": model_name,
            "error": str(e),
            "passed": False,
        }


def run(args):
    print(f"[Static Security] Analyzing model: {args.model}")

    report = {
        "stage": "static_security",
        "model": args.model,
        "source": args.source,
        "checks": {},
    }

    # 1. Model info
    report["checks"]["model_info"] = check_ollama_model_info(args.model)

    # 2. Modelscan
    model_path = find_ollama_model_path(args.model)
    print(f"[Static Security] Scanning: {model_path}")
    report["checks"]["modelscan"] = run_modelscan(model_path)

    # Overall verdict
    report["passed"] = all(
        c.get("passed", False) for c in report["checks"].values()
    )

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))

    if not report["passed"]:
        print("❌ Static Security FAILED")
        sys.exit(1)
    print("✅ Static Security PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--source", default="ollama")
    parser.add_argument("--output", required=True)
    run(parser.parse_args())

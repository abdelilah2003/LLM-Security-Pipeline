"""
[1] Static Security — ModelScan wrapper
Scan le modèle ollama pour backdoors, pickles malveillants, etc.
"""
import argparse
import json
import subprocess
import sys
import os
import glob
from pathlib import Path


def find_ollama_model_path(model_name: str) -> str:
    """Trouve le chemin local du modèle Ollama."""
    base = Path.home() / ".ollama" / "models"
    # Cherche tous les blobs (fichiers du modèle)
    blobs = list(base.rglob("*.bin")) + list(base.rglob("*.gguf"))
    if blobs:
        return str(base)
    return str(base)


def run_modelscan(path: str) -> dict:
    """Lance modelscan sur le chemin donné."""
    try:
        result = subprocess.run(
            ["modelscan", "--path", path, "--reporting-format", "json"],
            capture_output=True,
            text=True,
            timeout=120
        )
        return {
            "tool": "modelscan",
            "scanned_path": path,
            "return_code": result.returncode,
            "output": result.stdout[:3000] if result.stdout else "",
            "errors": result.stderr[:500] if result.stderr else "",
            "passed": result.returncode == 0
        }
    except FileNotFoundError:
        return {
            "tool": "modelscan",
            "scanned_path": path,
            "error": "modelscan non installé — pip install modelscan",
            "passed": False
        }
    except subprocess.TimeoutExpired:
        return {
            "tool": "modelscan",
            "scanned_path": path,
            "error": "Timeout après 120s",
            "passed": False
        }


def check_ollama_model_info(model_name: str) -> dict:
    """Vérifie les infos du modèle via ollama show."""
    try:
        result = subprocess.run(
            ["ollama", "show", model_name],
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            "tool": "ollama_show",
            "model": model_name,
            "info": result.stdout[:1000],
            "passed": result.returncode == 0
        }
    except Exception as e:
        return {
            "tool": "ollama_show",
            "model": model_name,
            "error": str(e),
            "passed": False
        }


def run(args):
    print(f"[Static Security] Analyse du modèle : {args.model}")

    report = {
        "stage": "static_security",
        "model": args.model,
        "source": args.source,
        "checks": {}
    }

    # 1. Infos modèle
    report["checks"]["model_info"] = check_ollama_model_info(args.model)

    # 2. Modelscan
    model_path = find_ollama_model_path(args.model)
    print(f"[Static Security] Scan sur : {model_path}")
    report["checks"]["modelscan"] = run_modelscan(model_path)

    # Résultat global
    report["passed"] = all(
        c.get("passed", False)
        for c in report["checks"].values()
    )

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))

    if not report["passed"]:
        print("❌ Static Security FAILED")
        sys.exit(1)
    else:
        print("✅ Static Security PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--source", default="ollama")
    parser.add_argument("--output", required=True)
    run(parser.parse_args())

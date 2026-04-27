"""
[2] Quality Benchmark
Tests de qualité sur tinyllama via Ollama :
- Cohérence des réponses
- Suivi d'instructions
- Raisonnement basique
- Score global
"""
import argparse
import json
import sys
import os
import requests
from datetime import datetime


OLLAMA_URL = "http://localhost:11434/api/generate"


def query_ollama(model: str, prompt: str, timeout: int = 60) -> str:
    """Envoie un prompt à Ollama et retourne la réponse."""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0, "num_predict": 150}
            },
            timeout=timeout
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        return f"ERROR: {e}"


# ── Définition des tests de qualité ──────────────────────────────────────────

QUALITY_TESTS = [

    # Suivi d'instructions simples
    {
        "id": "Q1",
        "category": "instruction_following",
        "prompt": "Réponds uniquement par 'OUI' ou 'NON'. Est-ce que Paris est la capitale de la France ?",
        "check": lambda r: "OUI" in r.upper(),
        "description": "Réponse factuelle simple OUI/NON"
    },
    {
        "id": "Q2",
        "category": "instruction_following",
        "prompt": "Compte de 1 à 5, un chiffre par ligne.",
        "check": lambda r: all(str(i) in r for i in range(1, 6)),
        "description": "Comptage ordonné"
    },

    # Raisonnement basique
    {
        "id": "Q3",
        "category": "reasoning",
        "prompt": "Si j'ai 3 pommes et j'en mange 1, combien en reste-t-il ? Réponds avec juste le chiffre.",
        "check": lambda r: "2" in r,
        "description": "Arithmétique simple"
    },
    {
        "id": "Q4",
        "category": "reasoning",
        "prompt": "Quel est le résultat de 10 + 15 ? Réponds avec juste le nombre.",
        "check": lambda r: "25" in r,
        "description": "Addition"
    },

    # Cohérence des réponses
    {
        "id": "Q5",
        "category": "coherence",
        "prompt": "Traduis ce mot en anglais : 'chien'. Réponds avec juste le mot traduit.",
        "check": lambda r: "dog" in r.lower(),
        "description": "Traduction simple"
    },
    {
        "id": "Q6",
        "category": "coherence",
        "prompt": "Quel est le contraire de 'grand' ? Réponds avec un seul mot.",
        "check": lambda r: any(w in r.lower() for w in ["petit", "petite", "small"]),
        "description": "Antonyme"
    },

    # Compréhension
    {
        "id": "Q7",
        "category": "comprehension",
        "prompt": "Lis ce texte et réponds : 'Le ciel est bleu. La mer est aussi bleue.' De quelle couleur est le ciel ?",
        "check": lambda r: "bleu" in r.lower() or "blue" in r.lower(),
        "description": "Compréhension de texte"
    },
    {
        "id": "Q8",
        "category": "comprehension",
        "prompt": "Complète cette phrase avec un seul mot : 'Le soleil se lève à l'___'.",
        "check": lambda r: any(w in r.lower() for w in ["est", "matin", "aube", "levant"]),
        "description": "Complétion de phrase"
    },
]


def run(args):
    print(f"[Quality Benchmark] Modèle : {args.model}")

    results = []
    categories = {}

    for test in QUALITY_TESTS:
        print(f"  ▶ {test['id']} — {test['description']}")
        response = query_ollama(args.model, test["prompt"])
        passed = False

        if not response.startswith("ERROR"):
            try:
                passed = test["check"](response)
            except Exception:
                passed = False

        result = {
            "id": test["id"],
            "category": test["category"],
            "description": test["description"],
            "prompt": test["prompt"],
            "response": response[:300],
            "passed": passed
        }
        results.append(result)
        status = "✅" if passed else "❌"
        print(f"     {status} Réponse : {response[:80]}")

        # Stats par catégorie
        cat = test["category"]
        if cat not in categories:
            categories[cat] = {"passed": 0, "total": 0}
        categories[cat]["total"] += 1
        if passed:
            categories[cat]["passed"] += 1

    # Score global
    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    score = passed_count / total if total > 0 else 0

    # Score par catégorie
    cat_scores = {
        cat: round(v["passed"] / v["total"], 2)
        for cat, v in categories.items()
    }

    THRESHOLD = 0.5  # 50% minimum pour tinyllama (modèle très petit)

    report = {
        "stage": "quality_benchmark",
        "model": args.model,
        "timestamp": datetime.now().isoformat(),
        "total_tests": total,
        "passed_tests": passed_count,
        "score": round(score, 2),
        "threshold": THRESHOLD,
        "category_scores": cat_scores,
        "passed": score >= THRESHOLD,
        "details": results
    }

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n[Quality] Score : {passed_count}/{total} ({score*100:.0f}%) — seuil : {THRESHOLD*100:.0f}%")

    if not report["passed"]:
        print("❌ Quality Benchmark FAILED")
        sys.exit(1)
    else:
        print("✅ Quality Benchmark PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--source", default="ollama")
    parser.add_argument("--output", required=True)
    run(parser.parse_args())

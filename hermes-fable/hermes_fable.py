"""
Hermes ⨉ Fable 5 — boucle d'agent calquée sur la logique de Fable 5.

Dépose ce fichier dans Hermes sur ton VPS. Il appelle Claude Fable 5 via l'API
authentifiée (clé ANTHROPIC_API_KEY ou profil `ant auth login`).

Points clés spécifiques à Fable 5 :
  - thinking TOUJOURS actif → on n'envoie AUCUN paramètre `thinking`
  - pas de temperature/top_p/top_k (rejetés par l'API → 400)
  - on pilote la profondeur via output_config.effort ("low".."max")
  - on gère stop_reason == "refusal" avec un fallback serveur vers Opus 4.8
  - on streame (les tours Fable 5 peuvent durer plusieurs minutes)
  - Fable 5 exige une rétention de données 30 jours (pas de ZDR)

Installation :  pip install anthropic
"""

import os
import json
import subprocess
from pathlib import Path

import anthropic

# Client zéro-arg : récupère ANTHROPIC_API_KEY, sinon le profil `ant auth login`.
client = anthropic.Anthropic()

MODEL = "claude-fable-5"
FALLBACK = "claude-opus-4-8"          # modèle de secours si Fable 5 refuse
EFFORT = "high"                        # "low" | "medium" | "high" | "xhigh" | "max"

SYSTEM_PROMPT = Path(__file__).with_name("fable_system_prompt.txt").read_text()

# --- Outils exposés à l'agent (adapte à ce dont Hermes a besoin) ----------------
TOOLS = [
    {
        "name": "run_bash",
        "description": "Exécute une commande shell et renvoie stdout+stderr. "
                       "Utilise-le pour lancer les tests, vérifier les fichiers, exécuter le code.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    # Recherche web côté serveur (gérée par Anthropic, pas de code client à écrire)
    {"type": "web_search_20260209", "name": "web_search"},
]


def execute_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Exécute un outil client. Renvoie (contenu, is_error)."""
    if name == "run_bash":
        try:
            out = subprocess.run(
                tool_input["command"], shell=True, capture_output=True,
                text=True, timeout=300,
            )
            body = (out.stdout or "") + (out.stderr or "")
            return body or "(aucune sortie)", out.returncode != 0
        except subprocess.TimeoutExpired:
            return "Erreur : commande expirée (300 s).", True
    return f"Outil inconnu : {name}", True


def run_agent(user_message: str, max_turns: int = 50) -> str:
    """Boucle agentique : cadre → délègue → construit → auto-teste → boucle."""
    messages = [{"role": "user", "content": user_message}]

    for _ in range(max_turns):
        # client.beta + betas[...] : nécessaire pour le fallback serveur en cas de refus
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=64000,                       # streaming → marge confortable
            system=SYSTEM_PROMPT,
            output_config={"effort": EFFORT},       # PAS de `thinking` : auto sur Fable 5
            betas=["server-side-fallback-2026-06-01"],
            fallbacks=[{"model": FALLBACK}],        # refus Fable 5 → rejoué sur Opus 4.8
            tools=TOOLS,
            messages=messages,
        ) as stream:
            response = stream.get_final_message()

        # Refus de bout en bout (Fable 5 ET le fallback ont décliné)
        if response.stop_reason == "refusal":
            cat = response.stop_details.category if response.stop_details else None
            return f"[Requête déclinée par les classifieurs de sécurité — catégorie : {cat}]"

        # Tour terminé : plus d'appel d'outil
        if response.stop_reason == "end_turn":
            return next((b.text for b in response.content if b.type == "text"), "")

        # Reprise serveur (outils serveur ayant atteint leur limite d'itérations)
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue

        # stop_reason == "tool_use" : exécute les outils client puis renvoie les résultats
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type == "tool_use" and block.name == "run_bash":
                content, is_error = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                    "is_error": is_error,
                })
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    return "[Limite de tours atteinte sans achèvement.]"


if __name__ == "__main__":
    import sys
    prompt = " ".join(sys.argv[1:]) or "Décris ta procédure de travail."
    print(run_agent(prompt))

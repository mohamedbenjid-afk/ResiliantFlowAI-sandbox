# llm_client.py
# Couche d'abstraction LLM : supporte 1min.ai OU Anthropic selon la config
#
# Secrets Streamlit à configurer :
#
#   ── Option A : 1min.ai ──────────────────────────────────────────────────
#   LLM_PROVIDER = "1minai"
#   ONEMINAI_KEY = "votre-clé-1min.ai"
#   ONEMINAI_MODEL = "claude-opus-4-5"   # optionnel, défaut ci-dessous
#
#   ── Option B : Anthropic direct ─────────────────────────────────────────
#   LLM_PROVIDER = "anthropic"
#   ANTHROPIC_API_KEY = "sk-ant-xxxxxxxxxxxx"

import json
import requests


def _get_secret(key: str, default: str = "") -> str:
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        import os
        return os.environ.get(key, default)


def _provider() -> str:
    return _get_secret("LLM_PROVIDER", "1minai")


# Modèles par défaut
DEFAULT_MODEL_1MINAI    = "claude-opus-4-7"
DEFAULT_MODEL_ANTHROPIC = "claude-opus-4-7"


# ─────────────────────────────────────────────────────────────────────────────
# PROVIDER 1min.ai  (non-streaming, format officiel)
# Doc : https://docs.1min.ai/docs/api/chat-with-ai-api
# ─────────────────────────────────────────────────────────────────────────────

def _tools_to_system_addon(tools: list) -> str:
    """
    1min.ai ne supporte pas le tool_use natif.
    On injecte les outils dans le system prompt et on demande à l'agent
    de répondre en JSON quand il veut appeler un outil.
    """
    lines = [
        "\n\n---",
        "Tu as accès aux outils suivants.",
        "Pour appeler un outil, réponds UNIQUEMENT avec ce JSON (rien d'autre) :",
        '{"tool_call": {"name": "NOM_OUTIL", "arguments": {<paramètres>}}}',
        "Quand ta réponse est finale (sans appel d'outil), réponds normalement en texte.",
        "",
        "OUTILS DISPONIBLES :",
    ]
    for t in tools:
        props = t.get("input_schema", {}).get("properties", {})
        params = ", ".join(
            f"{k} ({v.get('type', 'string')}): {v.get('description', '')}"
            for k, v in props.items()
        )
        lines.append(f"\n• {t['name']}({params})\n  → {t['description']}")
    lines.append("---")
    return "\n".join(lines)


def _build_prompt_from_messages(messages: list) -> str:
    """Reconstitue un prompt texte à partir de l'historique des messages."""
    parts = []
    for msg in messages:
        role = "Utilisateur" if msg["role"] == "user" else "Assistant"
        content = msg["content"]

        if isinstance(content, str):
            parts.append(f"{role}: {content}")
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")
                if btype == "text":
                    parts.append(f"{role}: {block['text']}")
                elif btype == "tool_use":
                    parts.append(
                        f"[Appel outil] {block.get('name')}: "
                        f"{json.dumps(block.get('input', {}), ensure_ascii=False)}"
                    )
                elif btype == "tool_result":
                    parts.append(f"[Résultat outil]: {block.get('content', '')}")
    return "\n\n".join(parts)


def _call_1minai(system: str, messages: list, tools: list = None) -> dict:
    """
    Appelle l'API 1min.ai (non-streaming) et retourne un dict normalisé.
    Format officiel : POST https://api.1min.ai/api/chat-with-ai
    Header : API-KEY (pas Bearer)
    """
    api_key = _get_secret("ONEMINAI_KEY")
    model   = _get_secret("ONEMINAI_MODEL", DEFAULT_MODEL_1MINAI)

    # System prompt complet (+ description des outils si besoin)
    system_full = system
    if tools:
        system_full += _tools_to_system_addon(tools)

    # Reconstituer tout l'historique en un seul prompt
    # (1min.ai gère l'historique via conversationId — ici on l'injecte en texte)
    prompt = _build_prompt_from_messages(messages)

    payload = {
        "type":  "UNIFY_CHAT_WITH_AI",
        "model": model,
        "promptObject": {
            "prompt": prompt,
            "settings": {
                "historySettings": {
                    "isMixed": False,
                    "historyMessageLimit": 20
                }
            }
        }
    }

    # Ajout du system prompt via le bon champ
    # D'après la doc, on le glisse dans le prompt avec un préfixe
    payload["promptObject"]["prompt"] = (
        f"[Instructions système]\n{system_full}\n\n"
        f"[Conversation]\n{prompt}"
    )

    resp = requests.post(
        "https://api.1min.ai/api/chat-with-ai",
        headers={
            "API-KEY":      api_key,
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=90
    )

    # Logguer l'erreur HTTP avant de planter
    if not resp.ok:
        error_body = ""
        try:
            error_body = resp.json()
        except Exception:
            error_body = resp.text[:500]
        raise RuntimeError(
            f"1min.ai API error {resp.status_code}: {error_body}"
        )

    data = resp.json()

    # ── Extraire le texte de la réponse (format non-streaming) ───────────────
    # La réponse peut venir dans plusieurs formats selon la version de l'API
    raw_text = ""

    # Format v2 (nouveau)
    if "aiRecord" in data:
        raw_text = (
            data.get("aiRecord", {})
                .get("aiRecordDetail", {})
                .get("resultObject", [""])[0]
            or ""
        )
    # Format alternatif observé
    elif "result" in data:
        raw_text = data["result"] or ""
    elif "message" in data:
        raw_text = data["message"] or ""
    elif "choices" in data:
        # Format OpenAI-compatible
        raw_text = data["choices"][0]["message"]["content"] or ""
    else:
        # Fallback : dump du JSON pour debug
        raw_text = json.dumps(data, ensure_ascii=False)

    raw_stripped = raw_text.strip()

    # Détecter un appel d'outil JSON
    if raw_stripped.startswith("{") and "tool_call" in raw_stripped:
        try:
            # Extraire le JSON même si du texte parasite l'entoure
            json_start = raw_stripped.index("{")
            json_end   = raw_stripped.rindex("}") + 1
            parsed    = json.loads(raw_stripped[json_start:json_end])
            tool_call = parsed.get("tool_call", {})
            if tool_call.get("name"):
                return {
                    "stop_reason": "tool_use",
                    "content": [{
                        "type":  "tool_use",
                        "id":    "tc_1minai_0",
                        "name":  tool_call["name"],
                        "input": tool_call.get("arguments", {}),
                    }]
                }
        except (json.JSONDecodeError, ValueError):
            pass

    return {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": raw_text}]
    }


# ─────────────────────────────────────────────────────────────────────────────
# PROVIDER Anthropic
# ─────────────────────────────────────────────────────────────────────────────

def _call_anthropic(system: str, messages: list, tools: list = None,
                    max_tokens: int = 2000) -> dict:
    import anthropic as _anthropic
    client = _anthropic.Anthropic(api_key=_get_secret("ANTHROPIC_API_KEY"))
    kwargs = dict(
        model=DEFAULT_MODEL_ANTHROPIC,
        max_tokens=max_tokens,
        system=system,
        messages=messages
    )
    if tools:
        kwargs["tools"] = tools
    resp = client.messages.create(**kwargs)
    return {
        "stop_reason": resp.stop_reason,
        "content": [
            {
                "type":  b.type,
                "text":  getattr(b, "text",  None),
                "id":    getattr(b, "id",    None),
                "name":  getattr(b, "name",  None),
                "input": getattr(b, "input", None),
            }
            for b in resp.content
        ]
    }


# ─────────────────────────────────────────────────────────────────────────────
# INTERFACE PUBLIQUE
# ─────────────────────────────────────────────────────────────────────────────

class LLMResponse:
    def __init__(self, raw: dict):
        self._raw = raw

    @property
    def stop_reason(self) -> str:
        return self._raw.get("stop_reason", "end_turn")

    @property
    def content(self) -> list:
        return self._raw.get("content", [])

    def final_text(self) -> str:
        return "".join(
            (b.get("text") or "")
            for b in self.content
            if b.get("type") == "text"
        )

    def tool_calls(self) -> list:
        return [b for b in self.content if b.get("type") == "tool_use"]


def chat(system: str, messages: list, tools: list = None,
         max_tokens: int = 2000) -> LLMResponse:
    """
    Point d'entrée unique pour tous les agents.
    Lit LLM_PROVIDER depuis les secrets Streamlit.

    Usage :
        from llm_client import chat
        resp = chat(system=SYSTEM, messages=messages, tools=TOOLS)
        if resp.stop_reason == "tool_use":
            for tc in resp.tool_calls():
                result = execute_tool(tc["name"], tc["input"])
    """
    provider = _provider()
    if provider == "anthropic":
        raw = _call_anthropic(system, messages, tools, max_tokens)
    else:
        raw = _call_1minai(system, messages, tools)
    return LLMResponse(raw)

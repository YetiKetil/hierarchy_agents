"""
Language-model providers (English, so that students can extend it).

Everything that talks to a language model lives in this file. The rest of the program
only knows two methods, which every provider implements:

    act(system, prompt, tool)  -> (action: dict, info: dict)
        The agent's turn. The model must answer by calling `tool`, a JSON-schema tool
        definition {"name", "description", "input_schema"}. Return the tool arguments.

    reply(system, prompt)      -> (text: str, info: dict)
        Free text. Used for the debrief after the game.

`info` reports usage with these keys (the names are Norwegian, as in the rest of the code):
    "modell" model name, "inn" input tokens, "ut" output tokens, "kall" number of API calls,
    "avkuttet" answers cut off by the token limit, "stopp" stop reason, "tekst" any free text
    the model wrote, "feil" error message or None.

Adding a provider (OpenAI, a local model, ...):
    1. Write a class with `act` and `reply` like the two below.
    2. Add it to PROVIDERS at the bottom, and to guess_provider() if its model names are recognisable.
    3. Use it with `leverandor: <name>` in a condition file, or `--provider <name>` on the command line.
"""
import os
import random
import time
from pathlib import Path


def _info(model):
    return {"modell": model, "inn": 0, "ut": 0, "kall": 0, "avkuttet": 0, "stopp": None, "tekst": "", "feil": None}


def _transient(e):
    """Errors worth retrying: rate limits, overload, timeouts."""
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    text = str(e).lower()
    return code in (408, 429, 500, 502, 503, 504) or any(
        s in text for s in ("rate", "quota", "overloaded", "unavailable", "timeout", "429", "503"))


def _with_retry(fn, attempts=6):
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            if i == attempts - 1 or not _transient(e):
                raise
            time.sleep(min(60, 2 ** i + random.random()))


_warned = set()


def clean_key(names):
    """Returns the first key found under `names`, without spaces or line breaks.

    A key pasted twice, or with a line break, would otherwise make every request fail with
    "Illegal header value". If the value has several lines, the first non-empty line is used."""
    for name in names:
        raw = os.environ.get(name)
        if raw:
            lines = [l.strip() for l in raw.replace("\r", "\n").split("\n") if l.strip()]
            if not lines:
                continue
            key = lines[0].strip().strip('"').strip("'")
            if (len(lines) > 1 or raw != raw.strip()) and name not in _warned:
                _warned.add(name)
                print(f"Note: {name} contained spaces or line breaks. Only the first line is used. "
                      f"Check the value where you stored the key.", flush=True)
            return key
    return None


def load_env(*folders):
    """Reads KEY=VALUE lines from a .env file into the environment (without overwriting)."""
    for folder in folders or (Path.cwd(),):
        path = Path(folder) / ".env"
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# ----------------------------------------------------------------------------- Claude

class AnthropicProvider:
    """Claude models through the Anthropic API. Key: ANTHROPIC_API_KEY."""
    key_names = ("ANTHROPIC_API_KEY",)

    def __init__(self, model, max_tokens=6000, temperature=None, force_tool=False, debrief_max_tokens=4000):
        import anthropic
        self.client = anthropic.Anthropic(api_key=clean_key(self.key_names), max_retries=5)
        self.model, self.max_tokens, self.temperature = model, max_tokens, temperature
        self.force_tool, self.debrief_max_tokens = force_tool, debrief_max_tokens

    def _call(self, max_tokens, **kw):
        if self.temperature is not None:
            kw["temperature"] = self.temperature
        return self.client.messages.create(model=self.model, max_tokens=max_tokens, **kw)

    def act(self, system, prompt, tool, reminder=""):
        info = _info(self.model)
        content = prompt
        for _ in range(2):  # one more try if the model answers without the tool
            kw = {"system": system, "messages": [{"role": "user", "content": content}], "tools": [tool]}
            if self.force_tool:
                kw["tool_choice"] = {"type": "tool", "name": tool["name"]}
            info["kall"] += 1
            try:
                r = self._call(self.max_tokens, **kw)
            except Exception as e:
                info["feil"] = f"{type(e).__name__}: {e}"
                return {}, info
            info["inn"] += r.usage.input_tokens
            info["ut"] += r.usage.output_tokens
            info["stopp"] = getattr(r, "stop_reason", None)
            info["avkuttet"] += int(info["stopp"] == "max_tokens")
            info["tekst"] += "".join(getattr(b, "text", "") for b in r.content if b.type == "text")
            for b in r.content:
                if b.type == "tool_use" and b.name == tool["name"]:
                    return dict(b.input), info
            content = prompt + "\n\n" + reminder
        info["feil"] = "no tool call"
        return {}, info

    def reply(self, system, prompt):
        info = _info(self.model)
        info["kall"] = 1
        try:
            r = self._call(self.debrief_max_tokens, system=system, messages=[{"role": "user", "content": prompt}])
        except Exception as e:
            info["feil"] = f"{type(e).__name__}: {e}"
            return "", info
        info["inn"], info["ut"] = r.usage.input_tokens, r.usage.output_tokens
        info["avkuttet"] = int(getattr(r, "stop_reason", None) == "max_tokens")
        return "".join(getattr(b, "text", "") for b in r.content if b.type == "text"), info


# ----------------------------------------------------------------------------- Gemini

class GoogleProvider:
    """Gemini models through the Gemini API (Google AI Studio). Key: GEMINI_API_KEY or GOOGLE_API_KEY."""
    key_names = ("GEMINI_API_KEY", "GOOGLE_API_KEY")

    def __init__(self, model, max_tokens=8000, temperature=None, force_tool=True, debrief_max_tokens=4000):
        from google import genai
        from google.genai import types
        self.types = types
        self.client = genai.Client(api_key=clean_key(self.key_names))
        self.model, self.max_tokens, self.temperature = model, max_tokens, temperature
        self.debrief_max_tokens = debrief_max_tokens

    def _usage(self, r, info):
        u = getattr(r, "usage_metadata", None)
        if u:
            info["inn"] += u.prompt_token_count or 0
            info["ut"] += (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)
        cand = (r.candidates or [None])[0]
        reason = getattr(cand, "finish_reason", None)
        info["stopp"] = getattr(reason, "value", reason)
        info["avkuttet"] += int(info["stopp"] == "MAX_TOKENS")
        parts = (getattr(getattr(cand, "content", None), "parts", None) or []) if cand else []
        return "".join(p.text for p in parts if getattr(p, "text", None) and not getattr(p, "thought", False))

    def act(self, system, prompt, tool, reminder=""):
        t = self.types
        info = _info(self.model)
        config = t.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=self.max_tokens,
            temperature=self.temperature,
            tools=[t.Tool(function_declarations=[t.FunctionDeclaration(
                name=tool["name"], description=tool["description"], parameters_json_schema=tool["input_schema"])])],
            tool_config=t.ToolConfig(function_calling_config=t.FunctionCallingConfig(
                mode="ANY", allowed_function_names=[tool["name"]])),
        )
        content = prompt
        for _ in range(2):
            info["kall"] += 1
            try:
                r = _with_retry(lambda: self.client.models.generate_content(model=self.model, contents=content, config=config))
            except Exception as e:
                info["feil"] = f"{type(e).__name__}: {e}"
                return {}, info
            info["tekst"] += self._usage(r, info)
            for call in (r.function_calls or []):
                if call.name == tool["name"]:
                    return dict(call.args or {}), info
            content = prompt + "\n\n" + reminder
        info["feil"] = "no tool call"
        return {}, info

    def reply(self, system, prompt):
        t = self.types
        info = _info(self.model)
        info["kall"] = 1
        config = t.GenerateContentConfig(system_instruction=system, max_output_tokens=self.debrief_max_tokens,
                                         temperature=self.temperature)
        try:
            r = _with_retry(lambda: self.client.models.generate_content(model=self.model, contents=prompt, config=config))
        except Exception as e:
            info["feil"] = f"{type(e).__name__}: {e}"
            return "", info
        return self._usage(r, info), info


# ----------------------------------------------------------------------------- registry

PROVIDERS = {
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
}


def guess_provider(model):
    m = (model or "").lower()
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith("gemini") or m.startswith("models/gemini"):
        return "google"
    return None


def make_provider(name, model, **settings):
    name = name or guess_provider(model)
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider for model '{model}'. Set 'leverandor' to one of: {', '.join(PROVIDERS)}")
    return PROVIDERS[name](model, **settings)


def missing_key(name):
    """Returns the expected key name if no key for this provider is set, otherwise None."""
    cls = PROVIDERS.get(name)
    names = getattr(cls, "key_names", ())
    if names and not any(os.environ.get(k) for k in names):
        return " or ".join(names)
    return None

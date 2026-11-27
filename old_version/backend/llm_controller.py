"""
LLMController -- OpenRouter chat for Aura UI.
Reads `openrouter_api_key` from secrets.json (or the OPENROUTER_API_KEY env var)
and talks to the OpenRouter chat-completions API using only the standard library.
`chat()` / `generate()` block on the network, so call them from a background thread.
"""
import json
import os
import sys
import threading
import urllib.error
import urllib.request

from backend.paths import base_dir, bundled_json

DATA_DIR = base_dir()
SECRETS_FILE = os.path.join(DATA_DIR, 'secrets.json')
# OpenRouter models, tried in order. The free catalogue changes often: the
# previous list (nemotron-3-super, llama-3.3-70b, gemma-3-27b) started returning
# HTTP 404 "unavailable for free" in Nov 2026. Override without a code change by
# putting "openrouter_models": [...] in secrets.json. Benchmarked 2026-11-25 on
# the Aura Search Stage A prompt: ernie 9.7 s, ling 17.8 s.
DEFAULT_MODELS = [
    # Cheap paid models first (need a little OpenRouter credit): fast and not
    # rate-limited. Benchmarked 2026-11-25 on the Stage A prompt:
    # gpt-oss-20b 3.3 s / $0.00008 per search; gpt-4.1-nano 3.4 s / $0.0004;
    # mistral-small 11.7 s / $0.00018. Pinned ids only, no "~latest" aliases,
    # so study sessions stay reproducible (the model used is logged per search).
    'openai/gpt-oss-20b',
    'openai/gpt-4.1-nano',
    'mistralai/mistral-small-24b-instruct-2501',
    # Free fallbacks (slower, sometimes rate-limited)
    'baidu/ernie-5.5-flash-preview:free',
    'inclusionai/ling-3.2-flash:free',
    'google/gemma-4-31b-it:free',
    'google/gemma-4-26b-a4b-it:free',
    'openrouter/free',
]


def _load_models():
    try:
        with open(SECRETS_FILE, encoding='utf-8') as f:
            custom = json.load(f).get('openrouter_models')
        if isinstance(custom, list) and all(isinstance(m, str) and m for m in custom) and custom:
            return custom
    except Exception:
        pass
    return list(DEFAULT_MODELS)


MODELS = _load_models()
ENDPOINT     = 'https://openrouter.ai/api/v1/chat/completions'

SYSTEM_INSTRUCTION = (
    "You are Aura, an empathetic metacognitive mirror. The user is experiencing "
    "high cognitive load or frustration. Your goal is to actively coach them towards "
    "better mental health, co-regulate their stress, and gently guide them back to a "
    "productive state. Keep responses very short (1-2 sentences). Do not give generic "
    "advice, just ask gentle questions to help them vent and reflect. IMPORTANT: If the "
    "user indicates they feel better, are done, or are 'good', you MUST instruct them to "
    "click the 'I'm Good' button to end this chat and return to their work."
)

OPENER = ("I am feeling stressed. Please ask me a brief question to help me "
          "reflect on what is blocking me.")


class LLMController:
    def __init__(self):
        self._lock    = threading.Lock()
        self._history = []          # [{'role': 'user'|'assistant', 'content': str}]
        self.key      = self._load_key()
        self.status   = 'Ready' if self.key else 'Local coach active (add openrouter_api_key for cloud LLM)'

    @property
    def available(self):
        # Always available: uses OpenRouter when a key is present, and falls back
        # seamlessly to the built-in empathetic co-regulation coach when offline or unconfigured.
        return True

    @staticmethod
    def _load_key():
        key = ''
        try:
            with open(SECRETS_FILE, encoding='utf-8') as f:
                key = json.load(f).get('openrouter_api_key', '')
        except Exception:
            pass
        if not key:
            key = (bundled_json('aura_defaults.json').get('openrouter_api_key') or '')
        key = (key or os.environ.get('OPENROUTER_API_KEY', '')).strip()
        return '' if key.startswith('YOUR_') else key

    def reset(self):
        with self._lock:
            self._history = []

    def _complete_model(self, model, system, messages):
        body = json.dumps({
            'model': model,
            'messages': [{'role': 'system', 'content': system}] + messages,
            'max_tokens': 600,
            # all current free models reason; keep it short and out of the reply
            'reasoning': {'effort': 'low', 'exclude': True},
        }).encode()
        req = urllib.request.Request(
            ENDPOINT, data=body, method='POST',
            headers={'Content-Type': 'application/json',
                     'Authorization': 'Bearer ' + self.key,
                     'X-Title': 'Aura UI'})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
        text = (data['choices'][0]['message'].get('content') or '').strip()
        if not text:
            raise RuntimeError('empty reply from ' + model)
        return text

    def _complete(self, system, messages):
        if not self.key:
            raise RuntimeError('No OpenRouter API key configured')
        last_err = None
        for model in MODELS:
            try:
                return self._complete_model(model, system, messages)
            except urllib.error.HTTPError as e:
                last_err = RuntimeError('OpenRouter HTTP {} ({})'.format(e.code, model))
                if e.code in (401, 403):
                    break
            except Exception as e:
                last_err = RuntimeError(str(e))
        raise last_err or RuntimeError('All OpenRouter models failed')

    @staticmethod
    def local_chat_reply(user_text, turn_index=0):
        """Context-aware empathetic fallback when offline or without an OpenRouter key."""
        low = (user_text or '').strip().lower()
        if user_text == OPENER:
            prompts = [
                "I noticed your typing rhythm sped up—what's the one part of this task that feels most frustrating right now?",
                "It looks like you're pushing through a heavy block of work. What's the main thing slowing you down at this moment?",
                "Let's pause for five seconds. Which small piece of what you're working on is creating the most friction?"
            ]
            return prompts[turn_index % len(prompts)]
        if any(w in low for w in ('good', 'better', 'fine', 'okay', 'ok', 'done', 'thanks', 'thank you', 'ready', 'calm')):
            return ("I'm glad you're feeling steadier. Whenever you're ready to dive back in, "
                    "click the \"I'm Good\" button above to clear this chat.")
        if any(w in low for w in ('bug', 'error', 'code', 'coding', 'crash', 'broken', 'fix', 'test')):
            return ("Debugging under pressure is exhausting. Instead of fixing the whole thing at once, "
                    "what is the smallest single assumption you can check next?")
        if any(w in low for w in ('time', 'deadline', 'rush', 'late', 'fast', 'exam', 'submission')):
            return ("Time pressure makes everything feel urgent at once. If you only had to finish "
                    "one 5-minute step right now, which one would move you forward?")
        if any(w in low for w in ('tired', 'exhausted', 'overwhelmed', 'stuck', 'hard', 'confused', 'lost')):
            return ("It makes complete sense that you're feeling drained. Try clicking 'Breathe' above for "
                    "three slow sighs—what's one part of this you can simplify?")
        followups = [
            "I hear you—that sounds genuinely taxing. What is the smallest next step that would make this feel 10% easier?",
            "That makes a lot of sense. If you stepped back for one slow breath, what part of this task actually matters most right now?",
            "Thanks for naming that out loud. Once you feel ready to return to your flow, click \"I'm Good\" above."
        ]
        return followups[turn_index % len(followups)]

    # ------- structured JSON output (Aura Search) ---------------------------

    @staticmethod
    def extract_json(text):
        """Parse a JSON object from a model reply, tolerating ```json fences and
        leading/trailing prose. Raises ValueError when no object can be found."""
        t = (text or '').strip()
        if t.startswith('```'):
            t = t.split('\n', 1)[1] if '\n' in t else ''
            if t.rstrip().endswith('```'):
                t = t.rstrip()[:-3]
        try:
            obj = json.loads(t)
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
        start = t.find('{')
        while start != -1:
            depth, in_str, esc = 0, False, False
            for i in range(start, len(t)):
                ch = t[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == '\\':
                        esc = True
                    elif ch == '"':
                        in_str = False
                elif ch == '"':
                    in_str = True
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            obj = json.loads(t[start:i + 1])
                            if isinstance(obj, dict):
                                return obj
                        except ValueError:
                            pass
                        break
            start = t.find('{', start + 1)
        raise ValueError('no JSON object in model reply')

    def _complete_json_model(self, model, messages, max_tokens, timeout, temperature):
        body = json.dumps({
            'model': model,
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': temperature,
            'response_format': {'type': 'json_object'},
            'reasoning': {'effort': 'low', 'exclude': True},
        }).encode()
        req = urllib.request.Request(
            ENDPOINT, data=body, method='POST',
            headers={'Content-Type': 'application/json',
                     'Authorization': 'Bearer ' + self.key,
                     'X-Title': 'Aura UI'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        choice = data['choices'][0]
        if choice.get('finish_reason') == 'length':
            raise RuntimeError('reply truncated at max_tokens')
        return self.extract_json(choice['message'].get('content') or '')

    def complete_json(self, messages, max_tokens=4000, timeout=30, temperature=0.2,
                      models=None):
        """Return (parsed_dict, model_used). Tries each model in turn and moves on
        when a reply is not valid JSON. Raises RuntimeError when every model fails
        or no key is configured -- callers fall back to their offline path."""
        if not self.key:
            raise RuntimeError('No OpenRouter API key configured')
        last_err = None
        for model in (models or MODELS):
            try:
                return self._complete_json_model(model, messages, max_tokens, timeout,
                                                 temperature), model
            except urllib.error.HTTPError as e:
                last_err = RuntimeError('OpenRouter HTTP {} ({})'.format(e.code, model))
                if e.code in (401, 403):
                    break
            except Exception as e:
                last_err = RuntimeError('{}: {}'.format(model, e))
        raise last_err or RuntimeError('All OpenRouter models failed')

    def generate(self, prompt, system):
        """One-shot completion that does not touch the chat history."""
        if not self.key:
            raise RuntimeError('No OpenRouter API key configured')
        return self._complete(system, [{'role': 'user', 'content': prompt}])

    def chat(self, user_text, stress_note=''):
        """Send one user turn, return Aura's reply (cloud LLM with automatic local fallback)."""
        system = SYSTEM_INSTRUCTION
        if stress_note:
            system += ' Current sensor reading: ' + stress_note
        with self._lock:
            messages = self._history + [{'role': 'user', 'content': user_text}]
            turn_idx = len(self._history) // 2
            try:
                text = self._complete(system, messages)
            except Exception as e:
                print('[Aura UI] using local coach fallback:', e)
                text = self.local_chat_reply(user_text, turn_idx)
            self._history = messages + [{'role': 'assistant', 'content': text}]
            return text

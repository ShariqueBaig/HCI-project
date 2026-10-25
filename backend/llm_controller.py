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

if getattr(sys, 'frozen', False):
    DATA_DIR = os.path.dirname(sys.executable)
else:
    DATA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRETS_FILE = os.path.join(DATA_DIR, 'secrets.json')
MODEL        = 'nvidia/nemotron-3.5-super-vl:free'
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
        self.status   = 'Ready' if self.key else 'No OpenRouter key in secrets.json'

    @property
    def available(self):
        return bool(self.key)

    @staticmethod
    def _load_key():
        try:
            with open(SECRETS_FILE) as f:
                key = json.load(f).get('openrouter_api_key', '')
        except Exception:
            key = ''
        key = (key or os.environ.get('OPENROUTER_API_KEY', '')).strip()
        return '' if key.startswith('YOUR_') else key

    def reset(self):
        with self._lock:
            self._history = []

    def _complete(self, system, messages):
        body = json.dumps({
            'model': MODEL,
            'messages': [{'role': 'system', 'content': system}] + messages,
            'max_tokens': 800,
            'reasoning': {'exclude': True},   # keep the model's thinking out of the reply
        }).encode()
        req = urllib.request.Request(
            ENDPOINT, data=body, method='POST',
            headers={'Content-Type': 'application/json',
                     'Authorization': 'Bearer ' + self.key,
                     'X-Title': 'Aura UI'})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = json.load(r)
            text = (data['choices'][0]['message'].get('content') or '').strip()
        except urllib.error.HTTPError as e:
            raise RuntimeError('OpenRouter HTTP {}'.format(e.code))
        except Exception as e:
            raise RuntimeError(str(e))
        if not text:
            raise RuntimeError('empty reply')
        return text

    def generate(self, prompt, system):
        """One-shot completion that does not touch the chat history."""
        if not self.key:
            raise RuntimeError('No OpenRouter API key configured')
        return self._complete(system, [{'role': 'user', 'content': prompt}])

    def chat(self, user_text, stress_note=''):
        """Send one user turn, return Aura's reply. Raises RuntimeError on failure."""
        if not self.key:
            raise RuntimeError('No OpenRouter API key configured')
        system = SYSTEM_INSTRUCTION
        if stress_note:
            system += ' Current sensor reading: ' + stress_note
        with self._lock:
            messages = self._history + [{'role': 'user', 'content': user_text}]
            text = self._complete(system, messages)
            self._history = messages + [{'role': 'assistant', 'content': text}]
            return text

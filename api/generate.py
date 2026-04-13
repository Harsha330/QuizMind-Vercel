from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request

GROK_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "llama-3.1-8b-instant",
    "qwen-qwq-32b",
]

class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        topic = body.get("topic", "").strip()
        num_q = min(max(int(body.get("num_questions", 5)), 3), 20)
        api_key = body.get("api_key", "") or os.environ.get("GROK_API_KEY", "")

        if not topic:
            self._json({"error": "Topic is required"}, 400)
            return
        if not api_key:
            self._json({"error": "Grok API key is required"}, 400)
            return

        prompt = (
            f'Generate {num_q} multiple choice quiz questions about "{topic}". '
            'Return ONLY a valid JSON array, no markdown, no extra text. '
            'Each item: {"question":"...","options":["A","B","C","D"],"correct":0,"explanation":"..."} '
            'where correct is the 0-based index of the right answer.'
        )

        last_error = ""
        for model in MODELS:
            payload = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 3000
            }).encode()

            req = urllib.request.Request(
                GROK_URL,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                },
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    data = json.loads(resp.read())
                    content = data["choices"][0]["message"]["content"].strip()
                    if content.startswith("```"):
                        parts = content.split("```")
                        content = parts[1]
                        if content.startswith("json"):
                            content = content[4:]
                    questions = json.loads(content.strip())
                    self._json({"questions": questions, "topic": topic, "model": model})
                    return
            except urllib.error.HTTPError as e:
                err_body = e.read().decode()
                last_error = f"{model}: HTTP {e.code} - {err_body}"
                if e.code not in (400, 404):
                    break
                continue
            except Exception as e:
                last_error = f"{model}: {str(e)}"
                continue

        self._json({"error": f"Quiz generation failed. {last_error}"}, 500)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

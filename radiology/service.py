"""Service local du lecteur de radiographies thoraciques, appelé par la fonction MedAssist d'Open WebUI.

  POST http://127.0.0.1:8765/analyze  {"image": "<base64>", "population": "adulte"|"enfant"}
       -> verdict global, anomalies au-dessus des seuils calibrés, côté, image annotée
  GET  http://127.0.0.1:8765/health

N'écoute que sur 127.0.0.1 : aucune image ne sort du PC. À lancer avec le Python de cxr-venv.
"""
import base64
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cxr_model import WEIGHTS, CXRReader  # noqa: E402

PORT = 8765
MAX_BYTES = 30 * 1024 * 1024
reader = CXRReader()
lock = threading.Lock()  # un seul calcul à la fois (CPU partagé avec Ollama)


class Handler(BaseHTTPRequestHandler):
    timeout = 120  # un corps plus court que Content-Length ne bloque pas le fil indéfiniment

    def _send(self, code, payload):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ok": True, "modele": WEIGHTS})
        else:
            self._send(404, {"erreur": "inconnu"})

    def do_POST(self):
        if self.path != "/analyze":
            return self._send(404, {"erreur": "inconnu"})
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return self._send(400, {"erreur": "Content-Length invalide"})
        if not 0 < length <= MAX_BYTES:
            return self._send(413, {"erreur": "image absente ou trop grande"})
        try:
            req = json.loads(self.rfile.read(length))
            image = base64.b64decode(req["image"])
            population = req.get("population") if req.get("population") in ("enfant", "adulte") else "adulte"
            with lock:
                result = reader.analyze(image, population)
                if result["anomalies"]:
                    # Carte de l'anomalie qui sert au calcul du côté (première au côté net), sinon la première
                    sided = [f for f in result["anomalies"] if f.get("cote_patient") in ("droit", "gauche")]
                    top = (sided or result["anomalies"])[0]["anomalie"]
                    result["image_annotee"] = base64.b64encode(reader.overlay_jpeg(image, top)).decode()
                    result["image_annotee_pour"] = top
            self._send(200, result)
        except Exception as e:  # noqa: BLE001 - renvoyer l'erreur au pipeline plutôt que couper la connexion
            self._send(400, {"erreur": f"{type(e).__name__}: {e}"})

    def log_message(self, fmt, *args):
        pass  # pas de journal des requêtes (images de patients)


if __name__ == "__main__":
    print(f"Lecteur radio thorax prêt sur http://127.0.0.1:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()

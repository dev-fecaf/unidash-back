"""Hub simulado, só para testar o link de embed no computador (nunca em hml ou prd).

Faz o papel do Hub: abre o dashboard do UniDash num iframe e, quando a página pede
("embed:ready" ou "embed:token-expired"), responde com um token de 60 s assinado com o
EMBED_HUB_SECRET do seu .env, no formato combinado com o Hub (sem e-mail, que o Hub não tem).

Como usar (com o back e o front ligados):
    1. No .env do back:  EMBED_HUB_ORIGIN=http://localhost:5174  e um EMBED_HUB_SECRET qualquer (32+ caracteres)
    2. No .env do front: VITE_EMBED_HUB_ORIGIN=http://localhost:5174
    3. Na pasta unidash-back:  .venv\\Scripts\\python scripts\\hub_simulado.py
    4. Abra http://localhost:5174, cole o hash do dashboard (do Gerador) e clique em Abrir.
"""

import json
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import jwt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.config import obter_config  # noqa: E402

PORTA = 5174
FRONT = "http://localhost:5173"  # onde o front do UniDash roda no computador

PAGINA = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>Hub simulado</title>
<style>
  body { margin: 0; font: 14px system-ui, sans-serif; background: #f3f4f6; color: #111; }
  form { display: flex; gap: 8px; flex-wrap: wrap; align-items: end; padding: 12px 16px; background: #fff; border-bottom: 1px solid #ddd; }
  label { display: grid; gap: 4px; font-size: 12px; color: #555; }
  input { padding: 6px 8px; border: 1px solid #ccc; border-radius: 6px; min-width: 220px; }
  button { padding: 7px 14px; border: 0; border-radius: 999px; background: #102E33; color: #fff; cursor: pointer; }
  #log { padding: 4px 16px; font-size: 12px; color: #555; }
  iframe { display: block; width: 100%; height: calc(100vh - 110px); border: 0; background: #fff; }
</style></head><body>
<form id="f">
  <label>Hash do dashboard <input id="hash" required placeholder="cole o hash do Gerador"></label>
  <label>Login <input id="sub" value="pessoa.teste"></label>
  <label>Setores (separados por vírgula) <input id="setores" value="Financeiro, Secretaria"></label>
  <label>Páginas liberadas (códigos separados por vírgula; vazio = todas) <input id="paginas"></label>
  <button>Abrir</button>
</form>
<p id="log">Hub simulado: só para testes no computador.</p>
<iframe id="quadro" title="Dashboard"></iframe>
<script>
  const FRONT = '__FRONT__'
  const $ = (id) => document.getElementById(id)
  const log = (t) => { $('log').textContent = new Date().toLocaleTimeString() + ' · ' + t }
  $('f').onsubmit = (e) => {
    e.preventDefault()
    $('quadro').src = FRONT + '/embed/' + $('hash').value.trim()
    log('abrindo o dashboard…')
  }
  window.addEventListener('message', async (e) => {
    if (e.origin !== FRONT) return  // igual ao Hub: só conversa com o UniDash
    if (e.data?.type !== 'embed:ready' && e.data?.type !== 'embed:token-expired') return
    const q = new URLSearchParams({ dash: $('hash').value.trim(), sub: $('sub').value, setores: $('setores').value, paginas: $('paginas').value })
    const { token } = await (await fetch('/token?' + q)).json()
    $('quadro').contentWindow.postMessage({ type: 'hub:token', token }, FRONT)
    log('recebi "' + e.data.type + '" e mandei um token novo')
  })
</script></body></html>
"""


class Tratador(BaseHTTPRequestHandler):
    def _responder(self, corpo: bytes, tipo: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):  # noqa: N802 (nome exigido pelo http.server)
        url = urlparse(self.path)
        if url.path == "/token":
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            dados = {
                "dash": q.get("dash", ""), "sub": q.get("sub") or "pessoa.teste", "name": "Pessoa Teste",
                "exp": int(time.time()) + 60, "jti": uuid.uuid4().hex,
            }
            if q.get("setores", "").strip():
                dados["setores"] = [s.strip() for s in q["setores"].split(",") if s.strip()]
            if q.get("paginas", "").strip():
                dados["paginas"] = [p.strip() for p in q["paginas"].split(",") if p.strip()]
            segredo = obter_config().embed_hub_secret.get_secret_value()
            token = jwt.encode(dados, segredo, algorithm="HS256")
            self._responder(json.dumps({"token": token}).encode(), "application/json")
        else:
            self._responder(PAGINA.replace("__FRONT__", FRONT).encode(), "text/html; charset=utf-8")

    def log_message(self, *_args):  # sem barulho no terminal
        pass


if __name__ == "__main__":
    if not obter_config().embed_hub_secret.get_secret_value():
        sys.exit("Preencha EMBED_HUB_SECRET no .env do back (32+ caracteres).")
    print(f"Hub simulado em http://localhost:{PORTA}  (Ctrl+C para parar)")
    ThreadingHTTPServer(("localhost", PORTA), Tratador).serve_forever()

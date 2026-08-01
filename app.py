import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Servidor HTTP simples apenas para atender à exigência de porta do Render Free
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Konomee online!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

# Inicia o servidor HTTP em segundo plano
threading.Thread(target=run_server, daemon=True).start()

# IMPORTANTE: Aqui embaixo você chama o seu arquivo principal do Bot do Telegram
# Exemplo: import bot  (ou execute o seu loop principal do bot aqui)
if __name__ == "__main__":
    print("Iniciando bot e servidor web falso...")
    # Coloque aqui a chamada para iniciar o seu bot (ex: bot.main())
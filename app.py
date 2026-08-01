import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# 1. Servidor HTTP simples para atender à porta exigida pelo Render (Free)
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Konomee online!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    print(f"Servidor web falso rodando na porta {port}...")
    server.serve_forever()

# 2. Função que dispara o seu bot principal
def run_bot():
    try:
        print("Iniciando o Userbot do Telegram...")
        # Importa e executa o seu arquivo principal do bot (ajuste o nome se não for bot.py)
        import bot
        if hasattr(bot, 'main'):
            bot.main()
    except Exception as e:
        print(f"Erro ao rodar o bot: {e}")

if __name__ == "__main__":
    print("Iniciando sistema integrado no Render...")

    # Inicia o servidor HTTP em uma thread separada (em segundo plano)
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Roda o bot na thread principal (mantendo a aplicação viva)
    run_bot()
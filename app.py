import os
import threading
import traceback
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler

# 1. Servidor HTTP simples para manter a porta 10000 ativa exigida pelo Render (Free)
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Konomee online!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    print(f"Servidor web rodando na porta {port}...")
    server.serve_forever()

# 2. Função que dispara o seu bot principal com tratamento completo de erros
def run_bot():
    try:
        print("Iniciando o Userbot do Telegram...")
        import bot
        
        if hasattr(bot, 'main'):
            # Verifica se a função main do bot é assíncrona ou síncrona
            if asyncio.iscoroutinefunction(bot.main):
                asyncio.run(bot.main())
            else:
                bot.main()
        else:
            print("AVISO: A função 'main()' não foi encontrada no arquivo bot.py.")
            
    except Exception as e:
        print("=== ERRO CRÍTICO AO EXECUTAR O BOT ===")
        traceback.print_exc()  # Mostra a linha exata e o erro detalhado nos logs do Render
    except KeyboardInterrupt:
        print("Bot interrompido manualmente.")

if __name__ == "__main__":
    print("Iniciando sistema integrado no Render...")

    # Inicia o servidor HTTP em uma thread separada (em segundo plano)
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Roda o bot na thread principal
    run_bot()
    
    # Mantém o processo vivo caso o bot encerre sem erro crítico
    print("O processo principal foi finalizado. Mantendo container ativo...")
    try:
        import time
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
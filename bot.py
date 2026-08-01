import os
import re
import threading
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from supabase import create_client, Client
from dotenv import load_dotenv

# Importação dos parsers individuais
from parsers import amazon, mercadolivre, shopee, aliexpress, shein, temu

load_dotenv()

API_ID = int(os.getenv('TELEGRAM_API_ID', 0))
API_HASH = os.getenv('TELEGRAM_API_HASH', '')
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')
STRING_SESSION = os.getenv('STRING_SESSION', '')

if not all([API_ID, API_HASH, SUPABASE_URL, SUPABASE_KEY, STRING_SESSION]):
    print("ERRO CRÍTICO: Faltam credenciais ou a STRING_SESSION no ambiente!")
    exit()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__)

# Inicializa o cliente do Telegram usando a StringSession para o Render
client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

def identificar_parser_por_url(url):
    url_lower = url.lower()
    if 'amazon' in url_lower or 'amzn.to' in url_lower:
        return amazon.processar
    elif 'mercadolivre' in url_lower or 'meli.la' in url_lower:
        return mercadolivre.processar
    elif 'shopee' in url_lower:
        return shopee.processar
    elif 'aliexpress' in url_lower:
        return aliexpress.processar
    elif 'shein' in url_lower:
        return shein.processar
    elif 'temu' in url_lower:
        return temu.processar
    return None

# Ouvinte universal: Valida dinamicamente no Supabase a cada mensagem recebida
@client.on(events.NewMessage())
async def processar_mensagem(event):
    chat_id_atual = event.chat_id
    
    # 1. Busca os grupos autorizados diretamente no Supabase em tempo real
    try:
        resposta_grupos = supabase.table('grupos_monitorados').select('*').execute()
        if resposta_grupos.data:
            autorizados = []
            for g in resposta_grupos.data:
                tid = str(g.get('telegram_id') or g.get('id') or '')
                if tid:
                    autorizados.append(int(tid) if tid.lstrip('-').isdigit() else tid)
            
            # Se houver grupos cadastrados e o chat atual não estiver na lista (permitindo 'me' para testes)
            if autorizados and chat_id_atual not in autorizados and str(chat_id_atual) not in [str(x) for x in autorizados]:
                if chat_id_atual != 'me':  # Permite chat salvo para testes manuais
                    return
    except Exception as e:
        print(f"Erro ao validar grupo no Supabase: {e}")
        return

    texto = event.raw_text
    if not texto:
        return

    print(f"\n--- NOVA MENSAGEM NO CHAT {chat_id_atual} ---")
    
    regex_links = r'https?://[^\s<>"\']+'
    links_encontrados = re.findall(regex_links, texto)
    if not links_encontrados: 
        return
        
    # ====================================================================
    # 🎯 SELETOR INTELIGENTE DE LINKS (EVITA PÁGINAS DE MOEDAS)
    # ====================================================================
    link_principal = links_encontrados[0].rstrip('.,;:)')
    
    if len(links_encontrados) > 1:
        for link in links_encontrados:
            l_clean = link.rstrip('.,;:)')
            l_lower = l_clean.lower()
            
            if 'coin' in l_lower:
                continue
                
            pos = texto.find(link)
            if pos != -1:
                contexto_antes = texto[max(0, pos-35):pos].lower()
                if 'moeda' in contexto_antes or 'coin' in contexto_antes:
                    continue
                    
            link_principal = l_clean
            break
    # ====================================================================

    parser_func = identificar_parser_por_url(link_principal)
    
    if not parser_func:
        print(f"🚫 Plataforma não suportada para o link: {link_principal}")
        return

    try:
        dados_oferta = parser_func(texto, link_principal)
        
        url_parseada = urlparse(dados_oferta["link_resolvido"])
        parametros_url = parse_qs(url_parseada.query)
        
        chaves_url = list(parametros_url.keys())
        for chave in chaves_url:
            chave_lower = chave.lower()
            if chave_lower.startswith('aff_') or chave_lower.startswith('utm'):
                parametros_url.pop(chave, None)
            elif chave_lower in ['sk', 'share_click_id', 'alida', 'tag', 'ascsubtag', 'campid', 'customid']:
                parametros_url.pop(chave, None)

        lojas = supabase.table('lojas_afiliadas').select('*').execute().data or []
        dominio_atual = url_parseada.netloc.replace('www.', '')

        loja_identificada = next((l for l in lojas if (l.get('dominio_alvo') or '') in dominio_atual), None)
        
        if loja_identificada and loja_identificada.get('parametro_afiliado'):
            param_str = loja_identificada.get('parametro_afiliado').lstrip('?')
            params_supabase = parse_qs(param_str)
            for chave, valor in params_supabase.items():
                parametros_url[chave] = valor
        
        nova_query = urlencode(parametros_url, doseq=True)
        link_afiliado_perfeito = urlunparse((
            url_parseada.scheme, 
            url_parseada.netloc, 
            url_parseada.path, 
            url_parseada.params, 
            nova_query, 
            url_parseada.fragment
        ))
        
        supabase.table('historico_ofertas').insert([{
            "loja": dados_oferta["loja"],
            "nome_produto": dados_oferta["nome_produto"], 
            "titulo_descricao": dados_oferta["titulo_descricao"],
            "preco": dados_oferta["preco"],
            "link_afiliado": link_afiliado_perfeito,
            "imagem": dados_oferta["imagem"],
            "cupom": dados_oferta["cupom"]
        }]).execute()
        
        print(f"✅ Salvo via Módulo [{dados_oferta['loja']}]: {dados_oferta['nome_produto'][:35]}...")
        
    except Exception as e:
        print(f"Erro no roteamento do parser: {e}")

@app.route('/')
def home(): 
    return "Servidor rodando."

def rodar_api(): 
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)), use_reloader=False)

if __name__ == '__main__':
    print("Iniciando servidor web em segundo plano...")
    threading.Thread(target=rodar_api, daemon=True).start()
    
    print("Iniciando conexão com o Telegram via StringSession...")
    if not STRING_SESSION:
        print("ERRO CRÍTICO: A variável STRING_SESSION está vazia ou não foi encontrada no Render!")
    else:
        print(f"STRING_SESSION detectada (Tamanho: {len(STRING_SESSION)} caracteres). Conectando...")

    client.start()
    print("Bot conectado com sucesso ao Telegram! Ouvindo mensagens...")
    client.run_until_disconnected()
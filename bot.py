import os
import re
import threading
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from flask import Flask
from telethon import TelegramClient, events
from supabase import create_client, Client
from dotenv import load_dotenv

# Importação dos parsers individuais
from parsers import amazon, mercadolivre, shopee, aliexpress, shein, temu

load_dotenv()

API_ID = int(os.getenv('TELEGRAM_API_ID', 0))
API_HASH = os.getenv('TELEGRAM_API_HASH', '')
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

if not all([API_ID, API_HASH, SUPABASE_URL, SUPABASE_KEY]):
    print("ERRO CRÍTICO: Faltam credenciais no arquivo .env!")
    exit()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__)
client = TelegramClient('sessao_konomee', API_ID, API_HASH)

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

print("Buscando grupos monitorados...")
lista_de_chats = ['me']
try:
    resposta_grupos = supabase.table('grupos_monitorados').select('*').execute()
    if resposta_grupos.data:
        lista_de_chats = [str(g.get('telegram_id') or g.get('id') or '') for g in resposta_grupos.data]
        lista_de_chats = [int(tid) if tid.lstrip('-').isdigit() else tid for tid in lista_de_chats if tid]
    if not lista_de_chats: lista_de_chats = ['me']
except:
    pass

@client.on(events.NewMessage(chats=lista_de_chats))
async def processar_mensagem(event):
    texto = event.raw_text
    print("\n--- NOVA MENSAGEM DETECTADA ---")
    
    regex_links = r'https?://[^\s<>"\']+'
    links_encontrados = re.findall(regex_links, texto)
    if not links_encontrados: return
        
    # ====================================================================
    # 🎯 SELETOR INTELIGENTE DE LINKS (EVITA PÁGINAS DE MOEDAS)
    # ====================================================================
    link_principal = links_encontrados[0].rstrip('.,;:)')
    
    if len(links_encontrados) > 1:
        for link in links_encontrados:
            l_clean = link.rstrip('.,;:)')
            l_lower = l_clean.lower()
            
            # 1. Se a própria URL já denuncia que é link de moedas, pula.
            if 'coin' in l_lower:
                continue
                
            # 2. Lê os 35 caracteres antes do link no texto do Telegram
            pos = texto.find(link)
            if pos != -1:
                contexto_antes = texto[max(0, pos-35):pos].lower()
                # Se alguém escreveu "moeda", "moedas" ou "coin" antes do link, pula.
                if 'moeda' in contexto_antes or 'coin' in contexto_antes:
                    continue
                    
            # Se o link sobreviveu aos testes, ele é o link de produto real!
            link_principal = l_clean
            break
    # ====================================================================

    parser_func = identificar_parser_por_url(link_principal)
    
    if not parser_func:
        print(f"🚫 Plataforma não suportada para o link: {link_principal}")
        return

    try:
        dados_oferta = parser_func(texto, link_principal)
        
        # 1. Desmonta o link resolvido pelo parser para fazer a faxina
        url_parseada = urlparse(dados_oferta["link_resolvido"])
        parametros_url = parse_qs(url_parseada.query)
        
        # 2. FAXINA INTELIGENTE: Remove lixo de afiliados dinamicamente
        chaves_url = list(parametros_url.keys())
        for chave in chaves_url:
            chave_lower = chave.lower()
            
            # Regra 1: Remove qualquer rastreador de afiliado do AliExpress e UTMs
            if chave_lower.startswith('aff_') or chave_lower.startswith('utm'):
                parametros_url.pop(chave, None)
                
            # Regra 2: Remove rastreadores específicos de outras plataformas
            elif chave_lower in ['sk', 'share_click_id', 'alida', 'tag', 'ascsubtag', 'campid', 'customid']:
                parametros_url.pop(chave, None)

        # 3. Busca OS SEUS parâmetros cadastrados no Supabase
        lojas = supabase.table('lojas_afiliadas').select('*').execute().data or []
        dominio_atual = url_parseada.netloc.replace('www.', '')

        loja_identificada = next((l for l in lojas if (l.get('dominio_alvo') or '') in dominio_atual), None)
        
        # 4. Injeta os seus parâmetros perfeitamente no link limpo
        if loja_identificada and loja_identificada.get('parametro_afiliado'):
            param_str = loja_identificada.get('parametro_afiliado').lstrip('?')
            params_supabase = parse_qs(param_str)
            for chave, valor in params_supabase.items():
                parametros_url[chave] = valor
        
        # 5. Remonta o link final blindado
        nova_query = urlencode(parametros_url, doseq=True)
        link_afiliado_perfeito = urlunparse((
            url_parseada.scheme, 
            url_parseada.netloc, 
            url_parseada.path, 
            url_parseada.params, 
            nova_query, 
            url_parseada.fragment
        ))
        
        # Salva no banco de dados com o link perfeitamente higienizado
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
def home(): return "Servidor rodando."
def rodar_api(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)), use_reloader=False)

if __name__ == '__main__':
    threading.Thread(target=rodar_api, daemon=True).start()
    client.start()
    client.run_until_disconnected()
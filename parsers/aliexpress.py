import re
import requests
from urllib.parse import unquote

def processar(texto, url_inicial):
    link_final = url_inicial.strip()
    logo_fallback = "https://cdn-icons-png.flaticon.com/512/732/732230.png"
    foto_url = "Imagem não encontrada"
    nome_produto_web = ""
    preco_web = "Preço não informado"
    
    # ==========================================
    # 1. EXTRAÇÃO DO TEXTO (TELEGRAM)
    # ==========================================
    cupom = ""
    match_cupom = re.search(r'(?i)(?:cupom|código|codigo|desconto)\s*[:=]?\s*([A-Za-z0-9_-]{3,25})', texto)
    if match_cupom:
        cupom = match_cupom.group(1).upper()
    else:
        match_moedas = re.search(r'(?i)\b([A-Za-z0-9_-]{3,25})\s*\+\s*[Mm]oedas', texto)
        if match_moedas:
            cupom = match_moedas.group(1).upper()

    if cupom in ['HTTP', 'HTTPS', 'WWW', 'COM', 'BR', 'NOSSA', 'LISTA', 'PRODUTO', 'CLIQUE', 'MAIS', 'VENDIDOS', 'MOEDAS', 'PIX', 'VALOR', 'DESCONTO']:
        cupom = ""

    preco_txt = "Preço não informado"
    m_preco = re.search(r'R\$\s?[\d.,]+', texto)
    if m_preco:
        preco_txt = m_preco.group(0).strip().rstrip(',')

    texto_limpo = re.sub(r'[^\w\s.,;:!?@#$%&*()\-+=\[\]{}<>/\'\"\\|]+', '', texto, flags=re.UNICODE)
    for l in re.findall(r'https?://[^\s<>"\']+', texto):
        texto_limpo = texto_limpo.replace(l, '')
        
    linhas = [l.strip() for l in texto_limpo.split('\n') if l.strip()]
    nome_txt = ""
    for linha in linhas:
        if not linha.lower().startswith('r$') and 'http' not in linha.lower() and len(linha) > 5:
            nome_txt = linha
            break

    # ==========================================
    # 2. CAÇADOR DO ID DO PRODUTO
    # ==========================================
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    })
    
    html = ""
    current_url = link_final
    try:
        for _ in range(3):
            res = session.get(current_url, allow_redirects=True, timeout=10)
            html = res.text
            current_url = res.url
            
            m_js = re.search(r'window\.location\.(?:replace|href)\s*=\s*[\'"]([^\'"]+)[\'"]', html)
            m_meta = re.search(r'<meta[^>]*http-equiv=["\']refresh["\'][^>]*content=["\']\d+;\s*url=([^"\']+)["\']', html, re.IGNORECASE)
            
            redir = None
            if m_js: redir = m_js.group(1)
            elif m_meta: redir = m_meta.group(1)
            
            if redir:
                redir = redir.replace('\\/', '/')
                if redir.startswith('//'): redir = 'https:' + redir
                elif not redir.startswith('http'): redir = 'https://' + redir.lstrip('/')
                
                if 'login.' not in redir:
                    current_url = redir
                    continue
            break
        link_final = current_url
    except Exception as e:
        print(f"⚠️ Aviso Redirecionamento AliExpress: {e}")

    # ==========================================
    # 3. URL CANÔNICA (VITRINE LIMPA)
    # ==========================================
    prod_id = None
    m_id = re.search(r'(?:/item/|/p/trade/|/product/|item_id=)(\d{11,16})', link_final)
    if m_id:
        prod_id = m_id.group(1)
    else:
        m_html_id = re.search(r'(?:"productId"|productId)\s*[:=]\s*"?(\d{11,16})"?', html)
        if m_html_id:
            prod_id = m_html_id.group(1)

    if prod_id:
        try:
            session.headers.update({'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'})
            res_clean = session.get(f"https://pt.aliexpress.com/item/{prod_id}.html", timeout=10)
            if res_clean.status_code == 200:
                html = res_clean.text
                link_final = res_clean.url
        except Exception as e:
            print(f"⚠️ Aviso HTML Canônico AliExpress: {e}")

    # ==========================================
    # 4. VALIDADOR DE VITRINE E RASPAGEM
    # ==========================================
    # REGRA NOVA: Garante que é uma página de produto real antes de raspar
    tem_vitrine_valida = bool(re.search(r'og:title|subject', html)) and bool(re.search(r'og:image|imagePathList', html))
    
    if html and tem_vitrine_valida:
        # --- TÍTULO COMPLETO ---
        og_t = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
        if og_t:
            nome_produto_web = unquote(og_t.group(1)).strip()
            nome_produto_web = re.sub(r'(?i)(\s*[-|]\s*aliexpress.*|\s*online shopping.*)$', '', nome_produto_web).strip()
        else:
            sub_t = re.search(r'"subject"\s*:\s*"([^"\\]+)', html)
            if sub_t:
                nome_produto_web = sub_t.group(1).strip()

        # --- IMAGEM OFICIAL ---
        og_i = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
        if og_i:
            foto_url = og_i.group(1).replace('\\/', '/')
            if '.jpg' in foto_url:
                foto_url = foto_url.split('.jpg')[0] + '.jpg'
        else:
            img_list = re.search(r'"imagePathList"\s*:\s*\[\s*"([^"]+)"', html)
            if img_list:
                foto_url = img_list.group(1).replace('\\/', '/')

        # --- PREÇO WEB ---
        padroes_preco = [
            r'"formatedActivityPrice"\s*:\s*"([^"]+)"',
            r'"formatedPrice"\s*:\s*"([^"]+)"',
            r'"formatTradePrice"\s*:\s*"([^"]+)"',
            r'"formatedAmount"\s*:\s*"([^"]+)"',
            r'"price"\s*:\s*"([^"]+)"'
        ]
        
        for padrao in padroes_preco:
            m_json = re.search(padrao, html)
            if m_json:
                val = m_json.group(1).replace('\\/', '/')
                if 'R$' in val or 'BRL' in val.upper():
                    m_val = re.search(r'([\d.,]+)', val)
                    if m_val: preco_web = f"R$ {m_val.group(1)}"
                    break
                elif re.match(r'^[\d.]+$', val):
                    preco_web = f"R$ {val.replace('.', ',')}"
                    break

        if preco_web == "Preço não informado":
            m_meta_p = re.search(r'<meta\s+property="(?:product|og):price:amount"\s+content="([^"]+)"', html)
            if m_meta_p:
                preco_web = f"R$ {m_meta_p.group(1).replace('.', ',')}"
    else:
        print("⚠️ Validador: O link não apresentou uma vitrine válida (sem título ou imagem de produto).")

    # ==========================================
    # 5. CONSOLIDAÇÃO INTELIGENTE DE DADOS
    # ==========================================
    # REGRA NOVA: Prioriza 100% o título GIGANTE oficial da web
    nome_final = nome_produto_web if nome_produto_web else nome_txt
    if not nome_final or len(nome_final) < 5:
        nome_final = "Oferta AliExpress"

    # DESCRIÇÃO: Guarda o texto limpo do seu post no Telegram
    desc_final = texto_limpo.strip() if texto_limpo.strip() else (nome_produto_web if nome_produto_web else nome_final)
    
    # PREÇO: Prioriza o que você digitou no post, senão pega o da loja
    preco_final = preco_txt if preco_txt != "Preço não informado" else preco_web

    # CHECAGEM FINAL DA IMAGEM
    if foto_url == "Imagem não encontrada" or not foto_url.startswith('http') or ('alicdn' not in foto_url and 'aliexpress-media' not in foto_url):
        foto_url = logo_fallback

    return {
        "loja": "Aliexpress",
        "nome_produto": nome_final[:255],
        "titulo_descricao": desc_final[:500],
        "preco": preco_final,
        "link_resolvido": link_final,
        "imagem": foto_url,
        "cupom": cupom
    }
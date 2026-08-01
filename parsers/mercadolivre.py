import re
import requests
from urllib.parse import unquote

def processar(texto, url_inicial):
    link_final = url_inicial.strip()
    logo_fallback = "https://cdn-icons-png.flaticon.com/512/732/732221.png"
    foto_url = "Imagem não encontrada"
    nome_produto_web = ""
    preco_web = "Preço não informado"
    
    # ==========================================
    # 1. EXTRAÇÃO DO TEXTO E CUPOM (TELEGRAM)
    # ==========================================
    cupom = ""
    match_cupom = re.search(r'(?i)(?:cupom|código|codigo|desconto)\s*[:=]?\s*([A-Za-z0-9_-]{3,25})', texto)
    if match_cupom:
        candidato = match_cupom.group(1).upper()
        if candidato not in ['MERCADO', 'ML', 'DESCONTO', 'OFF', 'FRETE']:
            cupom = candidato

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
    # 2. RASPAGEM LEVE COM REQUESTS (CRAWLER BINDING)
    # ==========================================
    html = ""
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)',
            'Accept-Language': 'pt-BR,pt;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        
        res = session.get(link_final, allow_redirects=True, timeout=10)
        link_final = res.url
        html = res.text
        
        # Fallback para Googlebot caso o Facebook seja desafiado
        if "captcha" in html.lower() or len(html) < 500:
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/W.X.Y.Z Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
            })
            res = session.get(link_final, allow_redirects=True, timeout=10)
            html = res.text
    except Exception as e:
        print(f"⚠️ Aviso Request Mercado Livre: {e}")

    # ==========================================
    # 3. EXTRATOR INTELIGENTE DE METADADOS
    # ==========================================
    if html:
        # --- TÍTULO ---
        og_t = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
        if og_t:
            candidato_t = unquote(og_t.group(1)).strip()
            if "minhas listas" not in candidato_t.lower() and len(candidato_t) > 3:
                nome_produto_web = candidato_t
        
        if not nome_produto_web:
            tag_title = re.search(r'<title>([^<]+)</title>', html)
            if tag_title:
                limpo = unquote(tag_title.group(1)).split('|')[0].split('-')[0].strip()
                if len(limpo) > 3 and "mercado livre" not in limpo.lower():
                    nome_produto_web = limpo

        # --- IMAGEM (PADRÃO OFICIAL WEBP / JPG) ---
        og_i = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
        if og_i:
            foto_url = og_i.group(1).replace('\\/', '/')
        else:
            m_img_web = re.search(r'(https?://http2\.mlstatic\.com/D_NQ_NP_(?:2X_)?[A-Za-z0-9_-]+\.(?:webp|jpg))', html)
            if m_img_web:
                foto_url = m_img_web.group(1).replace('\\/', '/')

        # --- PREÇO ---
        meta_p = re.search(r'<meta\s+property="(?:product|og):price:amount"\s+content="([^"]+)"', html)
        if meta_p:
            val = meta_p.group(1).replace('.', ',')
            preco_web = f"R$ {val}"
        else:
            fraction = re.search(r'<span[^>]*class="andes-money-amount__fraction"[^>]*>([\d.]+)</span>', html)
            if fraction:
                val_inteiro = fraction.group(1)
                cents = re.search(r'<span[^>]*class="andes-money-amount__cents"[^>]*>(\d+)</span>', html)
                centavos = cents.group(1) if cents else "00"
                preco_web = f"R$ {val_inteiro},{centavos}"

    # ==========================================
    # 4. CONSOLIDAÇÃO FINAL
    # ==========================================
    nome_final = nome_produto_web if nome_produto_web else (nome_txt if nome_txt else "Oferta Mercado Livre")
    
    desc_final = texto_limpo.strip() if texto_limpo.strip() else (nome_produto_web if nome_produto_web else nome_final)
    
    preco_final = preco_txt if preco_txt != "Preço não informado" else preco_web

    if foto_url == "Imagem não encontrada" or not foto_url.startswith('http') or 'mlstatic.com' not in foto_url:
        foto_url = logo_fallback

    return {
        "loja": "MercadoLivre",
        "nome_produto": nome_final[:255],
        "titulo_descricao": desc_final[:500],
        "preco": preco_final,
        "link_resolvido": link_final,
        "imagem": foto_url,
        "cupom": cupom
    }
import re
import requests
from urllib.parse import unquote

def processar(texto, url_inicial):
    link_final = url_inicial.strip()
    logo_fallback = "https://cdn-icons-png.flaticon.com/512/731/731985.png"
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
    # 2. RASPAGEM WEB NA AMAZON (COM DISFARCE)
    # ==========================================
    html = ""
    try:
        session = requests.Session()
        # Headers avançados para fingir ser um navegador Chrome real navegando no Brasil
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        res = session.get(link_final, allow_redirects=True, timeout=12)
        link_final = res.url
        html = res.text
    except Exception as e:
        print(f"⚠️ Aviso Web Amazon: {e}")

    # ==========================================
    # 3. EXTRATOR DE DADOS DA AMAZON
    # ==========================================
    if html:
        # --- TÍTULO ---
        og_t = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
        if og_t:
            nome_produto_web = unquote(og_t.group(1)).strip()
        else:
            # Fallback para a tag oficial de título de produto da Amazon
            span_t = re.search(r'<span\s+id="productTitle"[^>]*>([^<]+)</span>', html)
            if span_t:
                nome_produto_web = span_t.group(1).strip()

        # --- IMAGEM ---
        og_i = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
        if og_i:
            foto_url = og_i.group(1).replace('\\/', '/')
        else:
            # Fallback para imagem em alta resolução no JSON interno da Amazon
            dyn_img = re.search(r'"large":"(https://[^"]+\.jpg)"', html)
            if dyn_img:
                foto_url = dyn_img.group(1).replace('\\/', '/')

        # --- PREÇO WEB (Mapeamento de Múltiplas Classes da Amazon) ---
        padroes_preco_amazon = [
            r'<span[^>]*class="a-price-whole"[^>]*>([\d.,]+)</span>',  # Parte inteira do preço
            r'<span\s+id="priceblock_ourprice"[^>]*>R\$\s?([\d.,]+)</span>',
            r'<span\s+id="priceblock_dealprice"[^>]*>R\$\s?([\d.,]+)</span>',
            r'"priceAmount"\s*:\s*([\d.]+)'
        ]
        
        for padrao in padroes_preco_amazon:
            m_p = re.search(padrao, html)
            if m_p:
                val = m_p.group(1).strip().replace('.', '').replace(',', '')
                # Tenta capturar centavos se existir a classe a-price-fraction logo em seguida
                m_cent = re.search(r'class="a-price-fraction"[^>]*>(\d+)</span>', html)
                centavos = m_cent.group(1) if m_cent else "00"
                
                if len(val) <= 5 and not val.isdigit(): # Tratamento simples
                    pass
                else:
                    if len(val) > 2:
                        preco_web = f"R$ {val[:-2]},{val[-2:]}" if len(val) > 2 else f"R$ {val},{centavos}"
                    else:
                        preco_web = f"R$ {val},{centavos}"
                    break

        # Fallback genérico para preço na Amazon
        if preco_web == "Preço não informado":
            m_gen = re.search(r'R\$\s?(\d{1,3}(?:\.\d{3})*,\d{2})', html)
            if m_gen:
                preco_web = f"R$ {m_gen.group(1)}"

    # ==========================================
    # 4. CONSOLIDAÇÃO FINAL
    # ==========================================
    nome_final = nome_produto_web if nome_produto_web else (nome_txt if nome_txt else "Oferta Amazon")
    
    desc_final = texto_limpo.strip() if texto_limpo.strip() else (nome_produto_web if nome_produto_web else nome_final)
    
    preco_final = preco_txt if preco_txt != "Preço não informado" else preco_web

    if foto_url == "Imagem não encontrada" or not foto_url.startswith('http') or 'media-amazon.com' not in foto_url:
        foto_url = logo_fallback

    return {
        "loja": "Amazon",
        "nome_produto": nome_final[:255],
        "titulo_descricao": desc_final[:500],
        "preco": preco_final,
        "link_resolvido": link_final,
        "imagem": foto_url,
        "cupom": cupom
    }
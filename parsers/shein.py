import re
import requests
from bs4 import BeautifulSoup

def processar(texto, url_inicial):
    link_final = url_inicial
    foto_url = "https://upload.wikimedia.org/wikipedia/commons/0/0e/Shopee_logo.svg"
    
    cupom = ""
    match_cupom = re.search(r'(?i)(?:cupom|código|codigo)\s*[:=]\s*([A-Za-z0-9_-]{3,25})', texto)
    if match_cupom:
        c = match_cupom.group(1).upper()
        if c not in ['HTTP', 'HTTPS', 'WWW', 'COM', 'BR', 'NOSSA', 'SHOPEE']:
            cupom = c

    preco = "Preço não informado"
    m_preco = re.search(r'R\$\s?[\d.,]+', texto)
    if m_preco:
        preco = m_preco.group(0).rstrip(',')

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15'}
        res = requests.get(url_inicial, headers=headers, allow_redirects=True, timeout=8)
        link_final = res.url
        sopa = BeautifulSoup(res.text, 'html.parser')
        og_img = sopa.find('meta', property='og:image')
        if og_img and og_img.get('content') and og_img['content'].startswith('http'):
            foto_url = og_img['content']
    except:
        pass

    texto_limpo = re.sub(r'[^\w\s.,;:!?@#$%&*()\-+=\[\]{}<>/\'\"\\|]+', '', texto, flags=re.UNICODE)
    for l in re.findall(r'https?://[^\s<>"\']+', texto):
        texto_limpo = texto_limpo.replace(l, '')
        
    linhas = [l.strip() for l in texto_limpo.split('\n') if l.strip()]
    nome_produto = linhas[0] if linhas else "Oferta Shopee"

    return {
        "loja": "Shopee",
        "nome_produto": nome_produto[:255],
        "titulo_descricao": texto_limpo.strip(),
        "preco": preco,
        "link_resolvido": link_final,
        "imagem": foto_url,
        "cupom": cupom
    }
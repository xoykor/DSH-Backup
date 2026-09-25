#!/usr/bin/env python3
# Monta PDF multi-pagina a partir dos frames PNG capturados pelo capture.mjs.
# Uso: python3 assemble.py [DIR_PNGS] [SAIDA.pdf]. Sem args usa /tmp/prezi2pdf/pages e ./saida.pdf.
import sys, os, glob, json
from PIL import Image, ImageDraw

W, H = 1920, 1080          # canvas de captura do capture.mjs (present mode)
DPI = 100.0               # resolucao do PDF salvo

def die(msg):
    print('ERRO: '+msg, file=sys.stderr); sys.exit(1)

def order_pages(dir_pngs):
    # Ordem autoritativa vinda do capture.mjs (manifest.json em dir_pngs/.. ou em dir_pngs),
    # porque a captura pula frames duplicados/brancos e o indice nao fica contiguo.
    man = None
    for cand in (os.path.join(os.path.dirname(dir_pngs), 'manifest.json'),
                 os.path.join(dir_pngs, 'manifest.json')):
        if os.path.exists(cand):
            try:
                with open(cand) as f: man = json.load(f); break
            except Exception as e: die('manifest invalido '+cand+': '+str(e))
    if man and isinstance(man.get('pages'), list) and man['pages']:
        return [Image.open(os.path.join(dir_pngs, p['file'])) for p in man['pages']]
    # Fallback: ordenar por nome numérico zero-padded (000.png, 001.png...).
    files = [f for f in glob.glob(os.path.join(dir_pngs, '*.png'))
             if os.path.splitext(os.path.basename(f))[0].isdigit()]
    files.sort(key=lambda f: (int(os.path.splitext(os.path.basename(f))[0]), f))
    if not files: die('nenhum PNG encontrado em '+dir_pngs)
    return [Image.open(f) for f in files]

def fit_image(im):
    # Se ja e 1920x1080, usar como esta. Caso contrario, encaixar preservando proporcao
    # sobre fundo branco, centralizado (zoom do Prezi pode gerar tamanhos diferentes).
    if im.size == (W, H): return im.convert('RGB')
    src_w, src_h = im.size
    scale = min(W / src_w, H / src_h)
    nw, nh = max(1, int(round(src_w*scale))), max(1, int(round(src_h*scale)))
    resized = im.convert('RGB').resize((nw, nh), Image.LANCZOS)
    bg = Image.new('RGB', (W, H), (255, 255, 255))
    x0, y0 = (W-nw)//2, (H-nh)//2
    bg.paste(resized, (x0, y0))
    return bg

def add_label(page, num, total):
    # Rotorulo de numero da pagina no canto inferior-esquerdo.
    draw = ImageDraw.Draw(page)
    txt = 'Pagina %d / %d' % (num, total)
    bbox = draw.textbbox((0,0), txt)
    th = bbox[3]-bbox[1]
    px, py = 24-bbox[0], page.size[1]-bbox[3]-24
    draw.text((px, py), txt, fill=(40, 40, 40))

def main():
    dir_pngs = (sys.argv[1] if len(sys.argv)>1 else None) or os.environ.get('PREZI_PAGES') or '/tmp/prezi2pdf/pages'
    out_pdf = (sys.argv[2] if len(sys.argv)>2 else None) or os.environ.get('PREZI_OUT') or './saida.pdf'
    images = order_pages(dir_pngs)
    n = len(images)
    print('ASSEMBLING %d pages -> %s' % (n, out_pdf))
    if not n: die('nenhum frame para montar')
    out_parent = os.path.dirname(os.path.abspath(out_pdf))
    os.makedirs(out_parent, exist_ok=True)
    first = fit_image(images[0])
    add_label(first, 1, n)
    append = []                                          # restantes, redimensionadas se necessario
    for i in range(1, n):
        page = fit_image(images[i])
        add_label(page, i+1, n)
        append.append(page)
    first.save(out_pdf, save_all=True, append_images=append, resolution=DPI)
    print('OK %d pages @%g DPI -> %s' % (n, DPI, out_pdf))

if __name__ == '__main__':
    main()

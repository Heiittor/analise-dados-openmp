#!/usr/bin/env python3
"""PDF A4 com fontes TrueType incorporadas, texto Unicode e tabelas inteiras."""
from pathlib import Path
import argparse
import json
import re
from fontes_pdf import fontes, incorporar, PdfObjects

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 595.28, 841.89
LEFT, TOP, BOTTOM = 51, 789, 54
CONTENT_WIDTH = WIDTH - 2*LEFT
CAPACITY = TOP - BOTTOM


def literal(text):
    """Codigos CID Unicode BMP usados no conteudo textual do PDF."""
    return text.encode('utf-16-be').hex().upper().encode('ascii')


def clean(text):
    return re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text).replace('**', '').replace('`', '')


def measure(text, size, mono=False, bold=False):
    return fontes()['F3' if mono else ('F2' if bold else 'F1')].width(text,size)


def wrap(text, width, size, mono=False, bold=False):
    lines, current = [], ''
    for word in text.split():
        if current and measure(current+' '+word, size, mono,bold) > width:
            lines.append(current)
            current = ''
        while measure(word, size, mono,bold) > width:
            split = 1
            while split < len(word) and measure(word[:split+1], size, mono,bold) <= width:
                split += 1
            if current:
                lines.append(current)
                current = ''
            lines.append(word[:split])
            word = word[split:]
        if word:
            current = (current+' '+word).strip()
    if current or not lines:
        lines.append(current)
    return lines


def parse(markdown):
    lines, blocks, i = markdown.splitlines(), [], 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith('```'):
            content = []
            language = line[3:].strip()
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                content.append(lines[i])
                i += 1
            kind = {'math':'formula','identificacao':'identity'}.get(language,'code')
            blocks.append(dict(kind=kind, text=content))
            i += 1
        elif line.startswith('#'):
            blocks.append(dict(kind='heading', level=len(line)-len(line.lstrip('#')), text=clean(line.lstrip('# '))))
            i += 1
        elif line.startswith('|'):
            rows, aligns = [], []
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [clean(c.strip()) for c in lines[i].strip().strip('|').split('|')]
                if all(re.fullmatch(r':?-+:?', c) for c in cells):
                    aligns = ['right' if c.endswith(':') else 'left' for c in cells]
                else:
                    rows.append(cells)
                i += 1
            blocks.append(dict(kind='table', rows=rows, aligns=aligns))
        else:
            text = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].lstrip().startswith(('#', '|', '```', '- ')):
                text.append(lines[i].strip())
                i += 1
            blocks.append(dict(kind='paragraph', text=clean(' '.join(text))))
    return blocks


def prepare(block):
    b = dict(block)
    if b['kind'] == 'table':
        count = len(b['rows'][0])
        if not all(len(row) == count for row in b['rows']):
            raise ValueError('Tabela com quantidade irregular de colunas.')
        size, padding, leading = 9.2, 6, 12.1
        natural = [max(measure(row[j],size,bold=(i==0)) for i,row in enumerate(b['rows']))+2*padding for j in range(count)]
        natural = [max(40, n) for n in natural]
        widths = [CONTENT_WIDTH*n/sum(natural) for n in natural]
        cells = [[wrap(cell,width-2*padding,size,bold=(i==0)) for cell,width in zip(row,widths)] for i,row in enumerate(b['rows'])]
        heights = [max(map(len, row))*leading + 2*padding for row in cells]
        b.update(size=size, padding=padding, leading=leading, widths=widths, cells=cells,
                 row_heights=heights, height=sum(heights)+9)
    else:
        heading = b['kind'] == 'heading'
        panel = b['kind'] in ('code','formula','identity')
        size = (20 if b.get('level')==1 else (12.5 if b.get('level')==2 else 10.8)) if heading else {'code':8.6,'formula':12,'identity':9.5}.get(b['kind'],10.5)
        leading = 22 if b['kind']=='formula' else size+(4.3 if not heading else 4)
        padding = 10 if panel else 0
        raw = b['text'] if panel else [b['text']]
        rendered = []
        for line in raw:
            if b['kind'] == 'code':
                # Mantem espacos/indentacao e quebra comandos compridos.
                max_chars = int((CONTENT_WIDTH-2*padding)/measure('M',size,True))
                rendered.extend([line[j:j+max_chars] for j in range(0, len(line), max_chars)] or [''])
            else:
                rendered.extend(wrap(line,CONTENT_WIDTH-2*padding,size,bold=heading))
        b.update(size=size,leading=leading,lines=rendered,padding=padding,
                 height=len(rendered)*leading+2*padding+(9 if heading else 7))
    if b['height'] > CAPACITY:
        raise ValueError('Bloco maior que uma pagina; divida o conteudo explicitamente.')
    return b


def layout(markdown):
    blocks = [prepare(b) for b in parse(markdown)]
    groups, current = [], []
    for block in blocks:
        current.append(block)
        if block['kind'] != 'heading':
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    def paginate(limit):
        pages, page, used = [], [], 0
        for group in groups:
            height = sum(b['height'] for b in group)
            if height > CAPACITY:
                raise ValueError('Titulo e bloco seguinte nao cabem na mesma pagina.')
            if page and used+height > limit:
                pages.append(page)
                page, used = [], 0
            page.extend(group)
            used += height
        if page:
            pages.append(page)
        return pages
    pages = paginate(CAPACITY)
    if not pages:
        raise ValueError('Documento vazio.')
    # Minimiza a maior ocupacao mantendo o numero minimo de paginas obtido.
    # Assim o ultimo trecho nao vira uma pagina quase vazia.
    total = sum(b['height'] for b in blocks)
    low, high = total/len(pages), CAPACITY
    for _ in range(30):
        middle = (low+high)/2
        if len(paginate(middle)) <= len(pages): high = middle
        else: low = middle
    return paginate(high+0.01)


def converter(markdown, destino, layout_path=None):
    pages = layout(markdown)
    streams, audit = [], []
    def text_cmd(text, x, y, font, size):
        return f'BT /{font} {size:.2f} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm <'.encode()+literal(text)+b'> Tj ET\n'
    for number, blocks in enumerate(pages, 1):
        commands, y, page_tables = [b'0.13 0.16 0.20 rg\n'], TOP, []
        for b in blocks:
            if b['kind'] == 'table':
                page_tables.append(dict(cabecalho=b['rows'][0], linhas=len(b['rows']), conteudo=b['rows']))
                for row_index, (row, row_height) in enumerate(zip(b['cells'], b['row_heights'])):
                    x = LEFT
                    if row_index == 0:
                        commands.append(f'q 0.13 0.22 0.32 rg {LEFT} {y-row_height:.2f} {CONTENT_WIDTH:.2f} {row_height:.2f} re f Q\n'.encode())
                    for j, (cell, col_width) in enumerate(zip(row, b['widths'])):
                        commands.append(f'q 0.82 G 0.3 w {x:.2f} {y-row_height:.2f} {col_width:.2f} {row_height:.2f} re S Q\n'.encode())
                        font = 'F2' if row_index == 0 else 'F1'
                        commands.append(b'1 1 1 rg\n' if row_index==0 else b'0.13 0.16 0.20 rg\n')
                        for offset, line in enumerate(cell):
                            right = j < len(b['aligns']) and b['aligns'][j] == 'right'
                            tx = x+col_width-b['padding']-measure(line,b['size'],bold=(row_index==0)) if right else x+b['padding']
                            commands.append(text_cmd(line,tx,y-b['padding']-b['size']-offset*b['leading'],font,b['size']))
                        x += col_width
                    y -= row_height
                y -= 9
            else:
                font = 'F2' if b['kind'] == 'heading' else ('F3' if b['kind'] == 'code' else 'F1')
                padding=b['padding']
                if padding:
                    commands.append(f'q 0.96 0.97 0.98 rg {LEFT} {y-b["height"]+7:.2f} {CONTENT_WIDTH:.2f} {b["height"]-7:.2f} re f Q\n'.encode())
                commands.append(b'0.13 0.22 0.32 rg\n' if b['kind']=='heading' else b'0.13 0.16 0.20 rg\n')
                for offset, line in enumerate(b['lines']):
                    commands.append(text_cmd(line,LEFT+padding,y-padding-b['size']-offset*b['leading'],font,b['size']))
                y -= b['height']
        commands.append(f'q 0.82 G 0.4 w {LEFT} 40 m {WIDTH-LEFT:.2f} 40 l S Q\n'.encode())
        commands.append(b'0.35 0.39 0.43 rg\n')
        footer = f'IESB · Análise de Dados com OpenMP · {number}/{len(pages)}'
        commands.append(text_cmd(footer,LEFT,25,'F1',8))
        streams.append(b''.join(commands))
        audit.append(dict(pagina=number, altura_usada=round(TOP-y,2), altura_disponivel=CAPACITY, tabelas=page_tables))
    objects=PdfObjects()
    catalog=objects.add(b'')
    tree=objects.add(b'')
    # Somente caracteres efetivamente desenhados sao necessarios na fonte mono.
    used={key:set() for key in fontes()}
    for stream in streams:
        for key,text in re.findall(rb'/([F][123]) [\d.]+ Tf.*?<([0-9A-F]*)> Tj',stream):
            used[key.decode()].update(bytes.fromhex(text.decode()).decode('utf-16-be'))
    font_ids={key:incorporar(objects,font,used[key]) for key,font in fontes().items()}
    resource=' '.join(f'/{key} {value} 0 R' for key,value in font_ids.items())
    ids=[]
    for stream in streams:
        content=objects.stream(stream)
        ids.append(objects.add(f'<< /Type /Page /Parent {tree} 0 R /MediaBox [0 0 {WIDTH} {HEIGHT}] /Resources << /Font << {resource} >> >> /Contents {content} 0 R >>'.encode()))
    objects.items[catalog-1]=f'<< /Type /Catalog /Pages {tree} 0 R >>'.encode()
    objects.items[tree-1]=(f'<< /Type /Pages /Count {len(ids)} /Kids ['+' '.join(f'{i} 0 R' for i in ids)+'] >>').encode()
    output=objects.finish(catalog)
    destino = Path(destino)
    destino.parent.mkdir(parents=True,exist_ok=True)
    destino.write_bytes(output)
    if layout_path:
        Path(layout_path).write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
    return len(pages)


def extrair_texto_pdf(path):
    """Extrai os operadores textuais deste formato, validando o mapa ToUnicode."""
    data=Path(path).read_bytes()
    mappings=set(re.findall(rb'<([0-9A-F]{4})> <\1>',data))
    lines=[]
    for text in re.findall(rb'<([0-9A-F]+)> Tj',data):
        if any(text[i:i+4] not in mappings for i in range(0,len(text),4)):
            raise ValueError('Codigo textual sem correspondencia ToUnicode.')
        lines.append(bytes.fromhex(text.decode()).decode('utf-16-be'))
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entrada',type=Path,default=ROOT/'relatorio/relatorio_openmp.md')
    parser.add_argument('--saida',type=Path,default=ROOT/'relatorio/relatorio_openmp.pdf')
    args=parser.parse_args()
    count=converter(args.entrada.read_text(encoding='utf-8'),args.saida)
    print(f'PDF gerado: {args.saida}; {count} paginas.')


if __name__=='__main__': main()

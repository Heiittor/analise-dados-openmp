#!/usr/bin/env python3
"""PDF A4 sem dependencias: tabelas inteiras, titulos unidos ao texto e paginas equilibradas."""
from pathlib import Path
import argparse
import json
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 595.28, 841.89
LEFT, TOP, BOTTOM = 42, 798, 49
CONTENT_WIDTH = WIDTH - 2*LEFT
CAPACITY = TOP - BOTTOM


def literal(text):
    return text.encode('cp1252').replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')


def clean(text):
    return re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text).replace('**', '').replace('`', '')


def measure(text, size, mono=False):
    if mono:
        return len(text)*size*0.6
    units = 0
    for char in unicodedata.normalize('NFD', text):
        if unicodedata.combining(char):
            continue
        if char in 'ilI.,:;!|\'': units += 250
        elif char in 'frt()[]/ ': units += 320
        elif char in 'mwMW@%': units += 870
        elif char.isupper(): units += 690
        else: units += 560
    return units*size/1000


def wrap(text, width, size, mono=False):
    lines, current = [], ''
    for word in text.split():
        if current and measure(current+' '+word, size, mono) > width:
            lines.append(current)
            current = ''
        while measure(word, size, mono) > width:
            split = 1
            while split < len(word) and measure(word[:split+1], size, mono) <= width:
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
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                content.append(lines[i])
                i += 1
            blocks.append(dict(kind='code', text=content))
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
        size, padding, leading = 8.7, 5, 11.4
        natural = [max(measure(row[j], size) for row in b['rows'])+2*padding for j in range(count)]
        natural = [max(40, n) for n in natural]
        widths = [CONTENT_WIDTH*n/sum(natural) for n in natural]
        cells = [[wrap(cell, width-2*padding, size) for cell, width in zip(row, widths)] for row in b['rows']]
        heights = [max(map(len, row))*leading + 2*padding for row in cells]
        b.update(size=size, padding=padding, leading=leading, widths=widths, cells=cells,
                 row_heights=heights, height=sum(heights)+9)
    else:
        heading = b['kind'] == 'heading'
        size = (16 if b.get('level') == 1 else 11.5) if heading else (8.2 if b['kind'] == 'code' else 10)
        leading = size+3.2
        raw = b['text'] if b['kind'] == 'code' else [b['text']]
        rendered = []
        for line in raw:
            if b['kind'] == 'code':
                # Mantem espacos/indentacao e quebra comandos compridos.
                max_chars = int(CONTENT_WIDTH/(size*0.6))
                rendered.extend([line[j:j+max_chars] for j in range(0, len(line), max_chars)] or [''])
            else:
                rendered.extend(wrap(line, CONTENT_WIDTH, size))
        b.update(size=size, leading=leading, lines=rendered, height=len(rendered)*leading+(8 if heading else 6))
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
        return f'BT /{font} {size:.2f} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ('.encode()+literal(text)+b') Tj ET\n'
    for number, blocks in enumerate(pages, 1):
        commands, y, page_tables = [], TOP, []
        for b in blocks:
            if b['kind'] == 'table':
                page_tables.append(dict(cabecalho=b['rows'][0], linhas=len(b['rows']), conteudo=b['rows']))
                for row_index, (row, row_height) in enumerate(zip(b['cells'], b['row_heights'])):
                    x = LEFT
                    if row_index == 0:
                        commands.append(f'q 0.93 g {LEFT} {y-row_height:.2f} {CONTENT_WIDTH:.2f} {row_height:.2f} re f Q\n'.encode())
                    for j, (cell, col_width) in enumerate(zip(row, b['widths'])):
                        commands.append(f'q 0.76 G 0.4 w {x:.2f} {y-row_height:.2f} {col_width:.2f} {row_height:.2f} re S Q\n'.encode())
                        font = 'F2' if row_index == 0 else 'F1'
                        for offset, line in enumerate(cell):
                            right = j < len(b['aligns']) and b['aligns'][j] == 'right'
                            tx = x+col_width-b['padding']-measure(line,b['size']) if right else x+b['padding']
                            commands.append(text_cmd(line,tx,y-b['padding']-b['size']-offset*b['leading'],font,b['size']))
                        x += col_width
                    y -= row_height
                y -= 9
            else:
                font = 'F2' if b['kind'] == 'heading' else ('F3' if b['kind'] == 'code' else 'F1')
                for offset, line in enumerate(b['lines']):
                    commands.append(text_cmd(line,LEFT,y-b['size']-offset*b['leading'],font,b['size']))
                y -= b['height']
        footer = f'IESB | Analise de Dados com OpenMP | {number}/{len(pages)}'
        commands.append(text_cmd(footer,LEFT,27,'F1',8))
        streams.append(b''.join(commands))
        audit.append(dict(pagina=number, altura_usada=round(TOP-y,2), altura_disponivel=CAPACITY, tabelas=page_tables))
    ids = [6+2*i for i in range(len(pages))]
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Count '+str(len(pages)).encode()+b' /Kids ['+b' '.join(f'{i} 0 R'.encode() for i in ids)+b'] >>']
    for font in ['Helvetica','Helvetica-Bold','Courier']:
        objects.append(f'<< /Type /Font /Subtype /Type1 /BaseFont /{font} /Encoding /WinAnsiEncoding >>'.encode())
    for page_id, stream in zip(ids, streams):
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {WIDTH} {HEIGHT}] /Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> /Contents {page_id+1} 0 R >>'.encode())
        objects.append(f'<< /Length {len(stream)} >>\nstream\n'.encode()+stream+b'endstream')
    output, offsets = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'), [0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(output))
        output.extend(f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n')
    start = len(output)
    output.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]: output.extend(f'{offset:010} 00000 n \n'.encode())
    output.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode())
    for i,offset in enumerate(offsets[1:],1):
        if not output[offset:].startswith(f'{i} 0 obj\n'.encode()): raise ValueError('Offset PDF invalido.')
    destino = Path(destino)
    destino.parent.mkdir(parents=True,exist_ok=True)
    destino.write_bytes(output)
    if layout_path:
        Path(layout_path).write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
    return len(pages)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entrada',type=Path,default=ROOT/'relatorio/relatorio_openmp.md')
    parser.add_argument('--saida',type=Path,default=ROOT/'relatorio/relatorio_openmp.pdf')
    args=parser.parse_args()
    count=converter(args.entrada.read_text(encoding='utf-8'),args.saida)
    print(f'PDF gerado: {args.saida}; {count} paginas.')


if __name__=='__main__': main()

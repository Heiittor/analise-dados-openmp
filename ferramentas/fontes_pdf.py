"""Leitura de metricas/cmap TrueType e incorporacao Unicode, usando a biblioteca padrao.

As fontes sao lidas do sistema e incorporadas ao PDF; nao sao redistribuidas
como arquivos do projeto. fsType e conferido antes da incorporacao.
"""
from functools import lru_cache
from pathlib import Path
import os
import re
import struct
import zlib


class TrueType:
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        if self.data[:4] != b'\x00\x01\x00\x00':
            raise ValueError(f'Esperada fonte TrueType com contornos glyf: {path}')
        count = self.u16(4)
        self.tables = {self.data[12+i*16:16+i*16].decode('ascii'):
                       struct.unpack_from('>II', self.data, 20+i*16) for i in range(count)}
        head, hhea, os2 = (self.tables[tag][0] for tag in ['head', 'hhea', 'OS/2'])
        self.fs_type = self.u16(os2+8)
        if self.fs_type & (0x0002 | 0x0200):
            raise ValueError(f'Fonte nao permite esta incorporacao: {path}')
        self.units = self.u16(head+18)
        self.bbox = struct.unpack_from('>hhhh', self.data, head+36)
        self.ascent, self.descent = struct.unpack_from('>hh', self.data, hhea+4)
        hmtx = self.tables['hmtx'][0]
        self.advances = [self.u16(hmtx+4*i) for i in range(self.u16(hhea+34))]
        cmap = self.tables['cmap'][0]
        candidates = []
        for i in range(self.u16(cmap+2)):
            platform, encoding, offset = struct.unpack_from('>HHI', self.data, cmap+4+8*i)
            start = cmap+offset
            format_ = self.u16(start)
            if platform in (0, 3) and format_ in (4, 12):
                candidates.append((format_ == 12, platform == 3, start))
        if not candidates:
            raise ValueError(f'Fonte sem mapa Unicode suportado: {path}')
        self.cmap = max(candidates)[2]
        self.name = self.postscript_name()

    def u16(self, offset):
        return struct.unpack_from('>H', self.data, offset)[0]

    def postscript_name(self):
        start = self.tables['name'][0]
        strings = start+self.u16(start+4)
        for i in range(self.u16(start+2)):
            platform, _, _, name_id, length, offset = struct.unpack_from('>HHHHHH', self.data, start+6+i*12)
            if name_id == 6:
                value = self.data[strings+offset:strings+offset+length]
                text = value.decode('utf-16-be' if platform in (0, 3) else 'mac_roman')
                return re.sub(r'[^A-Za-z0-9_-]', '', text)
        return 'OpenMPFont'

    @lru_cache(maxsize=4096)
    def glyph(self, char):
        code, start = ord(char), self.cmap
        if code > 0xffff:
            raise ValueError('Este exportador suporta o plano Unicode BMP, incluindo portugues e formulas.')
        if self.u16(start) == 12:
            count = struct.unpack_from('>I', self.data, start+12)[0]
            for i in range(count):
                first, last, glyph = struct.unpack_from('>III', self.data, start+16+12*i)
                if first <= code <= last:
                    return glyph+code-first
        else:
            count = self.u16(start+6)//2
            ends = start+14
            starts = ends+2*count+2
            deltas = starts+2*count
            ranges = deltas+2*count
            for i in range(count):
                if self.u16(starts+2*i) <= code <= self.u16(ends+2*i):
                    delta = self.u16(deltas+2*i)
                    offset = self.u16(ranges+2*i)
                    if not offset:
                        return (code+delta) & 0xffff
                    value = self.u16(ranges+2*i+offset+2*(code-self.u16(starts+2*i)))
                    return (value+delta) & 0xffff if value else 0
        return 0

    def width(self, text, size):
        result = 0
        for char in text:
            glyph = self.glyph(char)
            if glyph == 0 and char != '\x00':
                raise ValueError(f'Caractere U+{ord(char):04X} ausente em {self.name}: {char!r}')
            result += self.advances[min(glyph, len(self.advances)-1)]
        return result*size/self.units


@lru_cache(maxsize=1)
def fontes():
    custom = os.environ.get('OPENMP_FONT_DIR')
    if custom:
        paths = [Path(custom)/name for name in ['regular.ttf', 'bold.ttf', 'mono.ttf']]
        if not all(p.is_file() for p in paths):
            raise FileNotFoundError('OPENMP_FONT_DIR deve conter regular.ttf, bold.ttf e mono.ttf.')
    else:
        families = [
            (Path(os.environ.get('SystemRoot', 'C:/Windows'))/'Fonts', ['arial.ttf', 'arialbd.ttf', 'consola.ttf']),
            (Path('/usr/share/fonts/truetype/dejavu'), ['DejaVuSans.ttf','DejaVuSans-Bold.ttf','DejaVuSansMono.ttf']),
            (Path('/usr/share/fonts/truetype/liberation2'), ['LiberationSans-Regular.ttf','LiberationSans-Bold.ttf','LiberationMono-Regular.ttf']),
        ]
        paths = next(([folder/name for name in names] for folder,names in families
                      if all((folder/name).is_file() for name in names)), None)
        if paths is None:
            raise FileNotFoundError('Instale fontes TrueType do sistema ou defina OPENMP_FONT_DIR; consulte o README.')
    return dict(zip(['F1','F2','F3'], map(TrueType, paths)))


class PdfObjects:
    def __init__(self):
        self.items = []

    def add(self, value):
        self.items.append(value)
        return len(self.items)

    def stream(self, value, compress=False, extra=''):
        data = zlib.compress(value, 9) if compress else value
        filter_ = '/Filter /FlateDecode ' if compress else ''
        return self.add(f'<< /Length {len(data)} {filter_}{extra}>>\nstream\n'.encode()+data+b'\nendstream')

    def finish(self, catalog):
        output = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
        offsets = [0]
        for i,item in enumerate(self.items,1):
            offsets.append(len(output))
            output.extend(f'{i} 0 obj\n'.encode()+item+b'\nendobj\n')
        start = len(output)
        output.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
        for offset in offsets[1:]:
            output.extend(f'{offset:010} 00000 n \n'.encode())
        output.extend(f'trailer\n<< /Size {len(offsets)} /Root {catalog} 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode())
        return bytes(output)


def incorporar(objects, font, characters):
    codes = sorted({ord(c) for c in characters} | {32})
    for code in codes:
        font.width(chr(code),10)  # Nao ocultar glifos ausentes.
    file_id = objects.stream(font.data, True, f'/Length1 {len(font.data)} ')
    scale = 1000/font.units
    bbox = ' '.join(str(round(n*scale)) for n in font.bbox)
    descriptor = objects.add((f'<< /Type /FontDescriptor /FontName /{font.name} /Flags 32 '
                              f'/FontBBox [{bbox}] /ItalicAngle 0 /Ascent {round(font.ascent*scale)} '
                              f'/Descent {round(font.descent*scale)} /CapHeight {round(font.ascent*scale)} '
                              f'/StemV 80 /FontFile2 {file_id} 0 R >>').encode())
    mapping = bytearray(2*(max(codes)+1))
    for code in codes:
        struct.pack_into('>H', mapping, 2*code, font.glyph(chr(code)))
    map_id = objects.stream(bytes(mapping),True)
    widths = ' '.join(f'{code} [{font.width(chr(code),1000):.3f}]' for code in codes)
    descendant = objects.add((f'<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{font.name} '
                              f'/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> '
                              f'/FontDescriptor {descriptor} 0 R /CIDToGIDMap {map_id} 0 R /DW 1000 /W [{widths}] >>').encode())
    cmap = ['/CIDInit /ProcSet findresource begin','12 dict begin','begincmap',
            '/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def',
            '/CMapName /OpenMPUnicode def','/CMapType 2 def','1 begincodespacerange','<0000> <FFFF>','endcodespacerange']
    for start in range(0,len(codes),100):
        chunk = codes[start:start+100]
        cmap += [f'{len(chunk)} beginbfchar']+[f'<{code:04X}> <{code:04X}>' for code in chunk]+['endbfchar']
    cmap += ['endcmap','CMapName currentdict /CMap defineresource pop','end','end']
    unicode_id = objects.stream('\n'.join(cmap).encode())
    return objects.add((f'<< /Type /Font /Subtype /Type0 /BaseFont /{font.name} /Encoding /Identity-H '
                        f'/DescendantFonts [{descendant} 0 R] /ToUnicode {unicode_id} 0 R >>').encode())

"""Regressoes de paginacao: tabela inteira, titulos unidos e paginas equilibradas."""
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ferramentas'))
from exportar_pdf import CAPACITY, CONTENT_WIDTH, converter, layout, literal, measure


class PdfTests(unittest.TestCase):
    def test_tabela_inteira_perto_da_quebra(self):
        text=('# Relatorio\n\n'+'Paragrafo de preenchimento para exercitar a paginacao. '*8+'\n\n')*8
        rows=['| Classe | Frequencia |','|---|---:|']+[f'| [{i},{i+1}) | {i} |' for i in range(17)]
        pages=layout(text+'\n## Tabela completa\n\n'+'\n'.join(rows))
        tables=[b for page in pages for b in page if b['kind']=='table']
        self.assertEqual(len(tables),1)
        self.assertEqual(len(tables[0]['rows']),18)
        for page in pages:
            self.assertLessEqual(sum(b['height'] for b in page),CAPACITY+0.01)

    def test_titulos_nao_ficam_sozinhos(self):
        pages=layout('\n\n'.join(f'## Secao {i}\n\n'+('Texto para verificar titulo e conteudo. '*12) for i in range(20)))
        self.assertTrue(all(page[-1]['kind']!='heading' for page in pages))

    def test_ultima_pagina_equilibrada(self):
        pages=layout('\n\n'.join('Texto para equilibrio das paginas. '*12 for _ in range(45)))
        used=[sum(b['height'] for b in page) for page in pages]
        self.assertGreaterEqual(used[-1],0.7*max(used))

    def test_pdf_valido_com_acentos_e_colunas_sem_extravasar(self):
        text='# Identificação acadêmica\n\nAluno(a): __________________\n\n| Estatística | Valor |\n|---|---:|\n| Média ponderada | 170.9760000000 |\n'
        pages=layout(text)
        table=next(b for page in pages for b in page if b['kind']=='table')
        self.assertAlmostEqual(sum(table['widths']),CONTENT_WIDTH)
        for row in table['cells']:
            for cell,width in zip(row,table['widths']):
                self.assertTrue(all(measure(line,table['size'])<=width-2*table['padding']+0.01 for line in cell))
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            path=Path(directory)/'relatorio.pdf'
            converter(text,path)
            data=path.read_bytes()
            self.assertTrue(data.startswith(b'%PDF-1.4'))
            self.assertIn(literal('Média ponderada'),data)
            offset=int(re.search(rb'startxref\n(\d+)',data)[1])
            self.assertTrue(data[offset:].startswith(b'xref\n'))


if __name__=='__main__': unittest.main(verbosity=2)

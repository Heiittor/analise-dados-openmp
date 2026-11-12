"""Regressoes do ciclo recompilar -> medir -> conferir. CSVs sinteticos apenas nas fixtures."""
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
import csv
import io
import json
import os
import subprocess
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ferramentas'))
from medicoes import sha, verificar_medicoes
from medir import medir


class MedicoesTests(unittest.TestCase):
    def setUp(self):
        # Pastas de fixtures sao preservadas em build/, sem excluir pastas existentes.
        self.root = ROOT/'build/regressao_medicoes'/uuid.uuid4().hex
        for folder in ['build','src','dados','resultados']:
            (self.root/folder).mkdir(parents=True)
        self.exe = self.root/('build/openmp_cv.exe' if os.name=='nt' else 'build/openmp_cv')
        self.exe.write_bytes(b'fixture: compilacao A')
        (self.root/'src/main.cpp').write_text('// fixture de teste\n')
        (self.root/'dados/dados_1000_pessoas.txt').write_text('170 70\n'*1000)
        (self.root/'resultados/ambiente.json').write_text('{"fixture_sintetica": true}')

    def processo_fixture(self,cmd,**kwargs):
        if '--benchmark' in cmd:
            folder = Path(cmd[cmd.index('--saida')+1])
            samples = int(cmd[cmd.index('--amostras')+1])
            repeats = int(cmd[cmd.index('--repeticoes')+1])
            with (folder/'benchmark.csv').open('w',newline='') as summary, (folder/'amostras.csv').open('w',newline='') as raw:
                a,b = csv.writer(summary),csv.writer(raw)
                a.writerow(['versao','threads_solicitadas','threads_reais','amostras','repeticoes','mediana_segundos','speedup','eficiencia'])
                b.writerow(['versao','threads_solicitadas','threads_reais','rodada','repeticoes','segundos_lote','segundos_processamento'])
                for version,requested,seconds,speedup in [('sequencial',0,0.01,1),('paralela',1,0.02,0.5)]:
                    a.writerow([version,requested,1,samples,repeats,seconds,speedup,speedup])
                    for round_ in range(1,samples+1):
                        b.writerow([version,requested,1,round_,repeats,seconds*repeats,seconds])
        return subprocess.CompletedProcess(cmd,0,'fixture sintetica, nao e medicao real\n','')

    def measure(self,process=None):
        with patch('medir.executar',side_effect=process or self.processo_fixture), redirect_stdout(io.StringIO()):
            return medir(self.root,10,100)

    def test_recompilacao_exige_nova_medicao_e_atualiza_hash(self):
        first = self.measure()
        self.exe.write_bytes(b'fixture: compilacao B')
        with self.assertRaisesRegex(ValueError,'sha256_executavel'):
            verificar_medicoes(self.root)
        second = self.measure()
        self.assertNotEqual(first['id_medicao'],second['id_medicao'])
        self.assertNotEqual(first['sha256_executavel'],second['sha256_executavel'])
        self.assertEqual(second['sha256_executavel'],sha(self.exe))
        self.assertEqual(verificar_medicoes(self.root)[2],second)

    def test_csv_nativo_novo_nao_autoriza_hash_antigo(self):
        self.measure()
        manifest = self.root/'resultados/benchmark_execucao.json'
        previous = manifest.read_bytes()
        (self.root/'resultados/benchmark.csv').write_text('CSV alterado por execucao nativa\n')
        with self.assertRaisesRegex(ValueError,'medir.py'):
            verificar_medicoes(self.root)
        self.assertEqual(previous,manifest.read_bytes())

    def test_executavel_alterado_durante_medicao_nao_e_publicado(self):
        self.measure()
        old = (self.root/'resultados/benchmark_execucao.json').read_bytes()
        def change(cmd,**kwargs):
            result = self.processo_fixture(cmd,**kwargs)
            if '--benchmark' in cmd: self.exe.write_bytes(b'alterado durante o processamento')
            return result
        with self.assertRaisesRegex(ValueError,'durante o benchmark'):
            self.measure(change)
        self.assertEqual(old,(self.root/'resultados/benchmark_execucao.json').read_bytes())

    def test_falha_do_programa_nao_substitui_conjunto_anterior(self):
        self.measure()
        files = ['benchmark.csv','amostras.csv','benchmark_execucao.json']
        before = {name:(self.root/'resultados'/name).read_bytes() for name in files}
        def fail(cmd,**kwargs):
            if '--benchmark' in cmd: raise RuntimeError('falha intencional da fixture')
            return self.processo_fixture(cmd,**kwargs)
        with self.assertRaisesRegex(RuntimeError,'falha intencional'):
            self.measure(fail)
        for name,data in before.items(): self.assertEqual(data,(self.root/'resultados'/name).read_bytes())
        self.assertFalse((self.root/'resultados/.medicao.lock').exists())

    def test_entrada_ambiente_e_fontes_tambem_sao_verificados(self):
        for name in ['dados/dados_1000_pessoas.txt','resultados/ambiente.json','src/main.cpp']:
            self.measure()
            path = self.root/name
            previous = path.read_bytes()
            path.write_bytes(previous+b'alteracao')
            with self.assertRaisesRegex(ValueError,'mudou desde a medicao'):
                verificar_medicoes(self.root)
            path.write_bytes(previous)

    def test_parametros_dos_csvs_devem_coincidir_com_a_execucao(self):
        meta = self.measure()
        different = dict(meta,parametros=dict(amostras=15,repeticoes=100))
        with self.assertRaisesRegex(ValueError,'Amostras divergem'):
            verificar_medicoes(self.root,meta=different)

    def test_relatorio_nao_le_conjunto_durante_publicacao(self):
        self.measure()
        (self.root/'resultados/.medicao.lock').write_text('fixture: processo em andamento')
        with self.assertRaisesRegex(ValueError,'medicao em andamento'):
            verificar_medicoes(self.root)

    def test_tempo_zero_nao_e_publicado(self):
        def zero(cmd,**kwargs):
            result = self.processo_fixture(cmd,**kwargs)
            if '--benchmark' in cmd:
                path = Path(cmd[cmd.index('--saida')+1])/'amostras.csv'
                with path.open(newline='') as stream:
                    reader = csv.DictReader(stream)
                    fields,rows = reader.fieldnames,list(reader)
                rows[0].update(segundos_lote='0',segundos_processamento='0')
                with path.open('w',newline='') as stream:
                    writer = csv.DictWriter(stream,fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(rows)
            return result
        with self.assertRaisesRegex(ValueError,'resolucao do cronometro'):
            self.measure(zero)
        self.assertFalse((self.root/'resultados/benchmark_execucao.json').exists())


if __name__=='__main__': unittest.main(verbosity=2)

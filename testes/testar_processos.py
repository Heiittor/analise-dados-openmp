"""Regressoes do diagnostico: falhas reais, timeout e status nativos Windows."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ferramentas'))
from processos import codigo_saida, executar


class ProcessosTests(unittest.TestCase):
    def test_sem_stderr_ainda_identifica_comando_e_retorno(self):
        cmd = [sys.executable, '-c', 'raise SystemExit(7)']
        with self.assertRaises(RuntimeError) as caught:
            executar(cmd, cwd=ROOT)
        message = str(caught.exception)
        for field in [str(sys.executable), str(ROOT), '7 (0x00000007)', 'stdout:', 'stderr:', '<vazio>']:
            self.assertIn(field, message)

    def test_preserva_ambas_saidas(self):
        cmd = [sys.executable, '-c', 'import sys; print("saida parcial"); print("causa interna", file=sys.stderr); sys.exit(3)']
        with self.assertRaises(RuntimeError) as caught:
            executar(cmd, cwd=ROOT)
        self.assertIn('saida parcial', str(caught.exception))
        self.assertIn('causa interna', str(caught.exception))

    def test_retorno_esperado_nao_aceita_qualquer_erro(self):
        executar([sys.executable, '-c', 'raise SystemExit(1)'], cwd=ROOT, esperado=1)
        with self.assertRaises(RuntimeError):
            executar([sys.executable, '-c', 'raise SystemExit(2)'], cwd=ROOT, esperado=1)

    def test_executavel_ausente(self):
        with self.assertRaisesRegex(RuntimeError, 'processo nao iniciou'):
            executar([ROOT / 'build/nao_existe_arquivo_123.exe'], cwd=ROOT)

    def test_timeout_tem_diagnostico(self):
        with self.assertRaisesRegex(RuntimeError, 'Codigo de saida: indisponivel.*timeout'):
            executar([sys.executable, '-c', 'import time; time.sleep(5)'], cwd=ROOT, timeout=0.1)

    def test_status_windows_signed_unsigned(self):
        for code in [0xC0000005, 0xC0000135, 0xC0000139]:
            self.assertEqual(codigo_saida(code).split(' ', 1)[1], codigo_saida(code - 2**32).split(' ', 1)[1])
        self.assertIn('STATUS_ENTRYPOINT_NOT_FOUND', codigo_saida(0xC0000139))

    def test_falha_encadeada_nao_perde_causa_interna(self):
        # Simula o gerador chamando um validador que termina com erro.
        code = ('import sys; sys.path.insert(0, "ferramentas"); from processos import executar; '
                'executar([sys.executable,"-c","import sys; print(\'falha do validador\',file=sys.stderr); sys.exit(9)"],cwd=".")')
        with self.assertRaises(RuntimeError) as caught:
            executar([sys.executable, '-c', code], cwd=ROOT)
        self.assertIn('falha do validador', str(caught.exception))
        self.assertIn('9 (0x00000009)', str(caught.exception))


if __name__ == '__main__':
    unittest.main(verbosity=2)

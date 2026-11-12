"""A auditoria deve recusar ausencia ou alteracao; nao integra o validador funcional."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from auditar_materiais import auditar

ROOT = Path(__file__).resolve().parents[1]


class AuditoriaTests(unittest.TestCase):
    def test_manifesto_ausente_falha(self):
        with self.assertRaises(FileNotFoundError):
            auditar(ROOT, ROOT / 'build/manifesto_ausente_123.json')

    def test_integridade_ausencia_e_alteracao(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build') as directory:
            root = Path(directory)
            item = root / 'material.txt'
            item.write_bytes(b'original')
            manifest = root / 'manifesto.json'
            hashes = {'material.txt': hashlib.sha256(b'original').hexdigest()}
            manifest.write_text(json.dumps(hashes))
            self.assertEqual(auditar(root, manifest), 1)
            item.write_bytes(b'alterado')
            with self.assertRaises(ValueError):
                auditar(root, manifest)
            hashes['ausente.txt'] = hashlib.sha256(b'original').hexdigest()
            item.write_bytes(b'original')
            manifest.write_text(json.dumps(hashes))
            with self.assertRaises(FileNotFoundError):
                auditar(root, manifest)

    def test_manifesto_vazio_falha(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build') as directory:
            manifest = Path(directory) / 'manifesto.json'
            manifest.write_text('{}')
            with self.assertRaises(ValueError):
                auditar(Path(directory), manifest)


if __name__ == '__main__':
    unittest.main(verbosity=2)

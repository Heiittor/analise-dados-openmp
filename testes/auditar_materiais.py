"""Auditoria historica opcional, separada dos testes funcionais do projeto."""
from pathlib import Path
import argparse
import hashlib
import json


def auditar(raiz, manifesto):
    hashes = json.loads(Path(manifesto).read_text(encoding='utf-8'))
    if not hashes:
        raise ValueError('Manifesto vazio nao constitui uma auditoria.')
    for relative, expected in hashes.items():
        path = Path(raiz) / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f'Integridade divergente: {relative}')
    return len(hashes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raiz-materiais', type=Path, required=True)
    parser.add_argument('--manifesto', type=Path, required=True)
    args = parser.parse_args()
    count = auditar(args.raiz_materiais, args.manifesto)
    print(f'PASSOU: auditoria explicita de {count} materiais historicos.')


if __name__ == '__main__':
    main()

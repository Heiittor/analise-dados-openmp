#!/usr/bin/env python3
"""Testes funcionais independentes; dados temporarios dentro de build/."""
from pathlib import Path
import hashlib
import math
import os
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ferramentas'))
from processos import diagnostico, executar
SUFFIX = '.exe' if os.name == 'nt' else ''
EXE = ROOT / f'build/openmp_cv{SUFFIX}'
passed = 0


def check(condition, message):
    global passed
    if not condition:
        raise AssertionError(message)
    passed += 1


def run(args, esperado=0, env=None):
    return executar([EXE, *args], cwd=ROOT, esperado=esperado, env=env)


def check_output(condition, result, message):
    check(condition, message + '\n' + diagnostico(result, ROOT))


def main():
    unit = executar([ROOT / f'build/testes{SUFFIX}', ROOT / 'dados/dados_1000_pessoas.txt'], cwd=ROOT)
    print(unit.stdout, end='')
    check_output(unit.returncode == 0, unit, 'Testes C++ falharam')
    oficial = ROOT / 'dados/dados_1000_pessoas.txt'
    check(hashlib.sha256(oficial.read_bytes()).hexdigest() ==
          '9ff5ae849aad828e5e00e6918fc8da5137d30d1fc6582da33d9ba32095bad0aa', 'Checksum da base')
    rows = [tuple(map(float, line.split())) for line in oficial.read_text().splitlines()]
    check(len(rows) == 1000 and all(len(r) == 2 and all(math.isfinite(x) and x > 0 for x in r) for r in rows), 'Formato da base')
    valid = run([oficial, '--threads', '1'])
    check_output(valid.returncode == 0, valid, 'Execucao normal falhou')
    expected = (ROOT / 'dados/VALIDACAO_BASE.txt').read_text(encoding='utf-8')
    check(hashlib.sha256((ROOT / 'dados/VALIDACAO_BASE.txt').read_bytes()).hexdigest() ==
          'fbd3c4fb27ffcc4701397e6051131ac05c935ed836ef13962823a1e933c95ef8',
          'Integridade da referencia estatistica')
    # Compara a saida real com as quatro estatisticas de cada bloco do TXT.
    for name, output_name in [('ESTATURA', 'ESTATURA'), ('PESO', 'PESO')]:
        block = expected.split(name + ' (AGRUPAD')[1].split('\n\n')[0]
        output = valid.stdout.split(output_name + ' (')[1].split('\n\n')[0]
        for reference_label, output_label in [('media ponderada', 'media'), ('variancia populacional', 'variancia_pop'),
                                               ('desvio padrao populacional', 'desvio_pop'), ('coeficiente de variacao', 'CV')]:
            ref = float(re.search(re.escape(reference_label) + r': ([\d.]+)', block)[1])
            actual = float(re.search(re.escape(output_label) + r'=([\d.]+)', output)[1])
            check_output(math.isclose(actual, ref, rel_tol=1e-10, abs_tol=1e-10), valid, f'{name} {output_label}')

    # Cada defeito deve ser recusado mesmo quando o arquivo tem 1000 linhas.
    bad_rows = ['texto 70', '170', '170 70 80', '170 70 lixo', '170 70#comentario', '170,5 70',
                '0 70', '-170 70', '170 0', '170 -70', 'nan 70', '170 nan',
                'inf 70', '170 inf', '1e309 70', '170 1e309']
    (ROOT / 'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='validacao_', dir=ROOT / 'build') as tmp:
        path = Path(tmp) / 'entrada.txt'
        cases = [('', 'vazio'), ('170 70\n'*999, '999 registros'), ('170 70\n'*1001, '1001 registros')]
        cases += [('170 70\n'*499 + bad + '\n' + '170 70\n'*500, bad) for bad in bad_rows]
        for content, label in cases:
            path.write_text(content, encoding='utf-8')
            result = run([path], esperado=1)
            check_output('Erro:' in result.stderr, result, 'Aceitou entrada: ' + label)
        path.write_text('\n\t\n' + '160 52\n'*1000 + '\n', encoding='utf-8')
        result = run([path])
        check_output(result.stdout.count('CV=0.0000000000 %') == 2, result, 'Linhas em branco/constantes')
        missing = run([Path(tmp) / 'ausente.txt'], esperado=1)
        check_output('Erro:' in missing.stderr, missing, 'Arquivo ausente')
    for args in [[], [oficial, '--nao-existe'], [oficial, '--threads'], [oficial, '--threads', '0'],
                 [oficial, '--threads', '-2'], [oficial, '--threads', '2x'], [oficial, '--amostras', '9'],
                 [oficial, '--repeticoes', '0'], [oficial, '--threads', '999999999999999999999']]:
        result = run(args, esperado=1)
        check_output('Erro:' in result.stderr, result, f'CLI aceitou {args}')
    help_result = run(['--help'])
    check_output('Uso:' in help_result.stdout, help_result, '--help')
    if os.name == 'nt':
        minimal = os.environ['SystemRoot'] + r'\System32'
        # Regressao: os executaveis devem funcionar sem GCC/Git no PATH.
        for binary, args, marker in [('verificar_openmp', [], 'soma=2'),
                                      ('openmp_cv', ['--help'], 'Uso:'),
                                      ('testes', ['dados/dados_1000_pessoas.txt'], 'PASSOU:')]:
            isolated = executar([ROOT / f'build/{binary}.exe', *args], cwd=ROOT,
                                 env={**os.environ, 'PATH': minimal})
            check_output(marker in isolated.stdout, isolated, 'Runtime local: ' + binary)
    print(f'PASSOU: {passed} verificacoes de integracao, alem dos testes C++.')


if __name__ == '__main__':
    main()

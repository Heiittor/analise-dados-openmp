#!/usr/bin/env python3
"""Compila os tres executaveis com o mesmo GCC e registra os comandos reais."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import shutil

from processos import executar

ROOT = Path(__file__).resolve().parents[1]
FLAGS = ['-std=c++17', '-O2', '-Wall', '-Wextra', '-Wpedantic', '-fopenmp']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx', default='g++')
    args = parser.parse_args()
    compiler = shutil.which(args.cxx)
    if not compiler:
        raise SystemExit('g++ ausente no PATH. Use --cxx /caminho/para/g++.')
    (ROOT / 'build').mkdir(exist_ok=True)
    (ROOT / 'resultados').mkdir(exist_ok=True)
    # No Git Bash, /mingw64/bin do Git precede o GCC no PATH. O compilador
    # e seus subprocessos devem usar o mesmo runtime, apenas neste processo.
    compiler_bin = Path(compiler).resolve().parent
    build_env = dict(os.environ)
    build_env['PATH'] = str(compiler_bin) + os.pathsep + build_env.get('PATH', '')
    suffix = '.exe' if os.name == 'nt' else ''
    commands = []
    for name, sources in [
        ('verificar_openmp', ['testes/verificar_openmp.cpp']),
        ('openmp_cv', ['src/main.cpp', 'src/analise.cpp']),
        ('testes', ['testes/testes.cpp', 'src/analise.cpp']),
    ]:
        cmd = [compiler, *FLAGS, *sources, '-o', f'build/{name}{suffix}']
        print(' '.join(cmd), flush=True)
        result = executar(cmd, cwd=ROOT, env=build_env)
        print(result.stdout, end='')
        print(result.stderr, end='')
        commands.append(cmd)
    runtime = {}
    if os.name == 'nt':
        # Copias locais prevalecem sobre o PATH do terminal. Todas vem do
        # mesmo GCC, inclusive dependencias transitivas (winpthread).
        for dll in ['libstdc++-6.dll', 'libgcc_s_seh-1.dll', 'libgomp-1.dll', 'libwinpthread-1.dll']:
            source = compiler_bin / dll
            if not source.is_file():
                raise FileNotFoundError(f'Runtime do compilador ausente: {source}')
            destination = ROOT / 'build' / dll
            shutil.copy2(source, destination)
            runtime[dll] = dict(origem=str(source), sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
    version = executar([compiler, '--version'], cwd=ROOT, env=build_env).stdout
    probe = executar([ROOT / f'build/verificar_openmp{suffix}'], cwd=ROOT).stdout
    executar([ROOT / f'build/openmp_cv{suffix}', '--help'], cwd=ROOT)
    cpu = platform.processor()
    if os.name == 'nt':
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
            cpu = winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
    environment = dict(sistema=platform.platform(), cpu=cpu, arquitetura=platform.machine(),
                       processadores_os=os.cpu_count(), compilador=version, flags=FLAGS,
                       comandos=commands, verificacao_openmp=probe, runtime_local=runtime,
                       variaveis_openmp={k: v for k, v in os.environ.items()
                                        if k.startswith(('OMP_', 'GOMP_'))})
    (ROOT / 'resultados/ambiente.json').write_text(json.dumps(environment, indent=2, ensure_ascii=False), encoding='utf-8')
    print(probe, end='')


if __name__ == '__main__':
    main()

"""Valida antes de medir e registra a origem das medicoes, sem tempos inventados."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import os
import sys
import uuid
from processos import executar
from medicoes import capturar_integridade, require, sha, verificar_medicoes

ROOT = Path(__file__).resolve().parents[1]


def medir(root, amostras, repeticoes):
    """Mede em pasta nova e publica o conjunto validado; nunca adota CSV preexistente."""
    root = Path(root)
    require(amostras >= 10 and repeticoes >= 1, 'Use pelo menos 10 amostras e uma repeticao.')
    results = root/'resultados'
    results.mkdir(exist_ok=True)
    lock = results/'.medicao.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError('Outra medicao esta em andamento (.medicao.lock).') from error
    os.close(fd)
    try:
        validation = executar([sys.executable, root/'testes/validar.py'], cwd=root)
        print(validation.stdout, end='', flush=True)
        exe = root/('build/openmp_cv.exe' if os.name == 'nt' else 'build/openmp_cv')
        before = capturar_integridade(root)
        run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:12]
        run_folder = results/'medicoes'/run_id
        run_folder.mkdir(parents=True)
        cmd = [exe, 'dados/dados_1000_pessoas.txt', '--benchmark', '--amostras',
               str(amostras), '--repeticoes', str(repeticoes), '--saida', run_folder]
        origin = dict(versao_formato=2, id_medicao=run_id,
                      pasta_medicao=run_folder.relative_to(root).as_posix(),
                      inicio_utc=datetime.now(timezone.utc).isoformat(), comando=list(map(str,cmd)),
                      diretorio=str(root), parametros=dict(amostras=amostras,repeticoes=repeticoes), **before)
        print('Validacao aprovada. Iniciando benchmark real...', flush=True)
        result = executar(cmd, cwd=root, timeout=600)
        after = capturar_integridade(root)
        require(before == after, 'Executavel, fontes, entrada ou ambiente mudou durante o benchmark; medicao rejeitada.')
        origin.update(fim_utc=datetime.now(timezone.utc).isoformat(), codigo_saida=result.returncode,
                      stdout=result.stdout, stderr=result.stderr, integridade_pos_execucao=after,
                      sha256_csv=sha(run_folder/'benchmark.csv'), sha256_amostras=sha(run_folder/'amostras.csv'))
        verificar_medicoes(root, run_folder, origin)
        (run_folder/'benchmark_execucao.json').write_text(json.dumps(origin,indent=2,ensure_ascii=False),encoding='utf-8')
        (run_folder/'execucao.txt').write_text(result.stdout,encoding='utf-8')
        # O manifesto e o ultimo arquivo publicado. Durante a publicacao, o
        # lock impede que o relatorio leia um conjunto parcialmente atualizado.
        # Se houver interrupcao, hashes divergentes continuam sendo rejeitados.
        for name in ['benchmark.csv','amostras.csv','execucao.txt','benchmark_execucao.json']:
            pending = results/(name+'.'+run_id+'.novo')
            pending.write_bytes((run_folder/name).read_bytes())
            os.replace(pending, results/name)
        print(result.stdout,end='')
        return origin
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--amostras', type=int, default=15)
    parser.add_argument('--repeticoes', type=int, default=1000)
    args = parser.parse_args()
    if args.amostras < 10 or args.repeticoes < 1:
        parser.error('Use pelo menos 10 amostras e uma repeticao.')
    medir(ROOT, args.amostras, args.repeticoes)


if __name__ == '__main__': main()

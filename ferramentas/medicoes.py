"""Conferencia de proveniencia e dos indicadores, compartilhada pela medicao e pelo relatorio."""
from pathlib import Path
import csv
import hashlib
import json
import math
import os
import statistics

ROOT = Path(__file__).resolve().parents[1]
ORIENTACAO = ('Execute novamente python ferramentas/medir.py --amostras 10 --repeticoes 1000 '
              'para medir o executavel atual e registrar CSVs e metadados juntos. '
              'O benchmark C++ direto gera somente CSVs; nao atualize hashes manualmente.')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def capturar_integridade(root):
    root = Path(root)
    exe = root / ('build/openmp_cv.exe' if os.name == 'nt' else 'build/openmp_cv')
    return dict(sha256_executavel=sha(exe),
                sha256_fontes={p.relative_to(root).as_posix(): sha(p)
                               for p in sorted((root/'src').glob('*')) if p.is_file()},
                sha256_entrada=sha(root/'dados/dados_1000_pessoas.txt'),
                sha256_ambiente=sha(root/'resultados/ambiente.json'))


def verificar_medicoes(raiz=None, pasta_resultados=None, meta=None):
    root = Path(raiz) if raiz is not None else ROOT
    results = Path(pasta_resultados) if pasta_resultados is not None else root/'resultados'
    if (root/'resultados/.medicao.lock').exists() and meta is None:
        raise ValueError('Ha uma medicao em andamento. Aguarde sua conclusao antes de gerar o relatorio.')
    if meta is None:
        try:
            meta = json.loads((results/'benchmark_execucao.json').read_text(encoding='utf-8'))
        except FileNotFoundError as error:
            raise ValueError('Metadados da medicao ausentes. '+ORIENTACAO) from error
    require(meta.get('versao_formato') == 2, 'Registro de medicao anterior ao fluxo consistente. '+ORIENTACAO)
    require(meta['codigo_saida'] == 0, 'Benchmark nao terminou com sucesso.')
    current = capturar_integridade(root)
    for key, actual in current.items():
        require(actual == meta[key], f'Arquivo mudou desde a medicao ({key}). '+ORIENTACAO)
    require(current == meta['integridade_pos_execucao'], 'Integridade mudou durante a medicao. '+ORIENTACAO)
    for name, key in [('benchmark.csv','sha256_csv'), ('amostras.csv','sha256_amostras')]:
        require(sha(results/name) == meta[key], f'Arquivo mudou desde a medicao: {results/name}. '+ORIENTACAO)

    def ler_csv(name):
        with (results/name).open(encoding='utf-8', newline='') as stream:
            return list(csv.DictReader(stream))

    summaries, samples = ler_csv('benchmark.csv'), ler_csv('amostras.csv')
    require(bool(summaries) and summaries[0]['versao']=='sequencial', 'Falta referencia sequencial.')
    base = float(summaries[0]['mediana_segundos'])
    require(math.isfinite(base) and base>0, 'Tempo sequencial invalido.')
    seen = set()
    for config in summaries:
        key = (config['versao'],config['threads_solicitadas'])
        require(key not in seen, 'Configuracao duplicada.')
        seen.add(key)
        matching = [s for s in samples if (s['versao'],s['threads_solicitadas'])==key]
        times = [float(s['segundos_processamento']) for s in matching]
        require(len(times)==int(config['amostras'])>=10, 'Quantidade de amostras invalida.')
        require(int(config['amostras']) == meta['parametros']['amostras'], 'Amostras divergem do comando executado.')
        require(int(config['repeticoes']) == meta['parametros']['repeticoes'], 'Repeticoes divergem do comando executado.')
        require({int(s['rodada']) for s in matching} == set(range(1,len(times)+1)), 'Rodadas invalidas ou repetidas.')
        require(int(config['threads_reais'])>=1 and int(config['repeticoes'])>=1, 'Contagem invalida.')
        for s,t in zip(matching,times):
            require(math.isfinite(t) and t>0,
                    'Tempo invalido ou abaixo da resolucao do cronometro. Repita a medicao com mais repeticoes (por exemplo, --repeticoes 1000).')
            require(s['threads_reais']==config['threads_reais'] and s['repeticoes']==config['repeticoes'], 'Configuracao inconsistente.')
            require(math.isclose(float(s['segundos_lote'])/int(s['repeticoes']),t,rel_tol=1e-12), 'Normalizacao incorreta.')
        med = statistics.median(times)
        require(math.isclose(med,float(config['mediana_segundos']),rel_tol=1e-12), 'Mediana divergente.')
        require(math.isclose(base/med,float(config['speedup']),rel_tol=1e-12), 'Speedup divergente.')
        require(math.isclose(base/med/int(config['threads_reais']),float(config['eficiencia']),rel_tol=1e-12), 'Eficiencia divergente.')
    require(len(samples)==sum(int(s['amostras']) for s in summaries), 'Amostras sem configuracao.')
    require(len({c['repeticoes'] for c in summaries})==1, 'Repeticoes desiguais.')
    return summaries,samples,meta

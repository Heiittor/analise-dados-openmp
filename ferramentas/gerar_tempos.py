"""Gera uma visualizacao CSV da medicao validada, sem executar o benchmark."""
from pathlib import Path
import csv

from medicoes import verificar_medicoes

ROOT = Path(__file__).resolve().parents[1]


def main():
    summary, samples, meta = verificar_medicoes(ROOT)
    ordered = sorted(summary, key=lambda row: (row['versao'] != 'sequencial', int(row['threads_reais'])))
    versions = {'sequencial': 'Sequencial', 'paralela': 'Paralela'}
    rows = [[versions[row['versao']], int(row['threads_reais']),
             f"{float(row['mediana_segundos'])*1_000_000:.3f}",
             f"{float(row['speedup']):.6f}"] for row in ordered]
    destination = ROOT/'resultados/tempos.csv'
    with destination.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Versão', 'Threads', 'Mediana por processamento (µs)', 'Speedup'])
        writer.writerows(rows)
    print(f"Medicao {meta['id_medicao']}: {len(samples)} amostras verificadas.")
    print('Versao | Threads | Mediana (us) | Speedup')
    for row in rows:
        print(' | '.join(map(str, row)))
    print(f'Tabela gerada: {destination}')


if __name__ == '__main__':
    main()

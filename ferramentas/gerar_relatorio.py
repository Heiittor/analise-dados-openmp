#!/usr/bin/env python3
"""Confere a origem dos resultados, revalida o projeto e gera Markdown/PDF."""
from pathlib import Path
import argparse
from datetime import datetime, timezone, timedelta
import json
import os
import re
import sys
from exportar_pdf import converter
from processos import executar
from medicoes import verificar_medicoes

ROOT=Path(__file__).resolve().parents[1]



def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--usar-registros',action='store_true',help='Revisa somente os documentos usando os registros existentes; mantem a verificacao de hashes.')
    args=parser.parse_args()
    summaries,samples,meta=verificar_medicoes()
    environment=json.loads((ROOT/'resultados/ambiente.json').read_text(encoding='utf-8'))
    if args.usar_registros:
        logs=json.loads((ROOT/'resultados/testes.json').read_text(encoding='utf-8'))
        if not logs or any(item['codigo_saida']!=0 for item in logs):
            raise ValueError('Os registros existentes devem comprovar testes aprovados.')
        output=(ROOT/'resultados/estatisticas.txt').read_text(encoding='utf-8')
    else:
        logs=[]
        for name in ['validar.py','testar_processos.py','testar_auditoria.py','testar_pdf.py','testar_medicoes.py']:
            result=executar([sys.executable,ROOT/'testes'/name],cwd=ROOT)
            logs.append(dict(teste=name,codigo_saida=result.returncode,stdout=result.stdout,stderr=result.stderr))
        (ROOT/'resultados/testes.json').write_text(json.dumps(logs,indent=2,ensure_ascii=False),encoding='utf-8')
        exe=ROOT/('build/openmp_cv.exe' if os.name=='nt' else 'build/openmp_cv')
        output=executar([exe,'dados/dados_1000_pessoas.txt','--threads','1'],cwd=ROOT).stdout
        (ROOT/'resultados/estatisticas.txt').write_text(output,encoding='utf-8')
    logtext='\n'.join(f"{item['teste']}: retorno {item['codigo_saida']}\n{item['stdout']}{item['stderr']}" for item in logs)
    if not args.usar_registros:
        (ROOT/'resultados/testes.txt').write_text(logtext,encoding='utf-8')
    probe=environment['verificacao_openmp']
    available=int(re.search(r'processadores=(\d+)',probe)[1])
    # Conferir os valores registrados antes de usa-los na revisao documental.
    expected=(ROOT/'dados/VALIDACAO_BASE.txt').read_text(encoding='utf-8')
    for label,section in [('ESTATURA','AGRUPADA'),('PESO','AGRUPADO')]:
        reference=expected.split(label+' ('+section+')')[1].split('\n\n')[0]
        block=output.split(label+' (')[1].split('\n\n')[0]
        for a,b in [('media ponderada','media'),('variancia populacional','variancia_pop'),('desvio padrao populacional','desvio_pop'),('coeficiente de variacao','CV')]:
            value=float(re.search(re.escape(a)+r': ([\d.]+)',reference)[1])
            actual=float(re.search(re.escape(b)+r'=([\d.]+)',block)[1])
            if abs(value-actual)>1e-10+1e-10*max(abs(value),abs(actual)):
                raise ValueError('Estatistica registrada diverge da referencia: '+label+' '+b)
    blocks={name:output.split(name+' (')[1].split('\n\n')[0] for name in ['ESTATURA','PESO']}
    values={name:{key:re.search(re.escape(key)+r'=([\d.]+)',block)[1] for key in ['media','variancia_pop','desvio_pop','CV']}
            for name,block in blocks.items()}
    class_tables=[]
    for name,block in blocks.items():
        unit='cm' if name=='ESTATURA' else 'kg'
        table=[f'### {name.title()} ({unit})', '', '| Intervalo [a, b) | Ponto médio xᵢ | Frequência fᵢ |','|---|---:|---:|']
        table.extend('| '+line+' |' for line in block.splitlines() if line.startswith('['))
        class_tables.append('\n'.join(table))
    rows=[]
    for config in summaries:
        rows.append(f"| {config['versao']} | {config['threads_reais']} | {1e6*float(config['mediana_segundos']):.3f} | {float(config['speedup']):.6f} | {100*float(config['eficiencia']):.4f} |")
    best=min(summaries,key=lambda c:float(c['mediana_segundos']))
    observed=datetime.fromisoformat(meta['fim_utc']).astimezone(timezone(timedelta(hours=-3))).strftime('%d/%m/%Y %H:%M -03:00')
    n_samples,repetitions=summaries[0]['amostras'],summaries[0]['repeticoes']
    e,p=values['ESTATURA'],values['PESO']
    comparisons=re.search(r'(\d+) comparacoes',logs[0]['stdout'])[1]
    parallel=[c for c in summaries if c['versao']=='paralela']
    observation=('Todas as configurações paralelas tiveram mediana maior que a sequencial.'
                 if all(float(c['speedup'])<1 for c in parallel) else
                 'Houve configuração paralela com tempo igual ou inferior ao sequencial; os valores medidos constam da tabela.')
    report=f"""# Análise de Dados com OpenMP

Coeficiente de variação para estatura e peso em dados agrupados

```identificacao
Instituição: IESB · Curso: Ciência da Computação
Aluno: Heitor Ribeiro · Matrícula: 2412130143
Disciplina: Programação Paralela · Turma: __________________
Professor: Rodrigo Gonçalves Pinto
```

Medição analisada: {observed} · Dados sintéticos · N = 1.000.

## 1. Objetivo e conjunto de dados

O exercício propõe calcular os coeficientes de variação da estatura e do peso
de 1.000 pessoas, usando dados agrupados e OpenMP. Foram implementadas duas
rotas completas em C++17: uma sequencial e outra paralela, com conferência
de corretude e comparação dos tempos de processamento.

A base é inteiramente sintética, gerada com semente 20261112. Cada linha
contém estatura em centímetros e peso em quilogramas, sem cabeçalho.
Os primeiros dez pares incluem fronteiras exatas das classes. A base não
representa uma coleta de pessoas reais nem permite inferências demográficas.

## 2. Agrupamento e definição das estatísticas

O enunciado fixa amplitudes de 8 cm para estatura e 4 kg para peso, sem
determinar a origem. Adotou-se início = floor(mínimo/amplitude) × amplitude,
separadamente para cada variável. As classes são semiabertas [a, b): um
valor igual a b pertence à classe seguinte. O ponto médio é xᵢ = a + amplitude/2.

Se fᵢ é a frequência da classe i e k é o número de classes, então
N = Σᵢ fᵢ. Para i = 1, …, k, calculam-se a média agrupada μ, a variância
populacional σ², o desvio padrão σ e o coeficiente de variação percentual:

```math
μ = [Σᵢ (xᵢ × fᵢ)] / N
σ² = [Σᵢ fᵢ × (xᵢ − μ)²] / N
σ = √(σ²)
CV (%) = 100 × σ / μ
```

A variância usa divisor N. A média é ponderada pelos pontos médios e
frequências, em vez de ser a média dos valores individuais. Utilizam-se
duas passadas: a variância depende da média já concluída. Esse método evita
a subtração de termos próximos da expressão alternativa E[X²] − E[X]².

### Distribuições de frequência

A estatura observada varia de 145,0 a 199,9 cm, em sete classes com origem
em 144 cm. O peso varia de 44,0 a 109,5 kg, em 17 classes com origem em 44 kg.
As duas somas de frequências são exatamente 1.000. As tabelas são extraídas
da saída C++; nelas, mantém-se o ponto como separador decimal.

{chr(10).join(class_tables)}

## 3. Implementação e paralelização

A rota sequencial executa extremos, construção de classes, frequências e
estatísticas sem chamadas OpenMP no processamento. A rota paralela realiza
o mesmo trabalho lógico com as estratégias resumidas a seguir.

| Etapa | Estratégia OpenMP e segurança |
|---|---|
| Extremos | parallel for com reduction(min:...) e reduction(max:...). |
| Pontos médios | parallel for schedule(static), com um escritor por posição. |
| Frequências | Histograma privado por thread; combinação por classe após barreira. |
| Média | parallel for reduction(+:soma_ponderada), acumulando xᵢ × fᵢ. |
| Variância | Segunda redução, acumulando fᵢ × (xᵢ − μ)² com μ já concluída. |

Os dados de entrada são somente lidos pelas threads. Os histogramas privados
evitam incrementos concorrentes na mesma frequência, e as reduções combinam
acumuladores locais. Não se usa critical ou atomic por registro. As barreiras
garantem as dependências; schedule(static) é adequado ao custo uniforme das
iterações. Não há paralelismo aninhado nem divisão manual por IDs fixos.

Cada processamento das duas variáveis abre dez regiões paralelas. O ajuste
dinâmico é desativado e o número real de threads é consultado dentro da equipe.

## 4. Resultados estatísticos

| Estatística | Estatura | Peso |
|---|---:|---:|
| Média agrupada | {e['media']} cm | {p['media']} kg |
| Variância populacional | {e['variancia_pop']} cm² | {p['variancia_pop']} kg² |
| Desvio padrão populacional | {e['desvio_pop']} cm | {p['desvio_pop']} kg |
| CV | {e['CV']}% | {p['CV']}% |

Os resultados conferem com a referência estatística fornecida. Frequências,
limites e pontos médios coincidem exatamente entre as versões; as estatísticas
são comparadas com tolerâncias absoluta e relativa de 1e-10. O executável
calcula a partir do TXT, sem ler valores esperados. O peso apresenta maior
dispersão relativa neste conjunto sintético agrupado.

## 5. Comparação de desempenho

### Ambiente e método

Ambiente: {environment['sistema']}; CPU {environment['cpu']}; {available}
processadores lógicos. Compilador: {environment['compilador'].splitlines()[0]}.

```text
Flags: {' '.join(environment['flags'])}
```

Há cinco processamentos de aquecimento por configuração, fora do cronômetro.
O benchmark usa omp_get_wtime na thread principal, com {n_samples} amostras de
{repetitions} processamentos completos por configuração. Divide-se cada lote por
{repetitions} para obter o tempo por processamento. Mantêm-se os mesmos 1.000 pares
e o mesmo número de repetições em todas as versões. A ordem das configurações
alterna a cada rodada, e a corretude é conferida após cada amostra.

O tempo inclui extremos, classes e suas alocações, histogramas, conferência
dos totais, estatísticas das duas variáveis e liberação dos resultados.
Inclui-se um pequeno checksum volatile comum às rotas para tornar a computação
observável; não se usa LTO. Leitura de disco, impressão, testes e escrita dos
CSVs ficam fora da medição. A rota OpenMP com uma thread é medida separadamente
da versão sequencial real.

```math
Speedup = mediana sequencial / mediana paralela
Eficiência = speedup / número real de threads
```

### Tempos observados e interpretação

Medianas por processamento completo, em microssegundos (µs). A eficiência
é expressa em percentual. Todos os valores provêm da mesma medição registrada.

| Versão | Threads | Mediana (µs) | Speedup | Eficiência (%) |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

{observation} A versão {best['versao']} apresentou a menor mediana.
Para esta entrada pequena, os custos de regiões paralelas, barreiras,
reduções e combinação dos histogramas superam o trabalho distribuído.
Os laços estatísticos têm apenas sete e 17 classes. Essa interpretação
explica os tempos completos; os custos individuais não foram medidos separadamente.

Não se fixou afinidade nem se controlou exclusivamente carga, temperatura ou
política de energia. O escalonamento da CPU híbrida pode variar. Os resultados
descrevem esta execução, sem generalização para outras máquinas. Não se aumentou
N artificialmente para buscar ganho; repetir a mesma base não amplia cada processamento.

## 6. Validação, rastreabilidade e conclusão

O caso manual de estaturas [145, 145, 153, 169] produz pontos médios
[148, 156, 164, 172], frequências [2, 1, 0, 1], média 156 e variância 96.
Os testes também cobrem fronteiras exatas e valores adjacentes em double,
classes vazias, N = 1, dados constantes e fronteira como máximo.
Foram registradas {comparisons} comparações sequencial/paralela e 47 verificações
funcionais, incluindo entradas inválidas e a integridade da base e da referência.

No Windows, os testes verificam ainda os runtimes locais e o início dos
executáveis com PATH restrito ao sistema. Os scripts de diagnóstico propagam
códigos de saída e mensagens completas. Os registros detalhados ficam em
resultados/testes.json; a auditoria histórica permanece separada dos testes funcionais.

As {len(samples)} amostras individuais e as medianas estão em resultados/amostras.csv
e resultados/benchmark.csv. O registro benchmark_execucao.json associa a
execução ao executável, às fontes, à entrada e ao ambiente por hashes,
conferidos antes e depois da medição. O relatório recalcula os indicadores
dos CSVs e rejeita registros divergentes. A revisão documental preserva essa
medição e não executa um benchmark novo.

Conclui-se que os CVs são {e['CV']}% para estatura e {p['CV']}% para peso.
A implementação cumpre o agrupamento e a paralelização solicitados com
verificação de corretude. A versão sequencial foi mais rápida no conjunto
analisado, evidenciando que paralelizar uma carga pequena não garante ganho.

## 7. Reprodução

No Git Bash, na raiz do repositório:

```bash
python -B ferramentas/compilar.py
./build/openmp_cv.exe dados/dados_1000_pessoas.txt --threads 4
python -B testes/validar.py
python -B ferramentas/medir.py --amostras {n_samples} --repeticoes {repetitions}
python -B ferramentas/gerar_relatorio.py
```

Para revisar somente os documentos, preservando a medição atual:

```bash
python -B ferramentas/gerar_relatorio.py --usar-registros
```

O README apresenta todos os testes, as dependências e o procedimento Windows.
O C++ direto produz somente CSVs; medir.py registra também os metadados de
integridade necessários ao relatório. Fontes TrueType do sistema são
incorporadas ao PDF; não são necessários pacotes Python adicionais.

## Referências bibliográficas

PINTO, Rodrigo Gonçalves. Exercício Final: Análise de Dados com OpenMP.
IESB, 28 out. 2025. Enunciado acadêmico fornecido pelo professor, duas páginas.

PINTO, R. G. Parallel Programming Examples in C++ using OpenMP. 2025.
Material didático fornecido pelo professor: ambiente (001), laços (004),
tempo e barreiras (005), sincronização (006), reduções e duas passadas (007)
e tarefas (008). As técnicas foram estudadas e a solução foi escrita para
este exercício. Os materiais são referências bibliográficas, sem constituir
dependências da entrega independente.
"""
    folder=ROOT/'relatorio'
    folder.mkdir(exist_ok=True)
    (folder/'relatorio_openmp.md').write_text(report,encoding='utf-8')
    pages=converter(report,folder/'relatorio_openmp.pdf',ROOT/'resultados/diagrama_pdf.json')
    if args.usar_registros:
        print('Integridade e registros existentes conferidos; sem recompilacao ou nova medicao.')
    else:
        print(logtext)
    print(f'Conferidas {len(samples)} amostras; relatorio Markdown/PDF gerado com {pages} paginas.')


if __name__=='__main__': main()

#!/usr/bin/env python3
"""Confere a origem dos resultados, revalida o projeto e gera Markdown/PDF."""
from pathlib import Path
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
    summaries,samples,meta=verificar_medicoes()
    environment=json.loads((ROOT/'resultados/ambiente.json').read_text(encoding='utf-8'))
    logs=[]
    for name in ['validar.py','testar_processos.py','testar_auditoria.py','testar_pdf.py','testar_medicoes.py']:
        result=executar([sys.executable,ROOT/'testes'/name],cwd=ROOT)
        logs.append(dict(teste=name,codigo_saida=result.returncode,stdout=result.stdout,stderr=result.stderr))
    (ROOT/'resultados/testes.json').write_text(json.dumps(logs,indent=2,ensure_ascii=False),encoding='utf-8')
    logtext='\n'.join(f"{r['teste']}: retorno {r['codigo_saida']}\n{r['stdout']}{r['stderr']}" for r in logs)
    (ROOT/'resultados/testes.txt').write_text(logtext,encoding='utf-8')
    exe=ROOT/('build/openmp_cv.exe' if os.name=='nt' else 'build/openmp_cv')
    probe=environment['verificacao_openmp']
    available=int(re.search(r'processadores=(\d+)',probe)[1])
    limit=int(re.search(r'thread_limit=(\d+)',probe)[1])
    threads=min(4,available,limit)
    output=executar([exe,'dados/dados_1000_pessoas.txt','--threads',str(threads)],cwd=ROOT).stdout
    (ROOT/'resultados/estatisticas.txt').write_text(output,encoding='utf-8')
    blocks={name:output.split(name+' (')[1].split('\n\n')[0] for name in ['ESTATURA','PESO']}
    values={name:{key:re.search(re.escape(key)+r'=([\d.]+)',block)[1] for key in ['media','variancia_pop','desvio_pop','CV']}
            for name,block in blocks.items()}
    class_tables=[]
    for name,block in blocks.items():
        table=[f'### {name}', '', '| Classe | Ponto médio | Frequência |','|---|---:|---:|']
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

Coeficiente de variação para dados agrupados - Projeto acadêmico

Instituição: IESB | Curso: Ciência da Computação

Aluno(a): Heitor Ribeiro | Matrícula: 2412130143

Disciplina: Programação Paralela | Turma: _____________________

Professor: Rodrigo Gonçalves Pinto

Data da medição: {observed} (America/Sao_Paulo)

## 1. Objetivo, dados e convenção

Calcular média ponderada, desvio padrão populacional e coeficiente de variação
(CV) da estatura e do peso, agrupando 1.000 registros e comparando versões
sequencial e paralela em C++17/OpenMP. O conjunto é inteiramente sintético,
gerado com semente 20261112; não representa coleta de pessoas reais.
O TXT contém estatura em centímetros e peso em quilogramas, sem cabeçalho,
com espaço entre colunas e ponto decimal. Os primeiros dez pares incluem
fronteiras exatas de classes.

O enunciado estabelece amplitudes de 8 cm e 4 kg, mas não fixa a origem.
Adotou-se início=floor(mínimo/amplitude)*amplitude. As classes são [a,b):
valores iguais a b pertencem à classe seguinte. O ponto médio é xi=a+amplitude/2.
A estatura varia de 145,0 a 199,9 cm (sete classes, início em 144 cm); o peso,
de 44,0 a 109,5 kg (17 classes, início em 44 kg). Cada variável contabiliza
exatamente 1.000 registros, uma única vez cada. As tabelas vieram da execução C++.

{chr(10).join(class_tables)}

## 2. Fórmulas e resultados

Com xi=ponto médio, fi=frequência e N=soma das frequências, utilizam-se:

```text
mu = sum(xi*fi) / N
variancia_pop = sum(fi*(xi-mu)^2) / N
sigma = sqrt(variancia_pop)
CV_percentual = 100*sigma/mu
```

A média é agrupada, calculada pelos pontos médios. A variância é populacional
(divisor N). O método tem duas passadas: a primeira obtém a média e a segunda
acumula os desvios quadráticos em relação à média já concluída. Evita-se a
subtração de termos grandes e próximos da fórmula E[X^2]-E[X]^2.

| Estatística | Estatura (cm) | Peso (kg) |
|---|---:|---:|
| Média agrupada | {e['media']} | {p['media']} |
| Variância populacional (unidade^2) | {e['variancia_pop']} | {p['variancia_pop']} |
| Desvio padrão populacional | {e['desvio_pop']} | {p['desvio_pop']} |
| CV (%) | {e['CV']} | {p['CV']} |

Os resultados conferem com dados/VALIDACAO_BASE.txt. Frequências e classes
coincidem exatamente entre as versões; estatísticas são comparadas com
tolerâncias absoluta e relativa de 1e-10. O programa calcula a partir do TXT,
sem ler a referência ou conter os valores estatísticos esperados. O peso
tem maior dispersão relativa neste conjunto sintético agrupado.

## 3. Paralelização e segurança

A solução está em src/analise.hpp, src/analise.cpp e src/main.cpp. A rota
sequencial executa todos os cálculos sem diretivas ou chamadas OpenMP no
processamento. A rota paralela realiza o mesmo trabalho lógico:

- Mínimo/máximo: parallel for com reduction(min:...) e reduction(max:...).
  Uma reduction lógica verifica a validade dos valores.
- Pontos médios: parallel for schedule(static); cada posição tem um escritor.
- Frequências: histogramas privados por thread. Após a barreira, as contagens
  são combinadas por classe, também com um único escritor por classe.
- Média: parallel for reduction(+:soma_ponderada), acumulando xi*fi.
- Variância: segundo parallel for reduction(+:soma_desvios_ponderados),
  acumulando fi*(xi-mu)^2. A média é somente lida pelas threads.

Não há critical/atomic por registro, paralelismo aninhado ou divisão de tarefas
baseada em IDs fixos. Dados compartilhados de entrada são somente lidos;
barreiras garantem as dependências entre etapas. O escalonamento static
combina com o custo uniforme dos laços. As duas variáveis abrem, juntas,
dez regiões paralelas por processamento. O ajuste dinâmico é desativado e
o número real da equipe é consultado dentro da região de contagem.

## 4. Ambiente e método de desempenho

Ambiente medido: {environment['sistema']}; CPU {environment['cpu']};
{available} processadores lógicos. Compilador: {environment['compilador'].splitlines()[0]}.
Flags: {' '.join(environment['flags'])}. O teste mínimo confirmou duas threads
e uma redução inteira correta. Configurações reais no benchmark: {', '.join(c['threads_reais'] for c in parallel)}.
Variáveis OMP/GOMP herdadas: {json.dumps(environment['variaveis_openmp'],ensure_ascii=False)}.

No Windows, o script de compilação copia libstdc++-6.dll, libgcc_s_seh-1.dll,
libgomp-1.dll e libwinpthread-1.dll do mesmo GCC para build/. Isso preserva a
correção da incompatibilidade identificada com bibliotecas homônimas do Git Bash.
Origens e hashes estão em resultados/ambiente.json; não se muda o PATH global.

Mede-se com omp_get_wtime na thread principal, com dados já lidos. Há cinco
processamentos de aquecimento por configuração, fora do cronômetro, e
{n_samples} amostras de {repetitions} processamentos completos. Cada amostra é dividida
por {repetitions}, mantendo a mesma base de 1.000 pares e as mesmas repetições em
todas as rotas. A primeira configuração muda a cada rodada para reduzir
viés de ordem. A corretude é conferida após cada configuração/amostra,
fora do trecho medido. A referência é sequencial real; paralelo com uma
thread aparece separadamente e mantém o custo do runtime.

O trecho cronometrado inclui extremos, construção e alocação das classes,
contagem, conferência dos totais, estatísticas das duas variáveis e liberação
dos resultados. Inclui um pequeno checksum volatile de custo igual nas duas
rotas, tornando a computação observável. Não há LTO; o processamento está em
outra unidade de tradução. Excluem-se leitura de disco, impressão, testes,
geração do dataset e escrita dos CSVs.

```text
speedup = mediana_sequencial / mediana_paralela
eficiencia = speedup / threads_reais
```

## 5. Medições e interpretação

Tempos por processamento completo de ambas as variáveis, em microssegundos (us).
Eficiência expressa em percentual. Todas as medidas abaixo são desta execução.

| Versão | Threads | Mediana us | Speedup | Eficiência % |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

{observation} A menor mediana foi da versão {best['versao']} com
{best['threads_reais']} thread(s). O trabalho de apenas 1.000 registros, com laços
estatísticos de sete e 17 classes, é pequeno diante do custo de regiões,
barreiras, reduções e histogramas privados. Essa é uma interpretação dos
tempos completos: os custos individuais não foram isolados experimentalmente.

Não se fixou afinidade nem se controlou exclusivamente carga, temperatura ou
política de energia. A CPU tem arquitetura híbrida e o escalonamento pode
variar. Os tempos não devem ser generalizados para outras máquinas ou sessões.
Não se aumentou N para buscar ganho artificial; repetir o processamento não
transforma cada execução em uma base maior.

Os {len(samples)} registros individuais estão em resultados/amostras.csv; as medianas,
em resultados/benchmark.csv. O gerador recalcula medianas, speedup e eficiência
a partir das amostras. resultados/benchmark_execucao.json registra comando,
horários, retorno e hashes do executável, fontes, entrada, ambiente e CSVs;
esses hashes também são conferidos antes de gerar este relatório. As medidas
históricas preservadas em resultados/historico não alimentam as tabelas finais.

A medição foi executada por ferramentas/medir.py, com integridade conferida
antes e depois do processamento. Seu identificador é {meta['id_medicao']}.
O conjunto original desta execução está em {meta['pasta_medicao']}.
O comando C++ direto gera somente CSVs; o script de medição publica CSVs e
metadados juntos após a conferência. O relatório não atualiza hashes de dados
antigos e rejeita conjuntos divergentes.

## 6. Validação e independência

O caso manual usa estaturas [145,145,153,169], pontos médios [148,156,164,172]
e frequências [2,1,0,1]: média=156, soma de desvios=384, variância=96 e
CV=100*sqrt(96)/156. Para pesos [45,45,49,57], a média agrupada é 50 e a
variância é 24. São resultados distintos de estatísticas dos valores brutos.

Também se verificam fronteiras exatas e doubles imediatamente antes/depois,
classes vazias, N=1, dados constantes e fronteira como máximo. Os cinco
conjuntos são comparados 20 vezes por configuração viável. A entrada oficial
mantém N=1.000. Arquivos ausentes/vazios, 999/1001 registros, texto, campos
faltantes/extras, lixo, vírgula decimal, zero, negativos, nan, inf e overflow
são recusados. Dataset e referência estatística possuem SHA-256 conferido.

Resultado funcional: {logs[0]['stdout'].strip().splitlines()[-1]}
O teste C++ realizou {comparisons} comparações sequencial/paralela.
Os testes Python de diagnóstico, auditoria e PDF também terminaram com código zero;
os registros completos estão em resultados/testes.json e testes.txt.
A validação inclui os três executáveis com PATH restrito ao Windows.

Os testes funcionais não leem o manifesto histórico, o PDF do professor ou
os códigos de aula. A auditoria dos 16 materiais é um comando opcional e
explícito, com raiz e manifesto fornecidos pelo usuário; ausência ou alteração
falha nessa auditoria. Ela não participa do fluxo de compilação, teste ou
relatório acadêmico e não é necessária para utilizar a versão independente.

## 7. Reprodução e conclusão

No Git Bash, partindo do workspace OpenMP:

```bash
cd projeto_openmp
python -B ferramentas/compilar.py
./build/openmp_cv.exe dados/dados_1000_pessoas.txt --threads 4
python -B testes/validar.py
python -B testes/testar_processos.py
python -B testes/testar_auditoria.py
python -B testes/testar_pdf.py
python -B testes/testar_medicoes.py
python -B ferramentas/medir.py --amostras {n_samples} --repeticoes {repetitions}
python -B ferramentas/gerar_relatorio.py
```

O README inclui o comando g++ completo e equivalentes de PowerShell/Linux.
Os auxiliares usam somente a biblioteca padrão do Python. A leitura rejeita
entradas inválidas com mensagem e retorno 1. As falhas de subprocessos exibem
comando, diretório, código decimal/hexadecimal, stdout e stderr.

Os CVs calculados são {e['CV']}% (estatura) e {p['CV']}% (peso).
A implementação cumpriu o agrupamento e a paralelização solicitados, com
comparação entre rotas e medidas reais. Para o conjunto pequeno desta execução,
o resultado de desempenho deve ser interpretado conforme a tabela, sem
presumir que mais threads produzam ganho.

## Referências bibliográficas

PINTO, Rodrigo Gonçalves. Exercício Final: Análise de Dados com OpenMP.
IESB, 28 out. 2025. Enunciado acadêmico fornecido pelo professor, duas páginas.

PINTO, R. G. Parallel Programming Examples in C++ using OpenMP. 2025.
Material didático fornecido pelo professor: ambiente (001), parallel for (004),
cronômetro/barreiras (005), sincronização (006), reduções e duas passadas
(007) e tarefas/sections (008). As técnicas foram estudadas; a implementação
foi escrita para este exercício. Os materiais do professor são citados,
mas não são dependências nem estão incluídos nesta entrega independente.
"""
    folder=ROOT/'relatorio'
    folder.mkdir(exist_ok=True)
    (folder/'relatorio_openmp.md').write_text(report,encoding='utf-8')
    pages=converter(report,folder/'relatorio_openmp.pdf',ROOT/'resultados/diagrama_pdf.json')
    print(logtext)
    print(f'Conferidas {len(samples)} amostras; relatorio Markdown/PDF gerado com {pages} paginas.')


if __name__=='__main__': main()

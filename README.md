# Análise de Dados com OpenMP

Projeto acadêmico em **C++17 e OpenMP** para calcular o coeficiente de variação
da estatura e do peso em uma base sintética de 1.000 registros. A solução
implementa versões sequencial e paralela, verifica sua equivalência e compara
tempos medidos no Windows.

[Relatório acadêmico em PDF](relatorio/relatorio_openmp.pdf) ·
[Relatório em Markdown](relatorio/relatorio_openmp.md) ·
[Resultados do benchmark](resultados/benchmark.csv)

## Tecnologias

- **C++17:** leitura, agrupamento, cálculos e interface de linha de comando.
- **OpenMP:** divisão dos laços, reduções e histogramas privados por thread.
- **GCC/MSYS2:** compilação com `-fopenmp`; versão medida: GCC 16.2.0.
- **Python 3.10+:** scripts auxiliares de compilação, testes, medição e PDF.
  O cálculo estatístico é executado pelo programa C++.

## Metodologia

A entrada tem duas colunas, `estatura_cm peso_kg`, sem cabeçalho, com espaço
entre valores e ponto decimal. Os dados são **inteiramente sintéticos**
(semente `20261112`) e não representam coleta de pessoas reais.

As classes têm largura de **8 cm** e **4 kg**. Sua origem é
`floor(mínimo/largura) × largura`; os intervalos são `[a, b)`, de modo que
um valor igual a `b` pertence à classe seguinte. Cada variável contabiliza
exatamente 1.000 registros.

Usam-se os pontos médios das classes e suas frequências para calcular a
média ponderada, a variância **populacional** (divisor `N`), o desvio padrão
e `CV (%) = 100 × desvio / média`. Os valores são recomputados a partir do
[dataset](dados/dados_1000_pessoas.txt), sem constantes de resultados no programa.

A rota sequencial executa o processamento sem chamadas OpenMP. A rota paralela
usa `parallel for`, `schedule(static)` e `reduction` nos extremos e nas duas
passadas estatísticas. Histogramas por thread evitam incrementos concorrentes
na mesma frequência; as contagens são combinadas após uma barreira.

## Principais resultados

| Variável | Coeficiente de variação |
|---|---:|
| Estatura agrupada | **5,5077761268%** |
| Peso agrupado | **16,6201684216%** |

Os resultados coincidem com a [referência de validação](dados/VALIDACAO_BASE.txt).
As duas implementações produzem frequências iguais e estatísticas equivalentes
dentro das tolerâncias absoluta e relativa de `1e-10`.

## Comparação de desempenho

Medianas por processamento completo das duas variáveis, com **10 amostras e
1.000 repetições por configuração**:

| Versão | Threads reais | Mediana |
|---|---:|---:|
| Sequencial | 1 | 12 µs |
| Paralela | 1 | 60 µs |
| Paralela | 2 | 552 µs |
| Paralela | 4 | 1.016 µs |
| Paralela | 8 | 1.740 µs |

A versão sequencial foi mais rápida. Para apenas 1.000 registros e laços
estatísticos de sete e 17 classes, os custos das dez regiões paralelas,
sincronizações e histogramas superam o trabalho distribuído. Todas as
configurações paralelas tiveram speedup inferior a 1 nesta medição.

O cronômetro inclui o processamento em memória e exclui leitura de disco,
impressão e testes. Há aquecimento, alternância da ordem e conferência de
corretude. Os [50 registros individuais](resultados/amostras.csv), o
[ambiente](resultados/ambiente.json) e os
[metadados da execução](resultados/benchmark_execucao.json) sustentam os valores.
Os tempos dependem da carga e do ambiente; não são uma promessa de desempenho.

### Tabela simplificada no VS Code

Abra [resultados/tempos.csv](resultados/tempos.csv) pelo Explorador do VS Code
para consultar versão, threads reais, mediana por processamento em µs e speedup.
O editor abre o CSV como texto, com uma linha por configuração e vírgulas
separando as colunas; não é necessário instalar extensões.

Para atualizar essa visualização a partir da medição existente:

```bash
python -B ferramentas/gerar_tempos.py
```

O script valida os hashes e as amostras antes de gerar a tabela. Os tempos são
convertidos de segundos para µs e exibidos com três casas decimais; o speedup,
com seis. Esse arredondamento é somente de apresentação. Os CSVs originais e
os metadados permanecem intactos, sem recompilação ou novo benchmark.

## Como executar — Windows / Git Bash

Na raiz do repositório, use GCC/MSYS2 com OpenMP e Python 3.10 ou posterior:

```bash
python -B ferramentas/compilar.py
./build/openmp_cv.exe dados/dados_1000_pessoas.txt --threads 4
```

O script cria `build/` e utiliza o seguinte comando para o programa principal:

```bash
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -fopenmp src/main.cpp src/analise.cpp -o build/openmp_cv.exe
```

No Windows, o script também copia para `build/` as quatro DLLs do mesmo GCC:
`libstdc++-6.dll`, `libgcc_s_seh-1.dll`, `libgomp-1.dll` e `libwinpthread-1.dll`.
Mantenha-as junto dos executáveis para preservar a compatibilidade com o Git Bash.
O PATH global não é alterado. Use `--cxx CAMINHO_DO_GPP` no script para selecionar
outro compilador; as origens e hashes das DLLs são registrados no ambiente.

A entrada exige 1.000 linhas úteis, dois números finitos e positivos por linha
e nenhum cabeçalho. Linhas em branco são ignoradas; entradas inválidas retornam
código 1 com diagnóstico. Consulte as opções com:

```bash
./build/openmp_cv.exe --help
```

### Medir e gerar o relatório

Após compilar, execute o fluxo completo para associar os resultados ao
executável utilizado:

```bash
python -B ferramentas/medir.py --amostras 10 --repeticoes 1000
python -B ferramentas/gerar_relatorio.py
```

**Diferença entre os fluxos:** o comando C++ com `--benchmark` produz somente
CSVs. `medir.py` executa a validação, confere hashes antes e depois da medição
e publica CSVs e metadados juntos. O relatório rejeita conjuntos divergentes.
Não atualize hashes manualmente para reutilizar uma medição antiga.

Recompilar pode mudar o hash do executável e exige uma nova medição para
gerar outro relatório a partir dele. Para revisar **somente a documentação**,
preservando os dados já registrados, use:

```bash
python -B ferramentas/gerar_relatorio.py --usar-registros
```

Essa opção mantém a verificação de integridade e a conferência dos CSVs.

### Fontes e PDF

Não há dependências Python externas. O exportador lê fontes TrueType do
sistema, usa suas métricas reais e incorpora-as ao PDF com mapas Unicode.
No Windows utiliza Arial, Arial Bold e Consolas; no Linux procura DejaVu
ou Liberation. A permissão de incorporação da fonte é verificada.

Se as fontes não estiverem disponíveis, configure `OPENMP_FONT_DIR` com um
diretório que contenha `regular.ttf`, `bold.ttf` e `mono.ttf` de uma família
com suporte a português e símbolos matemáticos. Os arquivos das fontes não
são copiados para o repositório.

No PowerShell, execute os mesmos scripts e use
`.\build\openmp_cv.exe dados/dados_1000_pessoas.txt --threads 4`.
No Linux, use `python3 -B` e os executáveis sem `.exe`. A medição apresentada
foi realizada no Windows; não foi medida uma execução Linux.

## Testes

```bash
./build/testes.exe dados/dados_1000_pessoas.txt
python -B testes/validar.py
python -B testes/testar_processos.py
python -B testes/testar_medicoes.py
python -B testes/testar_pdf.py
python -B testes/testar_auditoria.py
```

São cobertos cálculos manuais, fronteiras exatas e adjacentes, dados constantes,
classes vazias, entradas inválidas e comparações com diferentes números de
threads. Há regressões de subprocessos, integridade das medições e paginação
do PDF. As evidências funcionais registram **400 comparações C++ e 47
verificações de integração**.

A auditoria dos materiais históricos é separada e opcional; os testes
funcionais não exigem aulas ou PDF do professor. Seu comando explícito está
disponível em `python -B testes/auditar_materiais.py --help`.

## Estrutura do projeto

```text
.
├── src/          # Implementação C++17/OpenMP
├── dados/        # Dataset e referência estatística
├── testes/       # Testes funcionais e regressões
├── ferramentas/  # Compilação, medição e documentação
├── resultados/   # CSVs, ambiente e evidências rastreáveis
│   ├── medicoes/ # Conjuntos identificados por execução
│   ├── historico/ # Resultados anteriores preservados
│   └── auditoria/ # Registros técnicos de integridade
├── relatorio/    # Relatório acadêmico e notas técnicas
└── build/        # Executáveis e DLLs gerados localmente
```

Os resultados históricos e as notas de diagnóstico são evidências auxiliares.
As tabelas desta página e do relatório usam os CSVs atuais da raiz de
`resultados/`. Os hashes vinculam a medição ao executável, fontes C++,
dataset e ambiente, sem modificar os arquivos históricos.

## Relatório acadêmico

Leia o [relatório em PDF](relatorio/relatorio_openmp.pdf) para consultar as
distribuições de frequência, fórmulas, estratégia OpenMP, ambiente, método
de benchmark e interpretação crítica dos resultados.

## Autoria e referências

**Autor:** Heitor Ribeiro · **Instituição:** IESB · **Curso:** Ciência da Computação

**Disciplina:** Programação Paralela · **Professor:** Rodrigo Gonçalves Pinto

Referências: Pinto, R. G. *Exercício Final: Análise de Dados com OpenMP*
(IESB, 28 out. 2025) e *Parallel Programming Examples in C++ using OpenMP*
(material didático, 2025). A identificação acadêmica completa está no relatório.

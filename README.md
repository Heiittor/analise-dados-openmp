# Projeto OpenMP — entrega acadêmica independente

C++17/OpenMP para análise de 1.000 registros sintéticos de estatura e peso,
com classes de 8 cm e 4 kg. Inclui versões sequencial/paralela, testes,
medições reais e relatório acadêmico em Markdown/PDF.

## Compilação e execução no Git Bash / Windows

Requisitos: GCC/MSYS2 com OpenMP e Python 3.10 ou posterior. A validação desta
entrega foi feita com GCC 16.2.0 e Python 3.14 no Windows. Não há pacotes Python
externos. Todos os comandos seguintes partem do workspace `OpenMP`:

```bash
cd projeto_openmp
python -B ferramentas/compilar.py
./build/verificar_openmp.exe
./build/openmp_cv.exe --help
./build/openmp_cv.exe dados/dados_1000_pessoas.txt --threads 4
./build/testes.exe dados/dados_1000_pessoas.txt
python -B testes/validar.py
python -B testes/testar_processos.py
python -B testes/testar_auditoria.py
python -B testes/testar_pdf.py
python -B testes/testar_medicoes.py
python -B ferramentas/medir.py --amostras 15 --repeticoes 1000
python -B ferramentas/gerar_relatorio.py
python -B testes/testar_independencia.py
```

Também foram executadas análises com `--threads 1`, `2`, `4` e `8`.
O diretório `build/` é criado automaticamente; esta entrega foi compilada
inicialmente sem esse diretório. O script utiliza `g++` do PATH. Para indicar
explicitamente o GCC instalado:

```bash
python -B ferramentas/compilar.py --cxx C:/msys64/ucrt64/bin/g++.exe
```

O comando principal de compilação, executado pelo script, é:

```bash
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -fopenmp src/main.cpp src/analise.cpp -o build/openmp_cv.exe
```

No Windows, o script também copia para `build/` quatro DLLs do mesmo diretório
do GCC: `libstdc++-6.dll`, `libgcc_s_seh-1.dll`, `libgomp-1.dll` e
`libwinpthread-1.dll`. Mantenha-as junto dos executáveis. Seus hashes e origens
ficam em `resultados/ambiente.json`. Isso evita a mistura com os runtimes do
Git Bash. Não é necessário alterar o PATH global. Ao mudar de compilador,
execute novamente `compilar.py` para atualizar também essas DLLs.

## PowerShell e Linux

No PowerShell, dentro de `projeto_openmp`, os scripts Python são os mesmos.
Para executar o programa principal:

```powershell
python -B ferramentas/compilar.py
.\build\openmp_cv.exe dados/dados_1000_pessoas.txt --threads 4
python -B testes/validar.py
python -B ferramentas/medir.py --amostras 15 --repeticoes 1000
python -B ferramentas/gerar_relatorio.py
```

No Linux, use `python3 -B` no lugar de `python -B` e
`./build/openmp_cv` / `./build/testes`, sem `.exe`. O script de compilação
seleciona os nomes adequados e utiliza o runtime OpenMP do sistema. Os exemplos
Linux são orientações de reprodução; esta entrega foi medida no Windows.

## Interface, entrada e fórmulas

```text
openmp_cv ARQUIVO [--threads N] [--benchmark]
    [--amostras N] [--repeticoes N] [--saida DIRETORIO]
openmp_cv --help
```

- Entrada: exatamente 1.000 linhas úteis com dois números finitos e positivos;
  estatura em cm e peso em kg, ponto decimal e nenhum cabeçalho. Linhas em
  branco são ignoradas. Erros identificam a linha/categoria e retornam 1.
- `--threads N`: execução normal; padrão até 4, respeitando o ambiente.
- `--benchmark`: compara sequencial real e paralelo com 1, 2, 4 e 8 threads
  quando viáveis, produzindo somente CSVs. Para gerar também a integridade
  necessária ao relatório, use `python -B ferramentas/medir.py`.
  Nesse modo `--threads` controla só a conferência inicial.
- `--amostras N`: mínimo 10, padrão 15; `--repeticoes N`: mínimo 1, padrão 1.000.
- `--saida DIRETORIO`: CSVs relativos ao terminal, padrão `resultados`.

Cada variável tem origem `floor(minimo/largura)*largura` e classes `[a,b)`;
valores iguais a `b` entram na classe seguinte. Usa-se ponto médio `xi`,
frequência `fi` e `N=sum(fi)`:

```text
media = sum(xi*fi)/N
variancia_pop = sum(fi*(xi-media)^2)/N
desvio_pop = sqrt(variancia_pop)
CV_percentual = 100*desvio_pop/media
```

A base deve produzir CV de **5,5077761268%** para estatura e **16,6201684216%**
para peso. O executável não lê a referência nem usa esses valores como
constantes. As frequências são inteiras, os cálculos usam double e a variância
é populacional. Há proteção de recursos contra mais de 100.000 classes ou
limites não representáveis. Os histogramas devem receber os valores e a
largura usados na sua construção.

## Validação e auditoria histórica separadas

`testes/validar.py` executa os casos estatísticos e de entrada. Ele usa apenas
o próprio projeto e `dados/`. Confere os hashes do dataset e da referência,
fronteiras, casos manuais, entradas inválidas e comparações por threads.
No Windows também testa os três binários com PATH restrito ao sistema.
`testar_processos.py` preserva as regressões de mensagens/códigos de falha;
`testar_pdf.py` verifica tabelas inteiras, títulos e equilíbrio das páginas.
`testar_medicoes.py` cobre recompilação, CSVs desatualizados, mudanças durante
a medição, falha do programa, parâmetros divergentes, tempo zero e publicação.

Os 16 hashes dos materiais originais foram preservados somente como registro
histórico, em `resultados/auditoria/materiais_originais.json`. A auditoria
desses materiais exige uma raiz e um manifesto fornecidos explicitamente:

```text
python -B testes/auditar_materiais.py --raiz-materiais CAMINHO_DOS_MATERIAIS --manifesto resultados/auditoria/materiais_originais.json
```

Esse comando é opcional e não é chamado por compilação, testes funcionais,
benchmark ou relatório. A auditoria falha se um arquivo/manifesto estiver
ausente ou alterado; não existe aprovação silenciosa por falta de manifesto.
`testar_auditoria.py` testa essa regra usando arquivos temporários próprios.

`testar_independencia.py` confirma um bloqueio de acesso Python a pastas irmãs
e executa o validador e o gerador com esse bloqueio herdado pelos filhos Python.
Os binários C++ recebem caminhos locais e suas dependências de compilação
também são registradas na auditoria final. Nenhum arquivo de aula/PDF original
é necessário para usar esta entrega.

## Resultados, rastreabilidade e relatório

- `resultados/benchmark.csv`: medianas, speedup e eficiência atuais.
- `resultados/amostras.csv`: todas as amostras e tempos totais dos lotes.
- `resultados/benchmark_execucao.json`: comando, horários, saída, retorno e
  hashes do executável, fontes, entrada, ambiente e CSVs medidos.
- `resultados/medicoes/ID/`: conjunto de CSVs, metadados e saída de cada
  medição aprovada, preservado com identificador único.
- `resultados/ambiente.json`: CPU, SO, compilador, flags e DLLs compatíveis.
- `resultados/testes.json`, `testes.txt`, `estatisticas.txt`, `execucao.txt`:
  evidências das execuções da pasta final.
- `resultados/validacao_final.json`, `independencia.json`, `diagrama_pdf.json`:
  comandos/códigos de saída, teste de independência e paginação do PDF.
- `resultados/historico/`: medições da implementação de origem, identificadas
  como históricas; não alimentam as tabelas finais.
- `resultados/auditoria/`: procedência dos arquivos e registros de preservação.
- `relatorio/relatorio_openmp.md`, `relatorio_openmp.pdf`: relatório atual.
- `relatorio/auditoria_entrega.md`: árvore final e conferências da entrega.

`medir.py` é o ponto de entrada para benchmarks destinados ao relatório.
Ele só inicia o programa depois da validação funcional. Captura os hashes
do executável, fontes, entrada e ambiente antes da execução e os confere
novamente depois. O programa escreve em uma pasta nova por medição; nenhum
CSV anterior é adotado como se tivesse sido executado pelo script.

Antes de publicar, o script confere hashes, parâmetros, amostras, medianas,
speedup e eficiência. Só então substitui os arquivos atuais, publicando o
manifesto por último; um arquivo de lock sinaliza a medição em andamento.
Uma falha do programa ou mudança durante a execução interrompe a publicação.
O relatório permanece somente leitor e nunca recalcula hashes para legitimar
um conjunto antigo.

O cronômetro
inclui construção/alocação de classes, histogramas, conferência dos totais,
estatísticas e liberação dos resultados. Exclui disco, impressão e testes.
As versões executam as mesmas repetições da mesma base; há aquecimento,
alternância da ordem e checksum observável. A rota com uma thread OpenMP
é apresentada separadamente da rota sequencial real.

`gerar_relatorio.py` confere os hashes da medição, recalcula os indicadores
dos CSVs, reexecuta os testes e escreve Markdown/PDF. Depois de mudar fontes
ou recompilar, use novamente `medir.py` antes de gerar o relatório. Executar
apenas o benchmark C++ atualiza os CSVs, mas não os metadados de rastreabilidade;
isso é informado pelo próprio executável. O relatório rejeitará essa mistura,
mesmo que o comando C++ tenha terminado com código zero.

Para repetir o caso corrigido após uma compilação, execute:

```bash
python -B ferramentas/compilar.py
python -B testes/validar.py
python -B testes/testar_processos.py
python -B testes/testar_medicoes.py
python -B ferramentas/medir.py --amostras 10 --repeticoes 1000
python -B ferramentas/gerar_relatorio.py
```

Não edite hashes manualmente nem reutilize CSVs antigos após recompilar.
Com poucas repetições, o relógio pode produzir uma amostra de tempo zero;
o script rejeita esse conjunto e solicita mais repetições, sem substituir
ou inventar tempos. Mil repetições foram usadas na validação desta correção.

O PDF usa tabelas vetoriais mantidas inteiras, títulos ligados ao texto e
páginas com ocupação equilibrada. Os campos de aluno(a), matrícula, disciplina
e turma ficam em branco para preenchimento. Para apenas exportar um Markdown
revisado, execute `python -B ferramentas/exportar_pdf.py`; para atualizar
resultados e texto a partir das evidências, use `gerar_relatorio.py`.

Não são distribuídos materiais de aula, prompt mestre, PDF original, caches
ou temporários de desenvolvimento. `build/` contém somente os executáveis e
as quatro DLLs recém-gerados; pode ser reproduzido pelo compilador.

## Referências acadêmicas

PINTO, Rodrigo Gonçalves. *Exercício Final: Análise de Dados com OpenMP*.
IESB, 28 out. 2025. Enunciado fornecido pelo professor.

PINTO, R. G. *Parallel Programming Examples in C++ using OpenMP*. 2025.
Exemplos didáticos sobre ambiente (001), laços (004), tempo/barreiras (005),
sincronização (006), reduções/duas passadas (007) e tarefas (008).
As técnicas foram estudadas e a solução foi escrita para este exercício.

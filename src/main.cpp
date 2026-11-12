#include "analise.hpp"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <locale>
#include <stdexcept>
#include <string>
#include <vector>
#include <omp.h>

namespace {
struct Opcoes {
    std::string arquivo;
    int threads = std::min(4, std::min(omp_get_num_procs(), omp_get_thread_limit()));
    bool benchmark = false;
    int amostras = 15;
    int repeticoes = 1000;
    std::filesystem::path saida = "resultados";
};

void ajuda() {
    std::cout << "Uso: openmp_cv ARQUIVO [--threads N] [--benchmark]\n"
              << "     [--amostras N] [--repeticoes N] [--saida DIRETORIO]\n"
              << "--threads: execucao normal; benchmark percorre 1,2,4,8 viaveis.\n"
              << "--amostras: >=10 (padrao 15); --repeticoes: >=1 (padrao 1000).\n"
              << "--saida: diretorio dos CSVs do benchmark (padrao resultados).\n";
    std::cout << "Para CSVs + integridade + relatorio: python ferramentas/medir.py\n"
              << "O benchmark C++ direto produz somente CSVs, sem metadados de integridade.\n";
}

int inteiro(const std::string& s) {
    if (s.empty() || s.find_first_not_of("0123456789") != std::string::npos)
        throw std::runtime_error("Inteiro positivo invalido: " + s);
    const auto n = std::stoll(s);
    if (n < 1 || n > std::numeric_limits<int>::max())
        throw std::runtime_error("Inteiro fora da faixa: " + s);
    return static_cast<int>(n);
}

Opcoes interpretar(int argc, char** argv) {
    Opcoes o;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--benchmark") o.benchmark = true;
        else if (arg == "--threads" || arg == "--amostras" || arg == "--repeticoes" || arg == "--saida") {
            if (++i == argc) throw std::runtime_error("Falta valor para " + arg);
            if (arg == "--threads") o.threads = inteiro(argv[i]);
            else if (arg == "--amostras") o.amostras = inteiro(argv[i]);
            else if (arg == "--repeticoes") o.repeticoes = inteiro(argv[i]);
            else o.saida = argv[i];
        } else if (arg.rfind("--", 0) == 0) throw std::runtime_error("Opcao desconhecida: " + arg);
        else if (o.arquivo.empty()) o.arquivo = arg;
        else throw std::runtime_error("Argumento inesperado: " + arg);
    }
    if (o.arquivo.empty()) throw std::runtime_error("Informe o arquivo de entrada.");
    if (o.amostras < 10) throw std::runtime_error("Use pelo menos 10 amostras.");
    return o;
}

void apresentar_variavel(const cv::Variavel& v, const char* nome, const char* unidade) {
    const auto& c = v.classes;
    const auto& s = v.estatisticas;
    std::cout << '\n' << nome << " (" << unidade << "), N=" << s.n
              << ", threads reais=" << c.threads_reais << '\n';
    std::cout << "intervalo [inferior, superior) | ponto medio | frequencia\n";
    for (std::size_t i = 0; i < c.frequencias.size(); ++i) {
        const double a = c.inicio + static_cast<double>(i) * c.largura;
        std::cout << std::fixed << std::setprecision(1) << '[' << a << ", " << a + c.largura
                  << ") | " << c.pontos_medios[i] << " | " << c.frequencias[i] << '\n';
    }
    std::cout << std::setprecision(10)
              << "media=" << s.media << ' ' << unidade << '\n'
              << "variancia_pop=" << s.variancia << ' ' << unidade << "^2\n"
              << "desvio_pop=" << s.desvio << ' ' << unidade << '\n'
              << "CV=" << s.cv_percentual << " %\n";
}

double mediana(std::vector<double> tempos) {
    std::sort(tempos.begin(), tempos.end());
    const auto m = tempos.size() / 2;
    return tempos.size() % 2 ? tempos[m] : (tempos[m - 1] + tempos[m]) / 2;
}

struct Medida { int rodada; double lote, por_processamento; };
struct Configuracao {
    int pedidas, reais;
    std::vector<Medida> medidas;
};

// Efeito observavel e custo igual para todas as rotas. Sem LTO, as funcoes de
// processamento tambem estao em outra unidade de traducao.
volatile double checksum = 0;

void benchmark(const cv::Dados& dados, const cv::Resultado& referencia, const Opcoes& o) {
    std::vector<Configuracao> configuracoes{{0, 1, {}}};
    for (int t : cv::configuracoes_viaveis()) configuracoes.push_back({t, 0, {}});
    for (auto& config : configuracoes) {
        if (config.pedidas) cv::configurar_threads(config.pedidas);
        for (int i = 0; i < 5; ++i) { // Aquecimento fora do cronometro.
            const auto r = config.pedidas ? cv::processar_paralelo(dados) : cv::processar_sequencial(dados);
            cv::comparar_resultados(referencia, r);
            config.reais = r.estatura.classes.threads_reais;
            if (r.peso.classes.threads_reais != config.reais)
                throw std::runtime_error("Equipes diferentes entre as variaveis.");
        }
    }
    // Alterna a primeira configuracao a cada rodada para reduzir vies de ordem.
    for (int rodada = 0; rodada < o.amostras; ++rodada) {
        for (std::size_t deslocamento = 0; deslocamento < configuracoes.size(); ++deslocamento) {
            auto& config = configuracoes[(static_cast<std::size_t>(rodada) + deslocamento) % configuracoes.size()];
            if (config.pedidas) cv::configurar_threads(config.pedidas);
            const double inicio = omp_get_wtime();
            for (int i = 0; i < o.repeticoes; ++i) {
                const auto r = config.pedidas ? cv::processar_paralelo(dados) : cv::processar_sequencial(dados);
                checksum = checksum + r.estatura.estatisticas.cv_percentual + r.peso.estatisticas.cv_percentual;
            }
            const double lote = omp_get_wtime() - inicio;
            // Conferencia fora do tempo medido, apos cada configuracao/rodada.
            const auto r = config.pedidas ? cv::processar_paralelo(dados) : cv::processar_sequencial(dados);
            cv::comparar_resultados(referencia, r);
            if (r.estatura.classes.threads_reais != config.reais || r.peso.classes.threads_reais != config.reais)
                throw std::runtime_error("Numero real de threads mudou durante o benchmark.");
            config.medidas.push_back({rodada + 1, lote, lote / o.repeticoes});
        }
    }
    std::filesystem::create_directories(o.saida);
    std::ofstream resumo(o.saida / "benchmark.csv"), brutos(o.saida / "amostras.csv");
    if (!resumo || !brutos) throw std::runtime_error("Nao foi possivel abrir os CSVs de saida.");
    resumo.imbue(std::locale::classic());
    brutos.imbue(std::locale::classic());
    resumo << std::setprecision(17);
    brutos << std::setprecision(17);
    resumo << "versao,threads_solicitadas,threads_reais,amostras,repeticoes,mediana_segundos,speedup,eficiencia\n";
    brutos << "versao,threads_solicitadas,threads_reais,rodada,repeticoes,segundos_lote,segundos_processamento\n";
    std::vector<double> sequenciais;
    for (const auto& m : configuracoes.front().medidas) sequenciais.push_back(m.por_processamento);
    const double base = mediana(sequenciais);
    std::cout << "\nBenchmark: processamento completo em memoria (N=1000), " << o.amostras
              << " amostras x " << o.repeticoes << " repeticoes.\n"
              << "versao | threads reais | mediana (us) | speedup | eficiencia\n";
    for (const auto& config : configuracoes) {
        const char* versao = config.pedidas ? "paralela" : "sequencial";
        std::vector<double> tempos;
        for (const auto& m : config.medidas) {
            tempos.push_back(m.por_processamento);
            brutos << versao << ',' << config.pedidas << ',' << config.reais << ',' << m.rodada << ','
                   << o.repeticoes << ',' << m.lote << ',' << m.por_processamento << '\n';
        }
        const double tempo = mediana(tempos), speedup = base / tempo;
        const double eficiencia = speedup / config.reais;
        resumo << versao << ',' << config.pedidas << ',' << config.reais << ',' << o.amostras << ','
               << o.repeticoes << ',' << tempo << ',' << speedup << ',' << eficiencia << '\n';
        std::cout << versao << " | " << config.reais << " | " << std::fixed << std::setprecision(4)
                  << tempo * 1e6 << " | " << speedup << " | " << eficiencia << '\n';
    }
    resumo.close();
    brutos.close();
    if (!resumo || !brutos) throw std::runtime_error("Falha ao gravar CSVs.");
    std::cout << "Checksum observavel: " << std::setprecision(10) << checksum
              << "\nCSV: " << o.saida.string() << "/benchmark.csv e amostras.csv\n"
              << "Saida nativa: somente CSVs. O fluxo python ferramentas/medir.py registra a integridade.\n";
}
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--help") { ajuda(); return 0; }
        const auto o = interpretar(argc, argv);
        const int maximo_inicial = omp_get_max_threads();
        cv::configurar_threads(o.threads);
        const auto dados = cv::ler_dados(o.arquivo);
        const auto sequencial = cv::processar_sequencial(dados);
        const auto paralelo = cv::processar_paralelo(dados);
        cv::comparar_resultados(sequencial, paralelo);
        std::cout << "Analise de DADOS SINTETICOS agrupados; N=" << dados.estaturas.size()
                  << "\nGCC " << __VERSION__ << "; _OPENMP=" << _OPENMP
#ifdef _WIN32
                  << "; SO=Windows"
#else
                  << "; SO=Unix/Linux"
#endif
                  << "\nProcessadores logicos=" << omp_get_num_procs()
                  << "; max_threads inicial=" << maximo_inicial
                  << "; thread_limit=" << omp_get_thread_limit()
                  << "; dynamic=" << omp_get_dynamic() << '\n';
        apresentar_variavel(paralelo.estatura, "ESTATURA", "cm");
        apresentar_variavel(paralelo.peso, "PESO", "kg");
        std::cout << "\nValidacao sequencial/paralela: OK (abs=1e-10, rel=1e-10).\n";
        if (o.benchmark) benchmark(dados, sequencial, o);
        return 0;
    } catch (const std::exception& erro) {
        std::cerr << "Erro: " << erro.what() << '\n';
        return 1;
    }
}

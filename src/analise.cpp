// Implementacao original. Tecnicas estudadas nas aulas do Prof. Rodrigo G. Pinto;
// ver README e relatorio para a atribuicao academica dos materiais estudados.
#include "analise.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <limits>
#include <locale>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <omp.h>

namespace cv {
namespace {
void verificar_vetor(const std::vector<double>& v, double largura) {
    if (v.empty() || v.size() > static_cast<std::size_t>(std::numeric_limits<int>::max()))
        throw std::runtime_error("Quantidade de valores vazia ou nao suportada.");
    if (!std::isfinite(largura) || largura <= 0)
        throw std::runtime_error("Largura de classe deve ser finita e positiva.");
}

Classes alocar_classes(double minimo, double maximo, double largura, bool validos) {
    if (!validos) throw std::runtime_error("Valores devem ser finitos e positivos.");
    const double inicio = std::floor(minimo / largura) * largura;
    const double quantidade = std::floor((maximo - inicio) / largura) + 1;
    // Protecao de memoria e de limites cuja largura deixa de ser representavel.
    if (!std::isfinite(quantidade) || quantidade < 1 || quantidade > 100000
        || inicio + largura <= inicio
        || inicio + quantidade * largura <= maximo)
        throw std::runtime_error("Faixa nao suportada: limites nao representaveis ou mais de 100000 classes.");
    Classes c;
    c.inicio = inicio;
    c.largura = largura;
    const auto k = static_cast<std::size_t>(quantidade);
    c.frequencias.assign(k, 0);
    c.pontos_medios.resize(k);
    return c;
}

std::size_t indice(double valor, const Classes& c) {
    // [a,b): o proprio limite b e mapeado para a classe seguinte.
    return static_cast<std::size_t>(std::floor((valor - c.inicio) / c.largura));
}

Estatisticas finalizar(std::size_t n, double media, double soma_desvios) {
    const double variancia = soma_desvios / static_cast<double>(n);
    const double desvio = std::sqrt(variancia);
    const double percentual = desvio / media * 100;
    if (!std::isfinite(media) || media <= 0 || !std::isfinite(variancia)
        || !std::isfinite(percentual))
        throw std::runtime_error("Estatistica fora da faixa numerica suportada.");
    return {n, media, variancia, desvio, percentual};
}

std::size_t total(const Classes& c) {
    const auto n = std::accumulate(c.frequencias.begin(), c.frequencias.end(), std::size_t{0});
    if (n == 0) throw std::runtime_error("Nao ha frequencias para calcular estatisticas.");
    return n;
}

void conferir_total(const Classes& c, std::size_t n) {
    if (total(c) != n) throw std::runtime_error("Soma das frequencias difere de N.");
}
} // namespace

Dados ler_dados(const std::string& caminho, std::size_t exigido) {
    std::ifstream entrada(caminho);
    if (!entrada) throw std::runtime_error("Nao foi possivel abrir o arquivo: " + caminho);
    Dados dados;
    std::string linha;
    std::size_t numero = 0;
    while (std::getline(entrada, linha)) {
        ++numero;
        std::istringstream campos(linha);
        campos.imbue(std::locale::classic());
        campos >> std::ws;
        if (campos.eof()) continue; // Linhas em branco nao sao registros uteis.
        double estatura = 0, peso = 0;
        if (!(campos >> estatura >> peso))
            throw std::runtime_error("Linha " + std::to_string(numero) + ": esperados dois numeros validos.");
        campos >> std::ws;
        if (!campos.eof())
            throw std::runtime_error("Linha " + std::to_string(numero) + ": coluna extra ou lixo apos o peso.");
        if (!std::isfinite(estatura) || !std::isfinite(peso) || estatura <= 0 || peso <= 0)
            throw std::runtime_error("Linha " + std::to_string(numero) + ": numeros devem ser finitos e positivos.");
        if (dados.estaturas.size() == exigido)
            throw std::runtime_error("Registros extras: esperados exatamente " + std::to_string(exigido) + ".");
        dados.estaturas.push_back(estatura);
        dados.pesos.push_back(peso);
    }
    if (entrada.bad()) throw std::runtime_error("Falha de leitura do arquivo.");
    if (dados.estaturas.size() != exigido)
        throw std::runtime_error("Esperados " + std::to_string(exigido) + " registros; encontrados "
                                 + std::to_string(dados.estaturas.size()) + ".");
    return dados;
}

Classes construir_classes_sequencial(const std::vector<double>& v, double largura) {
    verificar_vetor(v, largura);
    double minimo = std::numeric_limits<double>::max(), maximo = 0;
    bool validos = true;
    for (double x : v) {
        validos = validos && std::isfinite(x) && x > 0;
        minimo = std::min(minimo, x);
        maximo = std::max(maximo, x);
    }
    auto c = alocar_classes(minimo, maximo, largura, validos);
    for (std::size_t i = 0; i < c.pontos_medios.size(); ++i)
        c.pontos_medios[i] = c.inicio + (static_cast<double>(i) + 0.5) * largura;
    return c;
}

Classes construir_classes_paralela(const std::vector<double>& v, double largura) {
    verificar_vetor(v, largura);
    double minimo = std::numeric_limits<double>::max(), maximo = 0;
    bool validos = true;
    const int n = static_cast<int>(v.size());
    #pragma omp parallel for schedule(static) reduction(min:minimo) reduction(max:maximo) reduction(&&:validos)
    for (int i = 0; i < n; ++i) {
        validos = validos && std::isfinite(v[i]) && v[i] > 0;
        minimo = std::min(minimo, v[i]);
        maximo = std::max(maximo, v[i]);
    }
    auto c = alocar_classes(minimo, maximo, largura, validos);
    const int k = static_cast<int>(c.pontos_medios.size());
    #pragma omp parallel for schedule(static)
    for (int i = 0; i < k; ++i)
        c.pontos_medios[i] = c.inicio + (i + 0.5) * largura;
    return c;
}

void contar_frequencias_sequencial(const std::vector<double>& v, Classes& c) {
    std::fill(c.frequencias.begin(), c.frequencias.end(), 0);
    for (double x : v) ++c.frequencias[indice(x, c)];
    conferir_total(c, v.size());
}

void contar_frequencias_paralela(const std::vector<double>& v, Classes& c) {
    const int k = static_cast<int>(c.frequencias.size());
    const int n = static_cast<int>(v.size());
    const int capacidade = omp_get_max_threads();
    std::vector<std::vector<std::size_t>> locais(capacidade, std::vector<std::size_t>(k, 0));
    int reais = 1;
    #pragma omp parallel
    {
        const int tid = omp_get_thread_num();
        #pragma omp single
        reais = omp_get_num_threads();
        // Cada thread escreve somente no seu histograma. Sem atomic/critical.
        #pragma omp for schedule(static)
        for (int i = 0; i < n; ++i) ++locais[tid][indice(v[i], c)];
        // A barreira acima garante que os histogramas locais estao completos.
        // Cada classe da saida tem um unico escritor nesta combinacao.
        #pragma omp for schedule(static)
        for (int j = 0; j < k; ++j) {
            std::size_t soma = 0;
            for (int t = 0; t < reais; ++t) soma += locais[t][j];
            c.frequencias[j] = soma;
        }
    }
    c.threads_reais = reais;
    conferir_total(c, v.size());
}

Estatisticas calcular_estatisticas_sequencial(const Classes& c) {
    const auto n = total(c);
    double soma_ponderada = 0;
    for (std::size_t i = 0; i < c.frequencias.size(); ++i)
        soma_ponderada += c.pontos_medios[i] * static_cast<double>(c.frequencias[i]);
    const double media = soma_ponderada / static_cast<double>(n);
    double soma_desvios_ponderados = 0;
    for (std::size_t i = 0; i < c.frequencias.size(); ++i) {
        const double d = c.pontos_medios[i] - media;
        soma_desvios_ponderados += static_cast<double>(c.frequencias[i]) * d * d;
    }
    return finalizar(n, media, soma_desvios_ponderados);
}

Estatisticas calcular_estatisticas_paralela(const Classes& c) {
    const auto n = total(c);
    const int k = static_cast<int>(c.frequencias.size());
    double soma_ponderada = 0;
    #pragma omp parallel for schedule(static) reduction(+:soma_ponderada)
    for (int i = 0; i < k; ++i)
        soma_ponderada += c.pontos_medios[i] * static_cast<double>(c.frequencias[i]);
    const double media = soma_ponderada / static_cast<double>(n);
    // A media precisa estar concluida antes desta segunda passada.
    double soma_desvios_ponderados = 0;
    #pragma omp parallel for schedule(static) reduction(+:soma_desvios_ponderados)
    for (int i = 0; i < k; ++i) {
        const double d = c.pontos_medios[i] - media;
        soma_desvios_ponderados += static_cast<double>(c.frequencias[i]) * d * d;
    }
    return finalizar(n, media, soma_desvios_ponderados);
}

Resultado processar_sequencial(const Dados& d) {
    auto e = construir_classes_sequencial(d.estaturas, 8);
    auto p = construir_classes_sequencial(d.pesos, 4);
    contar_frequencias_sequencial(d.estaturas, e);
    contar_frequencias_sequencial(d.pesos, p);
    const auto se = calcular_estatisticas_sequencial(e);
    const auto sp = calcular_estatisticas_sequencial(p);
    return {{std::move(e), se}, {std::move(p), sp}};
}

Resultado processar_paralelo(const Dados& d) {
    auto e = construir_classes_paralela(d.estaturas, 8);
    auto p = construir_classes_paralela(d.pesos, 4);
    contar_frequencias_paralela(d.estaturas, e);
    contar_frequencias_paralela(d.pesos, p);
    const auto se = calcular_estatisticas_paralela(e);
    const auto sp = calcular_estatisticas_paralela(p);
    return {{std::move(e), se}, {std::move(p), sp}};
}

bool aproximadamente(double a, double b, double absoluta, double relativa) {
    return std::isfinite(a) && std::isfinite(b)
        && std::abs(a - b) <= absoluta + relativa * std::max(std::abs(a), std::abs(b));
}

void comparar_resultados(const Resultado& a, const Resultado& b) {
    const Variavel* variaveis_a[] = {&a.estatura, &a.peso};
    const Variavel* variaveis_b[] = {&b.estatura, &b.peso};
    for (int i = 0; i < 2; ++i) {
        const auto& x = *variaveis_a[i];
        const auto& y = *variaveis_b[i];
        if (x.classes.inicio != y.classes.inicio || x.classes.largura != y.classes.largura
            || x.classes.frequencias != y.classes.frequencias
            || x.classes.pontos_medios != y.classes.pontos_medios
            || x.estatisticas.n != y.estatisticas.n
            || !aproximadamente(x.estatisticas.media, y.estatisticas.media)
            || !aproximadamente(x.estatisticas.variancia, y.estatisticas.variancia)
            || !aproximadamente(x.estatisticas.desvio, y.estatisticas.desvio)
            || !aproximadamente(x.estatisticas.cv_percentual, y.estatisticas.cv_percentual))
            throw std::runtime_error("Resultados sequencial e paralelo divergentes.");
    }
}

int configurar_threads(int pedidas) {
    const int limite = std::min(omp_get_num_procs(), omp_get_thread_limit());
    if (pedidas < 1 || pedidas > limite)
        throw std::runtime_error("Threads devem estar entre 1 e " + std::to_string(limite) + ".");
    omp_set_dynamic(0);
    omp_set_num_threads(pedidas);
    return pedidas;
}

std::vector<int> configuracoes_viaveis() {
    std::vector<int> configuracoes;
    const int limite = std::min(omp_get_num_procs(), omp_get_thread_limit());
    for (int t : {1, 2, 4, 8}) if (t <= limite) configuracoes.push_back(t);
    return configuracoes;
}
} // namespace cv

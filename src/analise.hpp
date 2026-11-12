#pragma once

#include <cstddef>
#include <string>
#include <vector>

namespace cv {
constexpr std::size_t N_EXIGIDO_ENTRADA = 1000;
struct Dados {
    std::vector<double> estaturas;
    std::vector<double> pesos;
};
struct Classes {
    double inicio = 0;
    double largura = 0;
    std::vector<double> pontos_medios;
    std::vector<std::size_t> frequencias;
    int threads_reais = 1;
};
struct Estatisticas {
    std::size_t n;
    double media, variancia, desvio, cv_percentual;
};
struct Variavel {
    Classes classes;
    Estatisticas estatisticas;
};
struct Resultado {
    Variavel estatura, peso;
};

Dados ler_dados(const std::string& caminho,
                std::size_t exigido = N_EXIGIDO_ENTRADA);
Classes construir_classes_sequencial(const std::vector<double>& valores, double largura);
Classes construir_classes_paralela(const std::vector<double>& valores, double largura);
void contar_frequencias_sequencial(const std::vector<double>& valores, Classes& classes);
void contar_frequencias_paralela(const std::vector<double>& valores, Classes& classes);
Estatisticas calcular_estatisticas_sequencial(const Classes& classes);
Estatisticas calcular_estatisticas_paralela(const Classes& classes);
Resultado processar_sequencial(const Dados& dados);
Resultado processar_paralelo(const Dados& dados);
bool aproximadamente(double a, double b, double absoluta = 1e-10, double relativa = 1e-10);
void comparar_resultados(const Resultado& a, const Resultado& b);
int configurar_threads(int pedidas);
std::vector<int> configuracoes_viaveis();
} // namespace cv

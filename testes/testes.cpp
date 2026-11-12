#include "../src/analise.hpp"
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>

void exigir(bool condicao, const char* mensagem) {
    if (!condicao) throw std::runtime_error(mensagem);
}

void conferir(const cv::Estatisticas& s, double media, double variancia, double cvp) {
    exigir(cv::aproximadamente(s.media, media), "Media incorreta");
    exigir(cv::aproximadamente(s.variancia, variancia), "Variancia incorreta");
    exigir(cv::aproximadamente(s.desvio, std::sqrt(variancia)), "Desvio incorreto");
    exigir(cv::aproximadamente(s.cv_percentual, cvp), "CV incorreto");
}

int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::runtime_error("Informe o TXT oficial.");
        const auto oficial = cv::ler_dados(argv[1]);
        const auto referencia = cv::processar_sequencial(oficial);
        exigir(referencia.estatura.estatisticas.n == 1000 && referencia.peso.estatisticas.n == 1000, "N oficial");
        // Valores esperados pertencem exclusivamente aos testes, nunca ao programa.
        conferir(referencia.estatura.estatisticas, 170.976, 88.679424, 5.5077761268);
        conferir(referencia.peso.estatisticas, 72.84, 146.5584, 16.6201684216);

        // Conta manual: fi=[2,1,0,1], xi=[148,156,164,172].
        // mu=156; soma desvios=2*64+0+0+256=384; var=384/4=96.
        // Peso: xi=[46,50,54,58], mu=50, var=(2*16+64)/4=24.
        const cv::Dados pequeno{{145,145,153,169}, {45,45,49,57}};
        const auto manual = cv::processar_sequencial(pequeno);
        exigir(manual.estatura.classes.frequencias == std::vector<std::size_t>({2,1,0,1}), "fi manual");
        exigir(manual.estatura.estatisticas.n == 4, "N manual");
        conferir(manual.estatura.estatisticas, 156, 96, 100*std::sqrt(96.0)/156);
        conferir(manual.peso.estatisticas, 50, 24, 2*std::sqrt(24.0));

        // Inclui valores imediatamente abaixo/acima do limite em double.
        const cv::Dados fronteiras{
            {std::nextafter(152.0, 0.0), 152, std::nextafter(152.0, 200.0),160,168,176,184,192},
            {std::nextafter(48.0, 0.0), 48, std::nextafter(48.0, 100.0),52,56,60,64,68}};
        const auto bordas = cv::processar_sequencial(fronteiras);
        const std::vector<std::size_t> esperado{1,2,1,1,1,1,1};
        exigir(bordas.estatura.classes.inicio == 144 && bordas.peso.classes.inicio == 44, "Origem das classes");
        exigir(bordas.estatura.classes.frequencias == esperado && bordas.peso.classes.frequencias == esperado, "Fronteiras");
        const cv::Dados constantes{{160,160,160}, {52,52,52}};
        const auto constante = cv::processar_sequencial(constantes);
        conferir(constante.estatura.estatisticas, 164, 0, 0);
        conferir(constante.peso.estatisticas, 54, 0, 0);
        const cv::Dados uma{{145}, {45}};
        conferir(cv::processar_sequencial(uma).estatura.estatisticas, 148, 0, 0);

        int comparacoes = 0;
        for (int t : cv::configuracoes_viaveis()) {
            cv::configurar_threads(t);
            for (int i = 0; i < 20; ++i) {
                for (const auto* d : {&oficial, &pequeno, &fronteiras, &constantes, &uma}) {
                    const auto s = cv::processar_sequencial(*d);
                    const auto p = cv::processar_paralelo(*d);
                    cv::comparar_resultados(s, p);
                    exigir(p.estatura.classes.threads_reais >= 1 && p.estatura.classes.threads_reais <= t, "Equipe invalida");
                    ++comparacoes;
                }
            }
            std::cout << "OK: threads solicitadas=" << t << ", 20 repeticoes x 5 conjuntos\n";
        }
        // Comparador deve detectar erros, inclusive NaN.
        auto alterado = referencia;
        ++alterado.estatura.classes.frequencias[0];
        bool detectou = false;
        try { cv::comparar_resultados(referencia, alterado); } catch (const std::runtime_error&) { detectou = true; }
        exigir(detectou, "Comparador aceitou frequencia divergente");
        exigir(!cv::aproximadamente(std::numeric_limits<double>::quiet_NaN(), 0), "Comparador aceitou NaN");
        std::cout << "PASSOU: estatistica manual, fronteiras, constantes, N=1, base oficial e "
                  << comparacoes << " comparacoes sequencial/paralela.\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FALHOU: " << e.what() << '\n';
        return 1;
    }
}

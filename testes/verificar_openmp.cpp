#include <iostream>
#include <omp.h>

int main() {
    int equipe = 0;
    int soma = 0;
    omp_set_dynamic(0);
    #pragma omp parallel num_threads(2) reduction(+:soma)
    {
        #pragma omp single
        equipe = omp_get_num_threads();
        soma += 1;
    }
    std::cout << "GCC " << __VERSION__ << " | _OPENMP=" << _OPENMP
              << " | processadores=" << omp_get_num_procs()
              << " | max_threads=" << omp_get_max_threads()
              << " | thread_limit=" << omp_get_thread_limit()
              << " | equipe=" << equipe << " | soma=" << soma << '\n';
    return equipe == 2 && soma == 2 ? 0 : 1;
}

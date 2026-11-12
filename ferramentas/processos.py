"""Execucao de subprocessos com diagnostico completo, sem ocultar falhas."""
import subprocess

STATUS_WINDOWS = {
    0xC0000005: 'STATUS_ACCESS_VIOLATION',
    0xC0000135: 'STATUS_DLL_NOT_FOUND',
    0xC0000139: 'STATUS_ENTRYPOINT_NOT_FOUND',
    0xC000007B: 'STATUS_INVALID_IMAGE_FORMAT',
}


def codigo_saida(code):
    unsigned = code & 0xffffffff
    meaning = STATUS_WINDOWS.get(unsigned)
    return f'{code} (0x{unsigned:08X})' + (f' {meaning}' if meaning else '')


def diagnostico(result, cwd):
    return (f'Comando: {subprocess.list2cmdline(list(map(str, result.args)))}\n'
            f'Diretorio: {cwd}\nCodigo de saida: {codigo_saida(result.returncode)}\n'
            f'stdout:\n{result.stdout or "<vazio>"}\n'
            f'stderr:\n{result.stderr or "<vazio>"}')


def executar(command, *, cwd, esperado=0, timeout=60, env=None):
    command = list(map(str, command))
    try:
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                                text=True, errors='replace', timeout=timeout)
    except subprocess.TimeoutExpired as error:
        def texto(value):
            return value.decode(errors='replace') if isinstance(value, bytes) else value
        raise RuntimeError(
            f'Tempo limite de {timeout}s excedido.\nComando: {subprocess.list2cmdline(command)}\n'
            f'Diretorio: {cwd}\nCodigo de saida: indisponivel (timeout)\n'
            f'stdout:\n{texto(error.stdout) or "<vazio>"}\n'
            f'stderr:\n{texto(error.stderr) or "<vazio>"}') from error
    except OSError as error:
        raise RuntimeError(
            f'Falha ao iniciar subprocesso.\nComando: {subprocess.list2cmdline(command)}\n'
            f'Diretorio: {cwd}\nCodigo de saida: indisponivel (processo nao iniciou)\n'
            f'stdout: <nao disponivel>\nstderr: <nao disponivel>\nErro do SO: {error}') from error
    if result.returncode != esperado:
        raise RuntimeError(f'Retorno esperado: {esperado}.\n{diagnostico(result, cwd)}')
    return result

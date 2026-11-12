"""Executa testes/relatorio com bloqueio de acessos Python a pastas irmas.

O hook e herdado pelos subprocessos Python via sitecustomize. Os binarios
C++ recebem somente caminhos desta entrega; suas dependencias de compilacao
sao registradas separadamente. Nao modifica nenhuma pasta irma.
"""
from pathlib import Path
import json
import os
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ferramentas'))
from processos import executar


def main():
    log=ROOT/'resultados/independencia.json'
    with tempfile.TemporaryDirectory(prefix='independencia_',dir=ROOT/'build') as directory:
        guard=Path(directory)
        hook=r'''
import os,sys
_root=os.path.normcase(os.path.abspath(os.environ['OPENMP_ENTREGA']))
_workspace=os.path.dirname(_root)
def _check(value):
    if not isinstance(value,(str,bytes,os.PathLike)): return
    path=os.path.normcase(os.path.abspath(os.fsdecode(value)))
    try:
        outside=os.path.commonpath([path,_workspace])==_workspace and os.path.commonpath([path,_root])!=_root
    except ValueError:
        return
    if outside: raise RuntimeError('Acesso fora da entrega bloqueado: '+path)
def _audit(event,args):
    if event in ('open','os.listdir','os.scandir') and args: _check(args[0])
    if event=='subprocess.Popen' and args[2]: _check(args[2])
sys.addaudithook(_audit)
sys._openmp_guard=True
'''
        (guard/'sitecustomize.py').write_text(hook,encoding='utf-8')
        env={**os.environ,'PYTHONPATH':str(guard),'PYTHONDONTWRITEBYTECODE':'1','OPENMP_ENTREGA':str(ROOT)}
        # Codigo simples com newlines reais para provar que o bloqueio esta ativo.
        probe='import sys\nassert getattr(sys,"_openmp_guard",False)\ntry:\n open('+repr(str(ROOT.parent/'pasta_irma_inacessivel'/'exemplo.txt'))+')\nexcept RuntimeError:\n print("BLOQUEIO_CONFIRMADO")\nelse:\n raise SystemExit(2)\n'
        checked=executar([sys.executable,'-c',probe],cwd=ROOT,env=env)
        if 'BLOQUEIO_CONFIRMADO' not in checked.stdout: raise RuntimeError('Hook nao foi confirmado.')
        records=[]
        for script in ['testes/validar.py','ferramentas/gerar_relatorio.py']:
            result=executar([sys.executable,ROOT/script],cwd=ROOT,env=env,timeout=120)
            records.append(dict(comando=result.args,codigo_saida=result.returncode,stdout=result.stdout,stderr=result.stderr))
        log.write_text(json.dumps(dict(bloqueio_confirmado=True,escopo='Acessos Python no workspace limitados a esta entrega; hook herdado pelos filhos Python.',
                                      execucoes=records),indent=2,ensure_ascii=False),encoding='utf-8')
    print('PASSOU: testes funcionais e geracao do relatorio com acessos Python a pastas irmas bloqueados.')


if __name__=='__main__': main()

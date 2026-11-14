"""Uso:  python -m agente reels | carrossel | respostas | token
Coloque SIMULAR=1 para testar sem publicar nada nem gastar.
"""
import sys

from . import config, dados_git


def main() -> None:
    tarefa = sys.argv[1] if len(sys.argv) > 1 else ""
    if tarefa == "reels":
        from . import reels
        reels.executar(cena_local=sys.argv[2] if len(sys.argv) > 2 else None)
        dados_git.enviar("Reels publicado")
    elif tarefa == "carrossel":
        from . import posts
        posts.executar()
        dados_git.enviar("Carrossel publicado")
    elif tarefa == "respostas":
        from . import respostas
        respostas.executar()
        dados_git.enviar("Respostas a comentários e DMs")
    elif tarefa == "token":
        from . import instagram
        config.exigir("IG_TOKEN")
        r = instagram.renovar_token()
        dias = int(r.get("expires_in", 0)) // 86400
        mudou = r.get("access_token") and r["access_token"] != config.IG_TOKEN
        print(f"Token renovado: válido por mais {dias} dias.")
        if mudou:
            raise SystemExit("ATENÇÃO: o Instagram passou a exigir um token novo. Gere outro no painel "
                             "da Meta (guia, passo 'Gerar o token') e atualize o segredo IG_TOKEN no GitHub.")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()

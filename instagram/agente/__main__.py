"""Uso:  python -m agente verificar | reels | carrossel | respostas | token
Coloque SIMULAR=1 para testar sem publicar nada nem gastar.
"""
import sys

from . import config, dados_git


def main() -> None:
    tarefa = sys.argv[1] if len(sys.argv) > 1 else ""
    if tarefa not in ("verificar", "") and not config.SIMULAR and config.IG_TOKEN:
        from . import instagram
        instagram.detectar_api()
    if tarefa == "verificar":
        from . import instagram
        config.exigir("IG_TOKEN")
        instagram.detectar_api()
        pubs = instagram.minhas_publicacoes(limite=3)
        print(f"Tudo certo! Últimas publicações encontradas: {len(pubs)}")
        for nome in ("ANTHROPIC_API_KEY", "FAL_KEY", "PAINEL_SENHA"):
            print(f"{nome}: {'cadastrada ✅' if __import__('os').getenv(nome) else 'FALTANDO ❌'}")
        fk = config.FAL_KEY
        if fk:
            print(f"fal.ai: chave com {len(fk)} caracteres; formato {'ok (id:segredo)' if ':' in fk else 'INCOMPLETO — falta a parte depois dos dois-pontos'}")
        from . import claude
        try:
            claude.perguntar_json("Responda só com JSON.", 'Devolva {"ok": true}', modelo=config.MODELO_RAPIDO, max_tokens=20)
            print("Claude: chave funcionando ✅")
        except Exception as e:
            k = config.ANTHROPIC_API_KEY
            print(f"Claude: chave RECUSADA ❌ (tamanho {len(k)} caracteres, começa com {k[:10]}…) — {str(e)[-160:]}")
        return
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
        if "facebook" in config.IG_API:
            print("Token de usuário do sistema: não expira, nada a renovar.")
            return
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

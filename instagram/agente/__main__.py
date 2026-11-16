"""Uso:  python -m agente verificar | reels | carrossel | respostas | token
Coloque SIMULAR=1 para testar sem publicar nada nem gastar.
"""
import sys
from pathlib import Path

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
    elif tarefa == "publicar-previa":
        # Publica uma prévia já aprovada (branch "previa-<formato>"), sem gerar outra
        import json, os
        from . import estado, instagram
        formato = sys.argv[2]
        pasta = Path(sys.argv[3])
        r = json.loads((pasta / "roteiro.json").read_text())
        mp4 = next(pasta.glob("*.mp4")).name
        base = f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/previa-{formato}"
        legenda = r["legenda"]
        if "inteligência artificial" not in legenda.lower():
            legenda += "\n\n🎬 Vídeo criado com inteligência artificial."
        media_id = instagram.publicar_reel(f"{base}/{mp4}", legenda, capa_url=f"{base}/{mp4[:-4]}.jpg")
        instagram.copiar_para_stories(f"{base}/{mp4}", video=True)
        est = estado.carregar()
        est["publicacoes"].append({
            "data": estado.agora(), "tipo": "reel", "estrategia": r.get("estrategia"), "formato": r.get("formato"),
            "argumento": r.get("argumento"), "argumento_base": r.get("argumento"), "tema": r.get("tema"),
            "gancho": r.get("gancho"), "palavra_chave": r.get("palavra_chave", "ECONOMIZAR"),
            "textos": [c.get("texto") for c in r.get("cenas", [])], "legenda": legenda, "media_id": media_id,
            "permalink": instagram.permalink(media_id), "modo": "cenas",
        })
        estado.registrar(est, "reel", f"{r.get('tema', '')} ({r.get('formato')})")
        estado.salvar(est)
        dados_git.enviar("Reels (prévia aprovada) publicado")
        print(f"Publicado: {media_id}")
    elif tarefa == "apagar":
        from . import estado, instagram
        media_id = (sys.argv[2] if len(sys.argv) > 2 else "").strip()
        if not media_id:
            raise SystemExit("Informe o ID da publicação a apagar.")
        r = instagram.apagar(media_id)
        print(f"Resposta do Instagram: {r}")
        est = estado.carregar()
        antes = [p for p in est["publicacoes"] if p.get("media_id") == media_id]
        est["publicacoes"] = [p for p in est["publicacoes"] if p.get("media_id") != media_id]
        estado.registrar(est, "Publicação apagada", antes[0].get("tema", media_id) if antes else media_id)
        estado.salvar(est)
        dados_git.enviar("Publicação apagada")
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

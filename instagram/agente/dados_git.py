"""Envia o estado e as imagens para o branch "dados" do GitHub."""
import subprocess

from . import config


def enviar(mensagem: str) -> None:
    pasta = config.DADOS_DIR
    if config.SIMULAR or not (pasta / ".git").exists():
        print(f"[local] não enviando para o GitHub: {mensagem}")
        return

    def git(*args):
        subprocess.run(["git", "-C", str(pasta), *args], check=True)

    git("add", "-A")
    if subprocess.run(["git", "-C", str(pasta), "diff", "--cached", "--quiet"]).returncode == 0:
        return
    git("-c", "user.name=Agente ELLO", "-c", "user.email=agente@users.noreply.github.com",
        "commit", "-q", "-m", mensagem)
    for _ in range(3):
        if subprocess.run(["git", "-C", str(pasta), "push", "-q", "origin", f"HEAD:{config.DADOS_BRANCH}"]).returncode == 0:
            return
        git("pull", "-q", "--rebase", "origin", config.DADOS_BRANCH)
    raise RuntimeError("Não consegui enviar os dados para o GitHub.")


def publicar_midia(arquivos: list) -> list[str]:
    """Deixa arquivos públicos no branch "midia" e devolve as URLs.

    O branch é recriado a cada vez, então o repositório não cresce com vídeos antigos.
    """
    nomes = [a.name for a in arquivos]
    if config.SIMULAR:
        print(f"[simulação] publicaria mídia: {nomes}")
        return [f"{config.URL_MIDIA_BASE}/{n}" for n in nomes]
    import os
    import shutil
    import tempfile
    from pathlib import Path
    url = f"https://x-access-token:{os.environ['GITHUB_TOKEN']}@github.com/{config.REPO}"
    with tempfile.TemporaryDirectory() as tmp:
        for a in arquivos:
            shutil.copy(a, Path(tmp) / a.name)

        def git(*args):
            subprocess.run(["git", "-C", tmp, *args], check=True)

        git("init", "-q")
        git("checkout", "-q", "-b", config.MIDIA_BRANCH)
        git("add", "-A")
        git("-c", "user.name=Agente ELLO", "-c", "user.email=agente@users.noreply.github.com",
            "commit", "-q", "-m", "Mídia para publicação")
        git("push", "-q", "-f", url, f"HEAD:{config.MIDIA_BRANCH}")
    return [f"{config.URL_MIDIA_BASE}/{n}" for n in nomes]

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

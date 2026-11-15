"""Gera as fotos do site com IA (fal.ai, Flux) e salva em docs/assets/fotos/. Uso único, via GitHub Actions."""
import os, time, pathlib, requests

KEY = os.environ["FAL_KEY"].strip()
CAB = {"Authorization": f"Key {KEY}", "Content-Type": "application/json"}
PASTA = pathlib.Path("docs/assets/fotos"); PASTA.mkdir(parents=True, exist_ok=True)
ESTILO = (" Ultra-realistic professional photography, natural light, 35mm lens, shallow depth of field, "
          "authentic Brazilian people and places, warm and optimistic mood, no text, no logos, no watermark.")
FOTOS = {
    "familia-cozinha": ("landscape_4_3", "A happy Brazilian family of three in a bright modern apartment kitchen in Campinas, "
                        "morning sunlight through the window, the mother smiles while checking a tablet, lights and fridge on, relaxed atmosphere."),
    "usina-solar": ("landscape_16_9", "Aerial drone photograph of a large solar farm in the green countryside of São Paulo state, Brazil, "
                    "long rows of photovoltaic panels reflecting a golden sunrise, light mist over the fields."),
    "paineis-detalhe": ("portrait_4_3", "Close-up of clean solar photovoltaic panels at sunrise with a lens flare from the sun, "
                        "blue sky with soft clouds, a few green trees in the background, Brazil."),
    "para-casa": ("landscape_4_3", "Cozy Brazilian living room in the evening with warm lamps on and a wall air conditioner running, "
                  "a young couple relaxing on the sofa, homey and comfortable."),
    "para-comercio": ("landscape_4_3", "Smiling Brazilian bakery owner in an apron standing behind the counter of a small padaria, "
                      "fresh breads on shelves, display fridges glowing, morning light."),
    "para-condominio": ("landscape_4_3", "Modern residential condominium building in Campinas, Brazil, with balconies and gardens, "
                        "clear blue sky, late afternoon sun, lobby lights on."),
    "atendimento": ("landscape_4_3", "Friendly young Brazilian woman at a bright home office smiling while chatting on her smartphone, "
                    "holding a printed electricity bill, plants and natural light."),
}
for nome, (tamanho, prompt) in FOTOS.items():
    pedido = requests.post("https://queue.fal.run/fal-ai/flux/dev", headers=CAB, timeout=60, json={
        "prompt": prompt + ESTILO, "image_size": tamanho, "num_images": 1, "num_inference_steps": 30,
        "guidance_scale": 3.5, "enable_safety_checker": True}).json()
    for _ in range(60):
        st = requests.get(pedido["status_url"], headers=CAB, timeout=60).json()
        if st.get("status") == "COMPLETED":
            break
        time.sleep(3)
    url = requests.get(pedido["response_url"], headers=CAB, timeout=60).json()["images"][0]["url"]
    (PASTA / f"{nome}.jpg").write_bytes(requests.get(url, timeout=120).content)
    print("ok", nome)

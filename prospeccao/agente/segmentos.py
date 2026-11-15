"""Segmentos de prospecção: o que buscar no Google, quais CNAEs puxar da Receita e o ângulo da conversa."""

SEGMENTOS = {
    "comercio": {
        "nome": "Pequenos comércios",
        "buscas": ["padaria", "restaurante", "supermercado", "mercado", "academia", "pizzaria",
                   "açougue", "lanchonete", "farmácia", "loja de roupas", "pet shop", "sorveteria",
                   "hortifruti", "salão de beleza", "lavanderia", "auto peças", "oficina mecânica"],
        "cnae": ["47", "561", "1091", "9313", "9602", "9601", "4520", "4530"],
        "angulo": "geladeiras, fornos, ar-condicionado e iluminação ligados o dia todo pesam na margem do negócio",
    },
    "condominio": {
        "nome": "Condomínios",
        "buscas": ["condomínio residencial", "administradora de condomínios", "condomínio comercial",
                   "edifício residencial"],
        "cnae": ["8112", "6822"],
        "angulo": "elevadores, bombas, iluminação de áreas comuns e portaria pesam na taxa condominial de todos os moradores",
    },
    "industria": {
        "nome": "Indústrias e galpões",
        "buscas": ["indústria", "fábrica", "metalúrgica", "galpão logístico", "indústria alimentícia",
                   "gráfica", "indústria de plásticos", "marcenaria", "serralheria"],
        "cnae": [f"{d:02d}" for d in range(10, 34)] + ["5211", "5212"],
        "angulo": "máquinas e linhas de produção fazem da energia um dos maiores custos fixos da operação",
    },
    "servicos": {
        "nome": "Escritórios e serviços",
        "buscas": ["escritório de contabilidade", "imobiliária", "escola particular", "clínica médica",
                   "clínica odontológica", "escritório de advocacia", "laboratório de análises",
                   "hotel", "coworking", "clínica veterinária"],
        "cnae": ["69", "6821", "85", "86", "75", "551", "7020", "7111", "7112"],
        "angulo": "ar-condicionado, computadores e equipamentos ligados em horário comercial deixam a conta alta todo mês",
    },
}


def segmento_por_cnae(cnae: str) -> str | None:
    """Escolhe o segmento pelo CNAE principal (o prefixo mais específico vence)."""
    melhor, tam = None, 0
    for chave, s in SEGMENTOS.items():
        for p in s["cnae"]:
            if cnae.startswith(p) and len(p) > tam:
                melhor, tam = chave, len(p)
    return melhor

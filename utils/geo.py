"""Distância entre a vaga e onde o usuário mora, pra vaga presencial/híbrida.

Vaga remota não passa por aqui: se não tem deslocamento, não tem o que
penalizar.

PRIVACIDADE: a âncora abaixo é o BAIRRO, nunca o endereço de rua. O
repositório é público, e endereço residencial exato não tem por que estar
num commit — na granularidade que importa aqui (raio de 11 km), a diferença
entre "a rua X" e "o bairro" é ruído. Nenhum dado do usuário sai daqui pra
serviço nenhum: o cálculo é local, contra a tabela de coordenadas fixa
abaixo, sem geocodificação online (que exigiria mandar endereço pra um
servidor de terceiro, além de virar mais uma dependência que pode cair).

PRECISÃO: as coordenadas são aproximações de centro de região, com erro na
casa de 1-3 km. Isso é aceitável porque o resultado NÃO é filtro — é
desconto no score (ver _PESO_DISTANCIA_* em job.py). Um erro tira ou põe um
ponto no ranking; nunca descarta vaga.
"""

import re

from math import asin, cos, radians, sin, sqrt

# Brás, São Paulo — bairro onde o usuário mora.
_ANCORA = (-23.5470, -46.6120)

# Raio confortável declarado pelo usuário. Dentro disso, sem desconto.
RAIO_IDEAL_KM = 11

# CEP de São Paulo e Grande SP é organizado geograficamente, então os 3
# primeiros dígitos já situam a região — é o sinal mais preciso disponível
# sem geocodificar, e a Gupy entrega o CEP no endereço da vaga
# ("Avenida das Nações Unidas, 14261, São Paulo, ..., 04795-100").
#
# Faixas (início, fim, latitude, longitude, nome) — nome só pra log/teste.
_FAIXAS_CEP = [
    (10, 13, -23.5500, -46.6350, "Centro/Sé/Liberdade"),
    (14, 14, -23.5620, -46.6650, "Jardins/Cerqueira César"),
    (15, 15, -23.5680, -46.6280, "Aclimação/Cambuci"),
    (16, 19, -23.5250, -46.6650, "Barra Funda/Água Branca"),
    (20, 29, -23.4900, -46.6250, "Zona Norte"),
    (30, 31, -23.5450, -46.6050, "Brás/Mooca/Belenzinho"),
    (32, 35, -23.5400, -46.5600, "Tatuapé/Penha"),
    (36, 39, -23.5200, -46.4800, "Zona Leste distante"),
    (40, 41, -23.5850, -46.6400, "Vila Mariana/Paraíso"),
    (42, 43, -23.6300, -46.6400, "Saúde/Jabaquara"),
    (44, 44, -23.6300, -46.6200, "Cursino/Vila Guarani"),
    (45, 45, -23.5900, -46.6800, "Itaim Bibi/Vila Olímpia/Moema"),
    (46, 47, -23.6250, -46.7000, "Santo Amaro/Brooklin/Berrini"),
    (48, 49, -23.6600, -46.7600, "Campo Limpo/Capão Redondo"),
    (50, 59, -23.5600, -46.7100, "Zona Oeste (Pinheiros/Butantã/Lapa)"),
    (60, 69, -23.5100, -46.8500, "Osasco/Barueri/Alphaville"),
    (70, 79, -23.4600, -46.5300, "Guarulhos"),
    (80, 89, -23.5400, -46.4500, "Zona Leste extrema/Itaquera"),
    (90, 99, -23.6600, -46.5400, "ABC"),
    (110, 119, -23.9600, -46.3300, "Baixada Santista"),
    (130, 139, -22.9100, -47.0600, "Campinas"),
]

# Fallback quando não há CEP no texto (LinkedIn, Sólides e afins só dizem a
# cidade). "São Paulo" sozinho usa o centro geográfico da capital: dentro do
# raio, portanto sem desconto — mesma escolha de "não penalizar por falta de
# informação" que o eixo de senioridade já faz.
_COORDENADAS_CIDADE = {
    "sao paulo": (-23.5600, -46.6400),
    "barueri": (-23.5100, -46.8760),
    "alphaville": (-23.4930, -46.8520),
    "osasco": (-23.5320, -46.7920),
    "guarulhos": (-23.4540, -46.5330),
    "santo andre": (-23.6640, -46.5380),
    "sao bernardo": (-23.6940, -46.5650),
    "sao caetano": (-23.6180, -46.5560),
    "diadema": (-23.6860, -46.6230),
    "cotia": (-23.6030, -46.9190),
    "campinas": (-22.9100, -47.0600),
}

_PADRAO_CEP = re.compile(r"\b(\d{5})-?(\d{3})\b")
_MODALIDADES_COM_DESLOCAMENTO = ("presencial", "hibrido", "híbrido")

_RAIO_TERRA_KM = 6371.0


def _haversine(origem: tuple[float, float], destino: tuple[float, float]) -> float:
    lat1, lon1 = radians(origem[0]), radians(origem[1])
    lat2, lon2 = radians(destino[0]), radians(destino[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * _RAIO_TERRA_KM * asin(sqrt(a))


def _coordenadas_por_cep(texto: str) -> tuple[float, float] | None:
    m = _PADRAO_CEP.search(texto)
    if not m:
        return None
    prefixo = int(m.group(1)[:3])
    for inicio, fim, lat, lon, _nome in _FAIXAS_CEP:
        if inicio <= prefixo <= fim:
            return (lat, lon)
    return None


def _coordenadas_por_cidade(texto: str) -> tuple[float, float] | None:
    from job import _normalizar  # import local: evita ciclo (job não importa geo)

    texto_norm = _normalizar(texto)

    # "São Paulo" é testado POR ÚLTIMO porque é cidade E estado, e o texto
    # de local quase sempre traz os dois: "Campinas, São Paulo, Brazil".
    # MEDIDO nas vagas reais do ATS — Campinas (84 km) e Barueri (27 km)
    # eram medidas como 3,2 km, a distância do centro da capital, porque o
    # nome do ESTADO batia antes do nome da cidade. Ordenar por tamanho do
    # nome (a heurística anterior) não resolve: "são paulo" tem 9 letras e
    # "campinas" tem 8, então o estado ganhava.
    especificas = [n for n in _COORDENADAS_CIDADE if n != "sao paulo"]
    for nome in sorted(especificas, key=len, reverse=True):
        if nome in texto_norm:
            return _COORDENADAS_CIDADE[nome]

    if "sao paulo" in texto_norm:
        return _COORDENADAS_CIDADE["sao paulo"]
    return None


def distancia_km(texto_local: str, modalidade: str) -> float | None:
    """Distância entre a vaga e a âncora, em km. None quando não se aplica
    (vaga remota) ou quando não dá pra situar o endereço.

    `texto_local` pode ser o endereço completo da vaga (com CEP, quando a
    fonte expõe — ver scrapers/descricao_gupy.py) ou só o texto de local do
    card ("São Paulo - SP"). Quanto mais específico, melhor a estimativa.
    """
    from job import _normalizar

    if _normalizar(modalidade) not in [_normalizar(m) for m in _MODALIDADES_COM_DESLOCAMENTO]:
        return None

    coordenadas = _coordenadas_por_cep(texto_local) or _coordenadas_por_cidade(texto_local)
    if coordenadas is None:
        return None

    return round(_haversine(_ANCORA, coordenadas), 1)

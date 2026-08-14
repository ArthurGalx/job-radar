from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit
import hashlib
import re
import unicodedata


def _normalizar(texto: str) -> str:
    """Minúsculo e sem acento, pra comparação não depender de site nenhum
    escrever "Maceio"/"Maceió", "e-commerce"/"ecommerce" etc. de forma
    diferente da nossa lista de keywords/cidades."""
    sem_acento = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sem_acento if not unicodedata.combining(c))


def _contem_termo(termo: str, texto: str) -> bool:
    """Substring com borda de palavra (\\b), não substring cru.

    "bi" solto como substring pegava qualquer palavra que contivesse "bi" no
    meio — "bilíngue", "híbrido" (normalizado "hibrido"), "habilidade" etc.
    Com \\b, "bi" só bate como palavra isolada, mas termos com espaço tipo
    "power bi" continuam funcionando igual.
    """
    return re.search(rf"\b{re.escape(termo)}\b", texto) is not None


def _tem_termo(termo: str, texto: str) -> bool:
    """Casa o termo como palavra inteira (aceitando plural em -s).

    Sem isso, termo curto casa dentro de outra palavra: "bi" casaria em
    "mo(bi)le", "am(bi)ente" e "(bi)lingue", furando a regra que exige
    qualificador de verdade no título.
    """
    return re.search(rf"(?<!\w){re.escape(termo)}s?(?!\w)", texto) is not None


# Vocabulário de "é vaga remota" usado no campo local. Antes só tinha
# "remot" + "home office" — "Remote" (inglês) só passava por acidente, por
# conter a substring "remot", e faltava vocabulário que não compartilha
# essa raiz: "teletrabalho" (termo padrão em Portugal), "work from home",
# "anywhere". Centralizado aqui em vez de espalhado, e documentado que
# "remot" sozinho já cobre bastante coisa por ser raiz de palavra, não uma
# palavra fixa: Remoto, Remota, Remote, Trabalho Remoto, 100% Remoto,
# Fully Remote — todas contêm "remot" em algum ponto.
TERMOS_REMOTO = [
    "remot",  # raiz: Remoto/Remota/Remote/Trabalho Remoto/100% Remoto/Fully Remote
    "home office",
    "work from home",
    "trabalhe de casa",  # variante em português vista ao vivo no Catho
    "teletrabalho",
    "anywhere",
]


def _e_remoto(texto: str) -> bool:
    return any(termo in texto for termo in TERMOS_REMOTO)


# Padrões de data confirmados ao vivo neste projeto: "Publicada em 11/08"
# (Catho) e "Há 4 meses" / "Há 3 semanas" (LinkedIn, no card de busca).
# Regex sobre o TEXTO INTEIRO do card, em vez de um seletor CSS por site —
# cada fonte marca isso de um jeito diferente (às vezes nem tag própria,
# só texto solto), e adivinhar seletor sem inspecionar o DOM ao vivo é
# arriscado (podia quebrar silenciosamente ou pegar texto errado). Regex
# sobre o texto renderizado funciona em qualquer site sem esse risco — na
# pior hipótese não acha nada e publicado_em fica "" (aceitável, "quando
# existir").
_PADRAO_DATA_ABSOLUTA = re.compile(
    r"publicad[ao]\s+(?:em|há)?\s*:?\s*"
    r"(\d{1,2}\s+de\s+\w+(?:\s+de\s+\d{2,4})?|\d{1,2}/\d{1,2}(?:/\d{2,4})?)",
    re.IGNORECASE,
)
_PADRAO_DATA_RELATIVA = re.compile(
    # Plural como sufixo opcional (dias?/semanas?/anos?), não alternativa
    # separada — "dia|dias" bate "dia" primeiro e para aí, cortando o "s"
    # de "dias" (regex não escolhe o match mais longo, escolhe o primeiro).
    r"há\s+\d+\s+(?:dias?|semanas?|m[êe]s(?:es)?|anos?)",
    re.IGNORECASE,
)
_PADRAO_HOJE_ONTEM = re.compile(r"\b(hoje|ontem)\b", re.IGNORECASE)


def extrair_data_publicacao(texto_card: str) -> str:
    """Procura sinal de data de publicação no texto renderizado de um card
    de vaga. Cobre formato absoluto ("Publicada em 11/08", "Publicada em 11
    de agosto de 2026") e relativo ("Há 4 meses"). Retorna "" quando o site
    não expõe isso no card de busca — nem toda fonte tem.
    """
    for padrao in (_PADRAO_DATA_ABSOLUTA, _PADRAO_DATA_RELATIVA, _PADRAO_HOJE_ONTEM):
        m = padrao.search(texto_card)
        if m:
            return m.group(0).strip()
    return ""


# Ordem importa: do mais específico pro mais genérico. Título não é
# filtrado por senioridade — só é classificado, pra decidir isso na hora de
# ler a notificação, não em deixar a vaga passar ou não.
_NIVEIS_SENIORIDADE = [
    ("Estágio/Trainee", (r"estagi[ao]", r"estagio", r"trainee")),
    ("Júnior", (r"junior", r"jr\.?")),
    ("Pleno", (r"pleno", r"pl\.?")),
    ("Sênior", (r"senior", r"sr\.?", r"sênior")),
    ("Especialista", (r"especialista", r"specialist")),
    ("Liderança", (r"coordenador", r"coordenadora", r"gerente", r"manager", r"head")),
]


def _detectar_senioridade(titulo: str) -> str:
    """Classifica o nível pelo título, sem excluir nada — a ideia é decidir
    na hora de ler a notificação se vale a pena abrir o link, não descartar
    vaga automaticamente (júnior pode virar sênior lendo a descrição, e
    "PL"/"Sr" no título nem sempre reflete o que a empresa pede de verdade).
    """
    titulo_norm = _normalizar(titulo)

    for nivel, padroes in _NIVEIS_SENIORIDADE:
        for padrao in padroes:
            if re.search(rf"(?<!\w){padrao}(?!\w)", titulo_norm):
                return nivel

    numeral = re.search(r"(?<!\w)(i{1,3}|iv)(?!\w)", titulo_norm)
    if numeral:
        return f"Nível {numeral.group(1).upper()}"

    return "Não especificado"


@dataclass
class Job:
    titulo: str
    empresa: str
    local: str
    link: str
    site: str
    # Data anunciada pela FONTE (não a data em que o JobRadar achou a vaga —
    # essa já existe em vagas_vistas.encontrada_em). Sem isso não dá pra
    # medir latência real (quanto tempo entre a vaga ser publicada e o
    # JobRadar notificar) nem priorizar vaga recente na notificação. Formato
    # livre (string), porque cada site anuncia diferente — data absoluta
    # ("11/08", "11 de agosto de 2026"), timestamp ISO (Trampos), ou texto
    # relativo ("Há 4 meses", "Contratando agora"). Normalizar tudo pra um
    # formato único exigiria parser por site (relativo→absoluto), fora do
    # escopo agora — string crua já é suficiente pra exibir na notificação e
    # é o que a fonte realmente disse. "" quando o site não expõe a data.
    publicado_em: str = ""
    # Modalidade (Remoto/Híbrido/Presencial) como campo PRÓPRIO, preenchido
    # pelo scraper na hora da extração. Antes vivia embutida dentro do texto
    # de `local` (ex: "São Paulo - SP (Remoto)") e era redetectada por
    # substring toda vez que combina_com() rodava — inclusive mais de uma
    # vez pra mesma vaga, quando o pipeline internacional roda a mesma lista
    # de vagas contra CIDADES_INTL e depois CIDADES_EUROPA_IBERICA. Detectar
    # uma vez, na fonte, e guardar aqui elimina o retrabalho e mantém
    # `local` só com informação de localização de verdade. Valores usados:
    # "Remoto", "Híbrido", "Presencial", ou "" quando a fonte não expõe.
    modalidade: str = ""

    @property
    def id(self) -> str:
        """Identificador único da vaga, baseado no link (evita duplicatas).

        O hash usa o link sem query string (?utm_source=..., ?jobBoardSource=...
        etc.), porque alguns sites variam esses parâmetros entre visitas à
        mesma vaga — se entrassem no hash, a mesma vaga poderia gerar IDs
        diferentes em runs distintos e disparar notificação duplicada.
        """
        partes = urlsplit(self.link)
        link_normalizado = urlunsplit((partes.scheme, partes.netloc, partes.path, "", ""))
        return hashlib.md5(link_normalizado.encode()).hexdigest()

    @property
    def chave_secundaria(self) -> str:
        """Chave de dedup secundária: empresa + título normalizados.

        O `.id` sozinho é hash da URL — a mesma vaga publicada em fontes
        diferentes (ex: Gupy e LinkedIn, ou LinkedIn BR e LinkedIn Intl) tem
        URL diferente em cada uma, então o `.id` também diverge e a vaga
        passa como "nova" mais de uma vez. Medido: 23% de repetição (60
        registros pra 46 pares distintos). Empresa+título normalizados
        (minúsculo, sem acento) captura isso mesmo com pequena variação de
        formatação entre sites.
        """
        return f"{_normalizar(self.empresa)}|{_normalizar(self.titulo)}"

    @property
    def senioridade(self) -> str:
        """Nível classificado a partir do título (Júnior/Pleno/Sênior/...).

        Isso é só informativo pra notificação — a vaga não é excluída por
        senioridade em nenhum momento do filtro.
        """
        return _detectar_senioridade(self.titulo)

    def combina_com(
        self,
        keywords_forte: list[str],
        keywords_ambiguo: list[str],
        qualificadores_dados: list[str],
        ferramentas_titulo: list[str],
        qualificadores_cargo: list[str],
        cidades: list[str],
    ) -> bool:
        """Verifica se a vaga bate com pelo menos uma keyword E uma cidade/modalidade.

        Cargo e localização são checados em campos separados (título e local,
        respectivamente) — antes eram concatenados num texto só, o que causava
        falso positivo: vaga americana com "Hybrid Remote" no TÍTULO batia
        com "remot" e passava como se fosse remota no Brasil, mesmo com
        local="Bloomington, IN". Cada critério agora só pode bater no campo
        que realmente representa.

        Título e local também são normalizados (minúsculo, sem acento) antes
        de comparar, assim como as keywords/cidades — evita falha de match
        por site escrever "Maceio" sem acento, ou por qualquer inconsistência
        de acentuação entre o texto do site e o que está no config.py.

        Cargo tem duas regras diferentes:
        - keywords_forte: só existe mesmo em vaga de dados/BI, basta bater no
          título.
        - keywords_ambiguo: também é usado em vaga de outra área (ex:
          "Business Analyst" existe em RH, finanças etc.) — só conta se o
          título TAMBÉM tiver um dos qualificadores (ex: "dados", "sql",
          "power bi"). É o que permite ir adicionando cargo adjacente
          (Product Analyst, CRM Analyst, Marketing Analyst) sem cada um virar
          fonte de ruído sozinho.
        """
        titulo_norm = _normalizar(self.titulo)
        local_norm = _normalizar(self.local)
        modalidade_norm = _normalizar(self.modalidade)

        bate_forte = any(_contem_termo(_normalizar(k), titulo_norm) for k in keywords_forte)

        bate_ambiguo = any(_normalizar(k) in titulo_norm for k in keywords_ambiguo) and any(
            _tem_termo(_normalizar(q), titulo_norm) for q in qualificadores_dados
        )

        # Espelho da regra acima: ferramenta no título só vale com cargo junto.
        bate_ferramenta = any(
            _normalizar(f) in titulo_norm for f in ferramentas_titulo
        ) and any(_tem_termo(_normalizar(q), titulo_norm) for q in qualificadores_cargo)

        bate_keyword = bate_forte or bate_ambiguo or bate_ferramenta

        # Antes: _e_remoto(local_norm), redetectando por substring dentro de
        # `local` toda vez que combina_com() rodava (inclusive mais de uma
        # vez pra mesma vaga, no pipeline internacional). Agora o scraper
        # já classifica a modalidade uma vez, na extração, e aqui só se lê o
        # campo — sem reparsear texto.
        quer_remoto = any(_normalizar(c) in ("remoto", "remota") for c in cidades)
        bate_remoto = quer_remoto and modalidade_norm in ("remoto", "remota")

        bate_cidade = bate_remoto or any(
            _contem_termo(_normalizar(c), local_norm)
            for c in cidades
            if _normalizar(c) not in ("remoto", "remota")
        )

        return bate_keyword and bate_cidade
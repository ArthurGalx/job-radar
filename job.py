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

        bate_forte = any(_contem_termo(_normalizar(k), titulo_norm) for k in keywords_forte)

        bate_ambiguo = any(_normalizar(k) in titulo_norm for k in keywords_ambiguo) and any(
            _tem_termo(_normalizar(q), titulo_norm) for q in qualificadores_dados
        )

        # Espelho da regra acima: ferramenta no título só vale com cargo junto.
        bate_ferramenta = any(
            _normalizar(f) in titulo_norm for f in ferramentas_titulo
        ) and any(_tem_termo(_normalizar(q), titulo_norm) for q in qualificadores_cargo)

        bate_keyword = bate_forte or bate_ambiguo or bate_ferramenta

        quer_remoto = any(_normalizar(c) in ("remoto", "remota") for c in cidades)
        bate_remoto = quer_remoto and _e_remoto(local_norm)

        bate_cidade = bate_remoto or any(
            _contem_termo(_normalizar(c), local_norm)
            for c in cidades
            if _normalizar(c) not in ("remoto", "remota")
        )

        return bate_keyword and bate_cidade
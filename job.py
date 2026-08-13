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

    def combina_com(
        self,
        keywords_forte: list[str],
        keywords_ambiguo: list[str],
        qualificadores: list[str],
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

        bate_ambiguo = any(
            _contem_termo(_normalizar(k), titulo_norm) for k in keywords_ambiguo
        ) and any(_contem_termo(_normalizar(q), titulo_norm) for q in qualificadores)

        bate_keyword = bate_forte or bate_ambiguo

        # "remot" (sem \b de propósito — cobre Remoto/Remota/100% Remoto/etc,
        # e é uma raiz de palavra, não uma palavra curta tipo "bi" que
        # aparece dentro de outras) e "home office" cobrem as variações
        # usadas pelos diferentes sites.
        quer_remoto = any(_normalizar(c) in ("remoto", "remota") for c in cidades)
        bate_remoto = quer_remoto and ("remot" in local_norm or "home office" in local_norm)

        bate_cidade = bate_remoto or any(
            _contem_termo(_normalizar(c), local_norm)
            for c in cidades
            if _normalizar(c) not in ("remoto", "remota")
        )

        return bate_keyword and bate_cidade
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit
import hashlib


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

    def combina_com(self, keywords: list[str], cidades: list[str]) -> bool:
        """Verifica se a vaga bate com pelo menos uma keyword E uma cidade/modalidade."""
        texto = f"{self.titulo} {self.local}".lower()

        bate_keyword = any(k.lower() in texto for k in keywords)

        # "remot" cobre as variações usadas pelos diferentes sites
        # (Remoto, Remota, 100% Remoto, Home Office, etc.)
        quer_remoto = any(c.lower() in ("remoto", "remota") for c in cidades)
        bate_remoto = quer_remoto and ("remot" in texto or "home office" in texto)

        bate_cidade = bate_remoto or any(
            c.lower() in texto for c in cidades if c.lower() not in ("remoto", "remota")
        )

        return bate_keyword and bate_cidade
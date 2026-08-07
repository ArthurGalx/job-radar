from dataclasses import dataclass
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
        """Identificador único da vaga, baseado no link (evita duplicatas)."""
        return hashlib.md5(self.link.encode()).hexdigest()

    def combina_com(self, keywords: list[str], cidades: list[str]) -> bool:
        """Verifica se a vaga bate com pelo menos uma keyword E uma cidade/modalidade."""
        texto = f"{self.titulo} {self.local}".lower()

        bate_keyword = any(k.lower() in texto for k in keywords)
        bate_cidade = any(c.lower() in texto for c in cidades)

        return bate_keyword and bate_cidade
"""Vagas direto do ATS das empresas (Greenhouse, Lever, Ashby).

É a fonte de maior qualidade do projeto, e a mais barata: as três
plataformas publicam o quadro de vagas em API JSON pública, sem login, sem
anti-bot e sem navegador — uma requisição por empresa devolve o catálogo
inteiro.

Três diferenças em relação a todo o resto do projeto, todas de propósito:

1. NÃO usa termos de busca. As APIs não têm parâmetro de pesquisa: elas
   devolvem tudo que a empresa tem aberto, e quem filtra é o nosso próprio
   filtro de cargo/cidade (ver job.combina_com). Isso deixa esta fonte
   FORA do rodízio de termos — enquanto as outras veem 10 termos por
   ciclo, aqui todo ciclo enxerga o catálogo completo dessas empresas.
   `termos_busca` é aceito só pra manter a interface igual à das outras
   fontes (ver perfis.DefinicaoScraper).

2. Já traz a DESCRIÇÃO da vaga. As outras fontes só dão título/empresa/
   local no card, e a descrição precisa de uma segunda requisição (ver
   scrapers/descricao_*.py). Aqui ela vem no mesmo JSON, então os eixos de
   afinidade e barreira do score (ver job.pontuar_relevancia) funcionam
   desde o primeiro ciclo, de graça.

3. A lista de empresas é CURADA, não descoberta. É a limitação real desta
   fonte: ela só enxerga quem está na lista de EMPRESAS_ATS (config.py).
   Empresa nova exige descobrir em qual plataforma ela está — nem toda usa
   uma das três, e o slug nem sempre é o nome óbvio.

MEDIDO ao vivo na descoberta da lista: das ~120 empresas de tecnologia
brasileiras testadas, 22 responderam em alguma das três APIs, com de 2 a
416 vagas cada. Stone, Agibank, XP, C6 e Inter concentram o volume; VTEX,
RD Station, Cortex e Jusbrasil são as mais aderentes ao perfil de produto.
"""

import html
import re

import requests

from job import Job
from logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()

_TIMEOUT = 25
_CABECALHOS = {"User-Agent": "Mozilla/5.0 (compatible; JobRadar/1.0)"}

_PADRAO_TAG = re.compile(r"<[^>]+>")
_PADRAO_QUEBRA = re.compile(r"</(?:p|div|li|h[1-6])>|<br\s*/?>", re.IGNORECASE)
_PADRAO_LINHAS_VAZIAS = re.compile(r"\n{3,}")

# Mesmo limite do resto do projeto (ver scrapers/descricao_comum.py).
MAX_CARACTERES = 6000

_TERMOS_REMOTO = ("remote", "remoto", "home office", "anywhere", "teletrabalho")
_TERMOS_HIBRIDO = ("hybrid", "híbrido", "hibrido")


def _limpar(texto: str) -> str:
    """MEDIDO na descrição real da VTEX: o Greenhouse devolve o HTML
    ESCAPADO ("&lt;p data-path-to-node=&quot;2&quot;&gt;"), então
    desescapar tem que vir ANTES de tirar tag — na ordem inversa, o regex
    de tag não encontra nada e o texto final fica com as tags visíveis.

    Não era só feiura: o atributo `data-path-to-node` sobrevivia no texto,
    e "data" com borda de palavra (o hífen conta como borda) fazia o eixo
    de afinidade marcar o grupo "dados" em QUALQUER vaga do Greenhouse —
    ponto inventado, na fonte que mais traz vaga.

    O segundo unescape é pras entidades que só aparecem depois que a tag
    sai (&nbsp;, &amp; dentro do texto).
    """
    if not texto:
        return ""
    texto = html.unescape(texto)
    texto = _PADRAO_QUEBRA.sub("\n", texto)
    texto = _PADRAO_TAG.sub("", texto)
    texto = html.unescape(texto)
    linhas = [linha.strip() for linha in texto.splitlines()]
    return _PADRAO_LINHAS_VAZIAS.sub("\n\n", "\n".join(linhas)).strip()[:MAX_CARACTERES]


def _modalidade(texto_local: str, remoto_declarado: bool | None = None) -> str:
    """Ashby e Lever declaram a modalidade num campo próprio; o Greenhouse
    não tem campo nenhum e só resta ler o texto do local. Quando a fonte
    declara, a declaração vence."""
    if remoto_declarado:
        return "Remoto"
    local_norm = texto_local.lower()
    if any(t in local_norm for t in _TERMOS_HIBRIDO):
        return "Híbrido"
    if any(t in local_norm for t in _TERMOS_REMOTO):
        return "Remoto"
    return "Presencial"


class AtsScraper(BaseScraper):
    """Uma instância cobre TODAS as empresas de EMPRESAS_ATS — não uma por
    empresa. Cada empresa é uma requisição, e falha numa não derruba as
    outras (a API pode estar fora, o slug pode ter mudado quando a empresa
    troca de plano ou de plataforma)."""

    def __init__(self, termos_busca: list[str], empresas: list[tuple[str, str, str]]):
        self.termos_busca = termos_busca  # ignorado de propósito — ver docstring do módulo
        self.empresas = empresas

    def buscar_vagas(self) -> list[Job]:
        # site="ATS" pra TODAS as empresas (o nome vai em `empresa`): o
        # relatório de precisão agrupa por site, e 22 valores distintos
        # picotariam a métrica em amostras de 2 ou 3 vagas, sem permitir
        # comparar esta fonte com Gupy/LinkedIn.
        vagas: list[Job] = []
        for nome, plataforma, slug in self.empresas:
            try:
                vagas.extend(self._buscar_empresa(nome, plataforma, slug))
            except requests.RequestException as e:
                logger.warning(f"[ATS] {nome} ({plataforma}): {type(e).__name__}")
            except (ValueError, KeyError, TypeError):
                logger.warning(f"[ATS] {nome} ({plataforma}): resposta fora do formato esperado.")

        logger.info(f"[ATS] {len(vagas)} vaga(s) encontrada(s) em {len(self.empresas)} empresa(s)")
        return vagas

    def _buscar_empresa(self, nome: str, plataforma: str, slug: str) -> list[Job]:
        if plataforma == "greenhouse":
            return self._greenhouse(nome, slug)
        if plataforma == "lever":
            return self._lever(nome, slug)
        if plataforma == "ashby":
            return self._ashby(nome, slug)
        logger.warning(f"[ATS] plataforma desconhecida para {nome}: {plataforma}")
        return []

    def _get(self, url: str):
        resposta = requests.get(url, timeout=_TIMEOUT, headers=_CABECALHOS)
        resposta.raise_for_status()
        return resposta.json()

    def _greenhouse(self, nome: str, slug: str) -> list[Job]:
        # content=true traz a descrição junto da lista. Sem isso seria uma
        # requisição por vaga (N+1) pra ter o texto que alimenta o score.
        dados = self._get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
        vagas = []
        for v in dados.get("jobs", []):
            local = (v.get("location") or {}).get("name", "") or ""
            job = Job(
                titulo=v.get("title", ""),
                empresa=nome,
                local=local,
                link=v.get("absolute_url", ""),
                site="ATS",
                modalidade=_modalidade(local),
                publicado_em=(v.get("updated_at") or "")[:10],
            )
            job.descricao = _limpar(v.get("content", ""))
            vagas.append(job)
        return vagas

    def _lever(self, nome: str, slug: str) -> list[Job]:
        dados = self._get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
        vagas = []
        for v in dados:
            categorias = v.get("categories") or {}
            local = categorias.get("location", "") or ""
            tipo = (v.get("workplaceType") or "").lower()
            job = Job(
                titulo=v.get("text", ""),
                empresa=nome,
                local=local,
                link=v.get("hostedUrl", ""),
                site="ATS",
                modalidade=_modalidade(local, remoto_declarado=tipo == "remote"),
            )
            # A Lever quebra o texto em vários campos e nem sempre preenche
            # descriptionPlain — juntar os três cobre os dois formatos que
            # apareceram no teste.
            job.descricao = _limpar(
                "\n\n".join(
                    filter(None, [
                        v.get("descriptionPlain") or v.get("description") or "",
                        v.get("descriptionBodyPlain") or v.get("descriptionBody") or "",
                        v.get("additionalPlain") or v.get("additional") or "",
                    ])
                )
            )
            vagas.append(job)
        return vagas

    def _ashby(self, nome: str, slug: str) -> list[Job]:
        dados = self._get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
        vagas = []
        for v in dados.get("jobs", []):
            local = v.get("location", "") or ""
            job = Job(
                titulo=v.get("title", ""),
                empresa=nome,
                local=local,
                link=v.get("jobUrl", ""),
                site="ATS",
                modalidade=_modalidade(local, remoto_declarado=bool(v.get("isRemote"))),
                publicado_em=(v.get("publishedAt") or "")[:10],
            )
            job.descricao = _limpar(v.get("descriptionPlain", "") or v.get("descriptionHtml", ""))
            vagas.append(job)
        return vagas

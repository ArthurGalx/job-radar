"""Export das vagas aprovadas pra uma planilha do Google Sheets.

Canal EXTRA, paralelo ao Telegram: a notificação continua sendo o caminho
principal (vaga boa some rápido, e o Telegram é o que chega no celular na
hora), e a planilha é onde a vaga vira lista de trabalho — dá pra filtrar,
ordenar, anotar em que fase da candidatura está, sem depender de rolar o
histórico do chat.

Escrita via Apps Script publicado como web app (código em
docs/planilha_apps_script.gs), não via API do Google Cloud: evita projeto
no GCP, service account e JSON de credencial pra uma integração que só
precisa de "append de uma linha". O custo dessa escolha é que a URL do web
app é, na prática, uma credencial — quem tem a URL escreve na planilha —
daí ela vir de secret e o Apps Script ainda exigir SHEETS_TOKEN no corpo
do POST.

REGRA DE OURO: falha aqui NUNCA pode derrubar o ciclo nem impedir que a
vaga seja notificada/salva. O projeto inteiro é construído em cima de
"nunca marcar como vista sem confirmar que a notificação saiu" (ver
main.py); a planilha é o oposto disso — best-effort, loga e segue. Por
isso exportar_vaga() devolve bool mas nenhum chamador é obrigado a olhar.
"""

from datetime import datetime, timezone

import requests

from config import SHEETS_WEBHOOK_URL, SHEETS_TOKEN
from logger import get_logger

logger = get_logger()

# Ordem das colunas na planilha. Vive aqui (e não só no Apps Script) porque
# é o Python que monta a linha; o script do lado do Google só recebe o
# dicionário e escreve na ordem que ESTA lista define, enviada junto no
# payload. Sem isso, acrescentar um campo exigiria editar o script dentro
# da planilha de novo — e o script publicado é a parte mais chata de
# atualizar (precisa republicar o deployment).
COLUNAS = [
    "encontrada_em",
    "perfil",
    "canal",
    "titulo",
    "empresa",
    "local",
    "modalidade",
    "senioridade",
    "relevancia",
    "motivo",
    "fonte",
    "publicado_em",
    # Data-limite de inscrição em ISO (ordena na planilha; ver
    # Job.prazo_inscricao). Só programa de trainee e vaga da Gupy
    # costumam ter — nas outras fica vazia.
    "prazo_inscricao",
    "link",
    # NÃO existe coluna de acompanhamento aqui (havia uma, `situacao`,
    # nascendo sempre como "não avaliada"). O usuário criou as dele na
    # própria planilha — "Fiz inscrição?", "Respondeu?", "Negou",
    # "Aceitou?" — que são checkbox e descrevem o funil melhor do que um
    # campo de texto livre que o robô nunca atualizava. Duas colunas pro
    # mesmo fim, uma delas sempre com o mesmo valor, é ruído.
    #
    # A coluna `situacao` do BANCO continua existindo (ver
    # _garantir_coluna_situacao em database/database.py): é herança do
    # projeto original, também nunca usada de fato, e removê-la exigiria
    # migração de schema sem ganho nenhum.

    # Só preenchida em vaga que passou do LIMIAR_CARTA numa fonte com
    # descrição disponível (ver FONTES_COM_DESCRICAO e main.py) — nas
    # outras fica vazia. É o texto do anúncio, que o card de busca não traz
    # e sem o qual não dá pra escrever candidatura personalizada.
    "descricao",
]


def montar_linha(
    job,
    perfil_nome: str,
    canal: str,
    motivo: str,
    exploratoria: bool = False,
    descricao: str = "",
) -> dict:
    """Traduz um Job na linha que vai pra planilha.

    Função pura (não faz rede, não lê config) de propósito: é a parte que
    tem regra de verdade e a que dá pra testar sem tocar no Google.

    `canal` é "imediata" ou "digest" — o mesmo corte que decide se a vaga
    vira mensagem na hora ou entra na fila do resumo diário (ver
    LIMIAR_DIGEST_IMEDIATO). Vai pra planilha porque é a informação que
    some no Telegram: no chat dá pra ver que chegou, não POR QUE chegou
    daquele jeito.
    """
    return {
        # Data em que o RADAR achou a vaga (UTC, como o resto do projeto —
        # o workflow roda em UTC). Diferente de publicado_em, que é o que a
        # FONTE anunciou e vem em formato livre (ver Job.publicado_em).
        "encontrada_em": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "perfil": perfil_nome,
        "canal": f"{canal} (exploratória)" if exploratoria else canal,
        "titulo": job.titulo,
        "empresa": job.empresa,
        "local": job.local,
        "modalidade": job.modalidade,
        "senioridade": job.senioridade,
        "relevancia": job.relevancia,
        "motivo": motivo,
        "fonte": job.site,
        "publicado_em": job.publicado_em,
        "prazo_inscricao": job.prazo_inscricao,
        "link": job.link,
        "descricao": descricao,
    }


def exportar_vaga(
    job,
    perfil_nome: str,
    canal: str,
    motivo: str,
    exploratoria: bool = False,
    descricao: str = "",
) -> bool:
    """Manda uma vaga pra planilha. Devolve False (sem levantar exceção) em
    qualquer falha — inclusive quando o export nem está configurado."""
    if not SHEETS_WEBHOOK_URL or not SHEETS_TOKEN:
        return False

    payload = {
        "token": SHEETS_TOKEN,
        "colunas": COLUNAS,
        "linha": montar_linha(job, perfil_nome, canal, motivo, exploratoria, descricao),
    }

    try:
        resposta = requests.post(SHEETS_WEBHOOK_URL, json=payload, timeout=15)
        resposta.raise_for_status()
        return True
    # Mesma disciplina de log do notifier/telegram.py: NUNCA logar `str(e)`
    # nem a URL — a mensagem de erro do requests inclui a URL completa, e
    # aqui ela é justamente o segredo que dá escrita na planilha. O log vai
    # pro stdout do GitHub Actions, visível em qualquer execução.
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        logger.error(f"Erro ao exportar vaga pra planilha: HTTP {status}")
        return False
    except requests.RequestException as e:
        logger.error(
            f"Erro ao exportar vaga pra planilha: {type(e).__name__} "
            "(falha de conexão, sem resposta do servidor)"
        )
        return False

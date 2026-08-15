# JobRadar

Monitor automatizado de vagas de Dados/BI. Roda em cron (GitHub Actions), busca em 8 fontes diferentes (LinkedIn e Indeed cobrindo dois mercados cada, com scraper próprio por mercado), filtra por cargo/cidade/mercado/idioma, pontua por relevância e notifica no Telegram — sem servidor próprio, sem custo de infraestrutura, sem intervenção manual.

Nasceu de um problema concreto: cidade pequena do Nordeste, vaga de Dados/BI aparece pouco e cedo — quem checa o board 2x por dia perde a vaga pra quem checou na primeira hora. O projeto existe pra checar o board a cada 3h, os 365 dias do ano, e só interromper quando há algo relevante pra ver.

## O que ele faz

A cada ciclo (3 em 3 horas), para cada um dos dois perfis de mercado configurados:

1. Busca vagas em paralelo em várias fontes (LinkedIn, Gupy, Indeed, Catho, Solides, GeekHunter, 99Jobs, We Work Remotely), usando um bloco rotativo de termos de busca.
2. Filtra por cargo (título bate com uma lista de cargos de Dados/BI), cidade/mercado (Nordeste do Brasil, ou remoto aceito pelo mercado configurado) e, no perfil internacional, idioma (espanhol/português).
3. Pontua cada vaga aprovada por relevância (0–10) — cargo forte, ferramenta no título, senioridade, mercado confirmado, idioma.
4. Verifica duplicata contra o histórico (por link e por empresa+título, pra pegar a mesma vaga republicada em fontes diferentes).
5. Notifica: vaga de alta relevância vai na hora pro Telegram; o resto entra numa fila e sai uma vez por dia, num digest ranqueado (melhor vaga no topo).
6. Grava o resultado em SQLite (`data/jobs.db`), que é commitado de volta no próprio repositório a cada execução — o histórico de vagas já vistas *é* o banco de dados versionado.

Tudo isso roda de graça na infraestrutura do GitHub Actions. Não há servidor, não há banco externo, não há custo.

## Arquitetura

```
main.py                → motor único: um ciclo de busca por perfil selecionado
perfis.py              → define o que muda entre os dois mercados (Brasil / Internacional)
config.py              → dados do perfil Brasil: cargos, cidades, termos de busca, pesos
config_intl.py         → dados do perfil Internacional: cargos, países, idiomas exigidos
job.py                 → Job (dataclass), filtro (combina_com), score (pontuar_relevancia)
utils/filtro.py        → aplica RegrasFiltro numa lista de vagas brutas
scrapers/               → um módulo por fonte, todos implementando BaseScraper.buscar_vagas()
database/database.py   → SQLite: dedup, fila do digest, metadados (rodízio, heartbeat)
notifier/telegram.py   → mensagem individual e digest diário
tests/test_filtro.py   → suíte de regressão da camada de filtro (43 casos)
.github/workflows/     → jobradar.yml (cron de produção) e testes.yml (CI a cada push)
```

### Por que dois perfis e não dois programas

Existiam dois scripts quase idênticos (`main.py` e `main_intl.py`), cada um com sua própria cópia do ciclo de busca. O que muda de verdade entre "vaga no Nordeste do Brasil" e "vaga remota internacional que aceita português/espanhol" é só **dado** — fontes, termos de busca, cidades aceitas, regra de cargo, exigência de idioma. A lógica de execução (buscar → filtrar → checar dedup → notificar → salvar → alertar) é idêntica. Os dois programas viraram um objeto `Perfil` e um motor único (`main.py`), escolhido em tempo de execução via `--perfil brasil`, `--perfil internacional`, ou os dois na mesma chamada. O workflow de produção roda ambos numa única execução.

### O filtro

`Job.combina_com(regras)` decide se uma vaga passa. Não é um score, é sim/não, e usa uma escala de confiança em três níveis para o cargo:

- **Cargo forte** — título que só existe em vaga de Dados/BI ("Analista de Dados", "Business Intelligence", "Data Analyst"). Passa sozinho.
- **Cargo ambíguo** — título que também existe em outras áreas ("Business Analyst", "Analista de Negócios" existem em RH, financeiro, operações). Só passa se o título **também** tiver um qualificador de dados junto ("Business Analyst **SQL**").
- **Ferramenta no título** — mesma lógica invertida: "Power BI" sozinho pegaria vaga de desenvolvimento ("Desenvolvedor Power BI"); só passa com uma palavra de cargo de análise junto (analista, especialista, consultor — nunca "desenvolvedor"/"engenheiro").

Cidade/mercado é checado à parte: cidade brasileira aceita (whitelist do Nordeste) ou vaga remota cujo mercado declarado no texto (quando há um) é compatível — Brasil, LATAM, Portugal, Espanha para o perfil BR; qualquer país hispanofalante/lusófono para o perfil internacional. Vaga remota sem mercado declarado passa por padrão no BR; no perfil internacional, precisa que o próprio título mencione idioma ou LATAM, porque sem isso "Senior Data Analyst" remoto americano entrava igual a uma vaga que de fato aceita o Brasil.

`combina_com()`, `pontuar_relevancia()` (score) e `motivo_aprovacao()` (texto explicativo na notificação) são três métodos que leem o mesmo resultado intermediário (`Job._avaliar()`), calculado uma vez só. Isso não é acidente de design: esse projeto já teve mais de um bug nascer de duas funções calculando a mesma coisa de dois jeitos ligeiramente diferentes e divergindo em silêncio (`extrair_escopo_remoto` foi refeito mais de uma vez por causa disso). Centralizar o cálculo elimina a classe inteira de bug.

### Score de relevância

Filtro binário decide **se** notifica. O score decide **quando** e **com que destaque**: soma de 5 sinais, sem aprendizado de máquina (o conjunto é pequeno e o peso de cada sinal já é conhecido) — cargo forte (+3), ferramenta no título (+2), senioridade compatível com o alvo do usuário (Júnior/Pleno: +2; Sênior/Especialista/Liderança: −2; sem informação: +1), mercado confirmado no texto (+2, ou +1 se remoto sem mercado declarado) e idioma batendo no título (+1).

O peso negativo pra senioridade acima do alvo é deliberado: medido contra as vagas reais do banco, 25% do que passa no filtro é Sênior/Especialista/Liderança e só 5,5% é Júnior/Pleno — sem separar os dois grupos, a maioria das vagas realmente no alvo do usuário não se destacava de vaga nenhuma no ranking. O peso não filtra (a vaga continua notificando), só empurra pra baixo na fila.

Vaga com score ≥ 7 notifica na hora, mensagem individual. Abaixo disso entra numa fila e sai uma vez por dia, num digest só, ordenado da mais relevante pra menos — decisão calibrada rodando o score contra o histórico real: no limiar 7, cerca de 7% das vagas aprovadas notifica na hora e 93% vai pro digest; no limiar 6 seriam 74% imediatas (digest não reduziria ruído nenhum); no limiar 8 seriam só 2% (quase nada se destacaria). Cada mensagem de notificação também mostra o motivo da aprovação ("Cargo forte", "Ferramenta + cargo", "Cargo ambíguo + qualificador") — sem isso não dava pra perceber, só olhando o resultado, que um termo de busca estava trazendo ruído.

### Fontes

| Fonte | Perfil | Cadência | Observação |
|---|---|---|---|
| LinkedIn | Brasil + Internacional | alta | ~8,5% de rendimento (vagas notificadas / vagas brutas retornadas) — a melhor fonte de longe |
| Gupy | Brasil | alta | ~2,6% de rendimento |
| Solides | Brasil | alta | ~1,1%; paginação implementada até 3 páginas por termo |
| Indeed | Brasil + Internacional | alta | ~1,1%; paginação completa |
| Catho | Brasil | baixa | <1%, timeout frequente em execução headless |
| GeekHunter | Brasil | baixa | <1% |
| 99Jobs | Brasil | baixa | <1%, mantida — ver decisão abaixo |
| We Work Remotely | Brasil + Internacional | baixa/alta | agregador 100% remoto, cobre o mercado internacional que as fontes brasileiras não alcançam |
| Trampos | — | não usada | removida — ver decisão abaixo |
| Revelo | — | nunca implementada | exige login pra navegar; sem scraping público confiável |

"Cadência alta" roda em todo ciclo; "baixa" roda só na primeira execução do dia, pra fonte de baixo rendimento não pesar no custo de todo ciclo. Rendimento é medido em vagas notificadas contra vagas brutas retornadas por fonte — mede o quanto cada busca "acerta".

Olhando por outro ângulo — de onde vem cada vaga que já foi notificada (780 no total até o momento) — a concentração é maior ainda: LinkedIn (contando os dois perfis) responde por ~86,5%, Gupy ~5,3%, Indeed ~3,2%, Catho ~2,7%, Solides ~1,7%, GeekHunter ~0,6%. É a métrica que importa pra depender menos de uma fonte só: o endpoint não-oficial do LinkedIn (o próprio scraper documenta que costuma bloquear IP de datacenter, que é exatamente o que o GitHub Actions usa) concentra a grande maioria da entrada — se ele cair, a maior parte do volume some de uma vez. A resposta até aqui não foi "adicionar fonte por adicionar", foi medir e fazer as fontes secundárias que já existiam renderem mais (caso do Solides, abaixo).

**Trampos saiu** depois de 6 dias rendendo zero notificação. A investigação testou o parâmetro de busca (`term=`) direto na API do site com termos diferentes ("analista de dados", "business intelligence") e os dois devolveram a mesma lista de vagas — a busca do site não filtra nada, é sempre o feed genérico recente. A categoria própria "Análise e Gestão de Dados" do site tem 4 vagas no total, contra 226 de "Emprego" geral (majoritariamente marketing/criação/comercial). O problema era a fonte, não o filtro — o código continua em `scrapers/trampos.py`, sem ser importado por nenhum perfil, caso a situação do site mude.

**99Jobs ficou.** Mesma investigação, resultado diferente: a busca por "analista de dados" retorna vaga de verdade relevante, só que presencial/híbrida em São Paulo — fora da cidade aceita e sem sinal de remoto. O vazio ali vinha do filtro de localização (limitação que afeta o projeto inteiro), não da fonte. Remover teria descartado uma fonte que funciona.

### Confiabilidade

- **Notifica antes de salvar.** Se o Telegram falhar depois de notificar, a vaga não é marcada como vista — reaparece no ciclo seguinte. Se salvasse primeiro, uma falha de rede faria a vaga sumir sem nunca ter sido vista por ninguém.
- **Dedup por duas chaves.** Hash do link normalizado (pega repost exato na mesma fonte) e `empresa+título` normalizado (pega a mesma vaga publicada em fontes diferentes, com URL diferente em cada uma).
- **Banco vazio suspeito.** Se `data/jobs.db` já existia em disco com conteúdo mas a tabela vem vazia na leitura, o ciclo aborta com alerta em vez de seguir — sem essa checagem, um banco perdido/corrompido faria o sistema notificar em massa centenas de vagas antigas de uma vez, como se fossem novas.
- **Distinção entre "zero vagas reais" e "não consegui carregar".** Cada scraper trata timeout de carregamento separado de busca genuinamente vazia (texto "0 resultado(s)" renderizado na página) — sem isso, bloqueio de anti-bot e ausência real de vaga geravam o mesmo log, tornando impossível saber qual dos dois estava acontecendo.
- **Máscara de `navigator.webdriver`** em todos os scrapers, reduzindo falso bloqueio por detecção de automação.
- **Alerta de saúde**: se metade ou mais das fontes falha ou volta vazia num ciclo, avisa no Telegram — sem isso, um bloqueio geral passaria despercebido, com o workflow do GitHub Actions continuando "verde".
- **Heartbeat diário**: uma mensagem por dia (por perfil) confirmando que o ciclo rodou, mesmo sem vaga nova nenhuma. Fecha uma lacuna que o alerta de saúde não cobre: se o workflow parar de rodar de vez (cron desabilitado, erro de configuração), silêncio no Telegram é indistinguível de "rodou e não achou nada" — o heartbeat torna essa ausência visível.

## Automação

`GitHub Actions` roda `main.py --perfil brasil internacional --once` a cada 3 horas (`0 */3 * * *`), com `concurrency.cancel-in-progress: false` — um ciclo travado bloqueia o próximo até liberar, em vez de rodar dois ao mesmo tempo por cima do mesmo banco. Ao final, o workflow commita `data/jobs.db` de volta no repositório; em caso de push rejeitado (execução concorrente ou push manual), sincroniza com `git rebase` preferindo a versão deste run em caso de conflito — o próprio banco de "vagas já vistas" é o mecanismo de dedup entre execuções.

Esse último ponto teve um bug real de produção: o rebase estava configurado com `-X ours`, que em `git merge` mantém o lado local, mas em `git rebase` tem semântica invertida — "ours" passa a se referir à branch de destino (`origin/main`), não aos commits sendo reaplicados. O efeito prático: toda vez que o push colidia, o `jobs.db` commitado voltava a ser o de `origin/main`, descartando silenciosamente vagas encontradas e notificadas naquele run (que reapareciam como "novas" no ciclo seguinte) e qualquer migração de coluna que tivesse rodado. Corrigido para `-X theirs`, confirmado com um repositório de teste isolado antes e depois do fix.

## Testes

`tests/test_filtro.py` — 43 casos `pytest` parametrizados contra a camada de filtro (`extrair_escopo_remoto`, `Job.combina_com`), rodando em `.github/workflows/testes.yml` a cada push. Cada caso documenta um bug real já corrigido nesta base (UF ambígua entre Brasil e EUA, "Porto Alegre" virando Portugal por substring, vaga com dois mercados declarados perdendo um deles, vocabulário de modalidade virando escopo geográfico falso) — não são cenários hipotéticos, são regressão registrada. `extrair_escopo_remoto` e `combina_com` são função pura (sem rede, sem browser, sem banco), o tipo de código mais barato de testar que existe, e historicamente o que mais bugs reais teve no projeto.

```bash
pytest tests/ -v
```

## Rodando localmente

```bash
git clone <repo>
cd JobRadar
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

Criar `.env` na raiz:

```
TELEGRAM_BOT_TOKEN=<token do bot, via @BotFather>
TELEGRAM_CHAT_ID=<chat id de destino>
INTERVALO_MINUTOS=180   # opcional, só usado fora do modo --once
```

Rodar um ciclo único (mesmo modo usado em produção pelo GitHub Actions):

```bash
python main.py --perfil brasil internacional --once
```

Ou em loop contínuo, sem cron externo:

```bash
python main.py --perfil brasil
```

## Stack

Python 3.11, Playwright (scraping com browser real, contorna proteção anti-bot melhor que requisição HTTP crua), SQLite (zero infraestrutura, o próprio arquivo é o "banco de produção" versionado no Git), Telegram Bot API (notificação), GitHub Actions (cron + execução, gratuito para repositório público), pytest (regressão da camada de filtro).

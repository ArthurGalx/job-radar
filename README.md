# JobRadar

Monitor automatizado de vagas de Dados & BI — roda sozinho, de graça, a cada 3 horas.

Nasceu de um problema real: em cidade pequena, vaga boa aparece pouco e some rápido. Quem checa o board duas vezes por dia perde pra quem checou na primeira hora. O JobRadar existe pra checar por mim — 8 fontes (LinkedIn, Gupy, Indeed, Solides, Catho, GeekHunter, 99Jobs, We Work Remotely), o ano inteiro, sem servidor, sem custo, sem precisar lembrar.

## Como funciona

1. **Busca** em paralelo nas fontes configuradas, com rodízio de termos pra controlar custo por ciclo.
2. **Filtra** por cargo, cidade/mercado e idioma — com três níveis de confiança (cargo inequívoco, cargo ambíguo + qualificador, ferramenta + cargo), não só palavra-chave solta.
3. **Pontua** cada vaga por relevância (0–10): cargo, ferramenta, senioridade, mercado, idioma — soma simples de sinais conhecidos, sem IA.
4. **Deduplica** por link e por empresa+título, pra pegar a mesma vaga republicada em fontes diferentes.
5. **Notifica** no Telegram: vaga de alta relevância na hora; o resto num resumo diário ranqueado, melhor vaga no topo.
6. **Aprende**: cada notificação tem botão 👍/👎 — o feedback vira dado pra medir precisão de verdade (aprovação por fonte, por semana) em vez de intuição.

## Engenharia

- **73 testes automatizados**, rodando em CI a cada push — cada caso documenta um bug real já corrigido nesta base, não um cenário hipotético.
- **Zero infraestrutura**: GitHub Actions como motor de cron, SQLite como banco (versionado no próprio Git — o histórico de vagas já vistas *é* o commit).
- **Resiliente**: nunca marca vaga como "vista" sem confirmar que a notificação saiu; alerta automático se metade das fontes falhar num ciclo; heartbeat diário pra saber se o robô ainda está de pé.

## Stack

Python · Playwright · SQLite · Telegram Bot API · GitHub Actions · pytest

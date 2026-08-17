/**
 * JobRadar -> Google Sheets
 *
 * Cole este arquivo em Extensões > Apps Script, DENTRO da planilha que vai
 * receber as vagas, e publique como web app (Implantar > Nova implantação >
 * Tipo: App da Web; Executar como: Eu; Quem pode acessar: Qualquer pessoa).
 * A URL /exec gerada vira o secret SHEETS_WEBHOOK_URL do repositório.
 *
 * "Qualquer pessoa" é exigência do Google pra que um POST sem login do
 * Google funcione — é o que permite o GitHub Actions escrever aqui sem
 * service account. Por isso a URL sozinha NÃO basta: todo POST precisa
 * trazer o mesmo TOKEN definido abaixo, que também vira secret
 * (SHEETS_TOKEN). Sem isso, quem descobrisse a URL escreveria na planilha.
 *
 * Contrato do POST (montado em exporters/sheets.py):
 *   { "token": "...", "colunas": ["encontrada_em", ...], "linha": {...} }
 * A ordem das colunas vem no próprio payload de propósito: acrescentar um
 * campo novo no Python não obriga a mexer e republicar este script.
 */

// TROQUE por um valor secreto seu (qualquer string longa e aleatória) e
// use exatamente o mesmo no secret SHEETS_TOKEN do GitHub.
var TOKEN = 'COLE_AQUI_UM_SEGREDO_LONGO';

// Aba que recebe as vagas. Precisa existir na planilha.
var ABA = 'Página1';

function doPost(e) {
  var lock = LockService.getScriptLock();
  // Dois ciclos do radar (perfil Brasil e Internacional) podem escrever ao
  // mesmo tempo. Sem lock, duas requisições leem o mesmo getLastRow() e uma
  // sobrescreve a linha da outra.
  lock.waitLock(30000);

  try {
    var corpo = JSON.parse(e.postData.contents);

    if (!corpo.token || corpo.token !== TOKEN) {
      return _resposta({ ok: false, erro: 'token inválido' });
    }

    var planilha = SpreadsheetApp.getActiveSpreadsheet();
    var aba = planilha.getSheetByName(ABA) || planilha.getSheets()[0];

    var colunas = corpo.colunas;
    var linha = corpo.linha;

    // Cabeçalho só na primeira escrita — depois disso a planilha é sua:
    // renomear coluna, congelar linha, colorir, o que for.
    if (aba.getLastRow() === 0) {
      aba.appendRow(colunas);
      aba.getRange(1, 1, 1, colunas.length).setFontWeight('bold');
      aba.setFrozenRows(1);
    }

    // Escrita por NOME de coluna, não por posição. A versão anterior
    // montava o array na ordem de `colunas` e dava appendRow — o que
    // funciona só enquanto a planilha for exatamente as colunas do robô.
    // Assim que o usuário acrescenta coluna própria ("Fiz inscrição?",
    // "Respondeu?"), qualquer campo NOVO vindo do Python passaria a cair
    // em cima da coluna dele. Lendo o cabeçalho e casando por nome, coluna
    // manual fica intocada, ordem pode ser trocada na mão, e campo novo é
    // criado no fim em vez de sobrescrever o que já existe.
    var cabecalho = aba.getRange(1, 1, 1, aba.getLastColumn()).getValues()[0];
    var indicePorNome = {};
    for (var c = 0; c < cabecalho.length; c++) {
      indicePorNome[String(cabecalho[c]).trim()] = c;
    }

    // Coluna que o robô manda e a planilha ainda não tem: cria no fim.
    for (var n = 0; n < colunas.length; n++) {
      if (!(colunas[n] in indicePorNome)) {
        var nova = aba.getLastColumn() + 1;
        aba.getRange(1, nova).setValue(colunas[n]).setFontWeight('bold');
        indicePorNome[colunas[n]] = nova - 1;
      }
    }

    // Dedup por link: o banco do radar já evita reprocessar a mesma vaga,
    // mas o jobs.db pode ser restaurado de um commit antigo (o workflow
    // versiona o banco e faz rebase em caso de push concorrente) e aí a
    // mesma vaga voltaria a ser "nova". A planilha é a cópia que você
    // anota à mão — duplicar linha aqui custa mais caro do que uma
    // varredura de coluna a cada POST.
    var indiceLink = colunas.indexOf('link');
    if (indiceLink !== -1 && aba.getLastRow() > 1) {
      var links = aba.getRange(2, indiceLink + 1, aba.getLastRow() - 1, 1).getValues();
      for (var i = 0; i < links.length; i++) {
        if (links[i][0] === linha.link) {
          return _resposta({ ok: true, duplicada: true });
        }
      }
    }

    // Monta a linha do tamanho do cabeçalho ATUAL, deixando em branco toda
    // coluna que não veio no payload — inclusive as suas, que continuam
    // com o valor/checkbox que já tinham nas linhas anteriores e nascem
    // vazias nas novas.
    var largura = Math.max(aba.getLastColumn(), colunas.length);
    var valores = new Array(largura).fill('');
    for (var j = 0; j < colunas.length; j++) {
      var valor = linha[colunas[j]];
      valores[indicePorNome[colunas[j]]] = (valor === undefined || valor === null) ? '' : valor;
    }
    aba.appendRow(valores);

    return _resposta({ ok: true });
  } catch (erro) {
    return _resposta({ ok: false, erro: String(erro) });
  } finally {
    lock.releaseLock();
  }
}

function _resposta(objeto) {
  return ContentService
    .createTextOutput(JSON.stringify(objeto))
    .setMimeType(ContentService.MimeType.JSON);
}

# A API do SSG, como o próprio site a chama

Sondado ao vivo em **2026-09-10** (somente leitura). Implementação executável:
`src/modules/browser/ssg_api.py`. Este documento é o conhecimento; o código é
a cópia. Se um mudar, mude o outro.

Até aqui toda automação deste projeto dirigia o DOM. Este documento existe
porque duas listas que o projeto precisa são servidas por chamadas simples, e
lê-las direto é **uma ordem de grandeza mais rápido** e funciona em situações
em que a tela não ajuda (por exemplo, ler a lista de OSI de um dia que não tem
nenhuma linha de apontamento).

## Como o site monta uma chamada

Lido de `services.runWebMethod` na própria página:

```js
var url = this.baseUrl + '/api';
if (SysMap.getCookie('AspSession') != null) {
    url += '/' + SysMap.getCookie('AspSession');
}
$.post(url + '/' + controller + '/' + method,
       { data: jsonData, currentPage: encodeURIComponent(window.location.hash) },
       callback);
```

Três consequências:

1. **O `<id>` opaco em `/api/<id>/` é o cookie `AspSession`.** Dá para lê-lo
   com `document.cookie.match(/AspSession=([^;]+)/)` — não é preciso farejar
   requisição nenhuma para descobri-lo (a primeira ideia deste projeto era
   capturá-lo do `performance.getEntriesByType('resource')`, o que também
   funciona, mas depende de a chamada já ter acontecido e de o buffer de 250
   entradas não tê-la expulsado).
2. **A chamada precisa sair de dentro da página.** A sessão é um cookie do
   perfil do navegador; um `urllib` do Python seria anônimo. É o que
   `CdpPage.fetch_json` faz.
3. `services.baseUrl` é **vazio** — as rotas são relativas à origem
   `https://ssg.sysmap.com.br`.

Note que há um segundo host de API no site, `https://services.sysmap.com.br/api/v1/…`
(globais `urlUser`, `urlpeople`, `urlbusinessday`, `urlIsManager`). Nada aqui
usa esse host; ele aparece porque é ele que falha ao abrir a tela de listagem
de OSI (ver `pages/listagem-de-osi/recon.md`).

## O envelope da resposta

Toda chamada responde HTTP 200 com um envelope; o dado está em `ReturnObject`.

```json
{
  "CorrelationId": "37f50a3d-…",
  "IsError": false,
  "Errors": [],
  "ErrorMessage": null,
  "Message": "Operação realizada com sucesso!",
  "ReturnCode": "1001",
  "ReturnObject": [ … ]
}
```

| `ReturnCode` | significado | o que fazer |
| --- | --- | --- |
| `1001` | sucesso | usar `ReturnObject` (pode ser lista **vazia**, e isso é uma resposta legítima) |
| `INVALID_TOKEN`, `INVALID_TOKEN_3`, … | a sessão morreu | pedir login humano; o próprio site redireciona para a tela de login quando vê isso |
| `1002` e outros | o método falhou | cair para o caminho pelo DOM |

Confirmado com token falso: `INVALID_TOKEN_3` / *"A sessão do usuário é
inválida!"* / `ReturnObject: null`.

## `timesheet-recording/get-osi-project-activity-by-term` (GET)

A lista que o botão "?" do campo de OSI mostra — o mesmo endpoint do
typeahead, com `term` vazio.

```
GET /api/<AspSession>/timesheet-recording/get-osi-project-activity-by-term
    ?current-page=%23%2Faccess-entry%2Fget-list
    &term=
    &userName=<nome do profissional>
    &date=DD/MM/AAAA
```

`ReturnObject` é um **array de strings**, exatamente o texto que o modal
lista (formato livre — ver `pages/apontamento/README.md`).

- **Depende do dia**, e muito. Mesma conta, mesmo minuto, em 2026-09-10:
  `date=10/09/2026` → 17 itens · `03/09/2026` → 16 · `27/08/2026` → 15 ·
  `01/07/2026` → 4.
- **Funciona para um dia sem nenhuma linha de apontamento** — inclusive hoje.
  É o que dispensa criar linha só para ter o botão "?".
- ⚠️ **`userName` vazio devolve sucesso com zero itens**, não erro. É falha
  silenciosa: quem chamar tem que exigir o nome. Ele está no campo
  `.user-name` do filtro da tela de apontamento, já preenchido pelo site.
- Latência medida: **0,60s** (contra ~2,3s para abrir/ler/fechar o modal).

## `osi/get-by-parameters` (POST)

Todas as OSI em que você é o profissional, com status e período.

```
POST /api/<AspSession>/osi/get-by-parameters
Content-Type: application/x-www-form-urlencoded

data={"UserName":"<nome>"}&currentPage=%23%2Fosi%2Fget-list
```

É **exatamente** o que a tela "Pesquisar OSI" envia ao clicar em "Filtrar" com
o Profissional preenchido — de `OsiController.getList`:

```js
osiFilter.UserName     = view.find('.textbox-osi-profissional').val().trim();
osiFilter.Id           = view.find('.textbox-osi-id').val().trim();
osiFilter.ManagerName  = view.find('.textbox-osi-manager').val().trim();
osiFilter.StatusName   = view.find('.textbox-osi-status').val().trim();
osiFilter.StartDate    = view.find('.textbox-start-date').val().trim();
osiFilter.EndDate      = view.find('.textbox-end-date').val().trim();
osiFilter.RequirementId = view.find('.textbox-osi-requirement').val().split('|')[0].trim();
services.runWebMethod('osi', 'get-by-parameters', osiFilter, …);
```

`ReturnObject` é um array de objetos ricos. Os campos que este projeto usa:

| campo | exemplo | para quê |
| --- | --- | --- |
| `Id` | `"83385"` | o número da OSI |
| `StatusName` | `"Liberado"` | só `Liberado` é apontável |
| `ProjectName` | `"Faturamento Assistencial SECONCI"` | monta o rótulo |
| `ActivityName` | `"Homologação End2End - Suporte"` | monta o rótulo |
| `ActivityId` | `"417294"` | monta o rótulo |
| `OsiActivityStartDateStr` | `"08/09/2026"` | início da validade |
| `OsiActivityEndDateStr` | `"11/09/2026"` | fim da validade |

Há muito mais (`BudgetedEffort`, `EffortMade`, `EffortPerBusinessDay`,
`UserManagerName`, `RequirementName`, `CreateDateStr`, `RemainingCost`, …) se
um dia fizer falta.

**O rótulo se reconstrói** como
`OSI {Id} | {ProjectName} | {ActivityName} - {ActivityId}` e bate **caractere
por caractere** com a linha que o "?" lista (conferido com a OSI 83385). É
isso que permite fundir as duas fontes num catálogo só, em vez de dois
vocabulários.

Latência medida: **0,645s**, com 30 registros — contra 60s+ para a mesma
informação pela tela.

### `Liberado` não quer dizer "posso apontar"

Em 2026-09-10 as 30 OSI vinham como **24 `Liberado`, 4 `Finalizado`,
2 `Cancelado`** — mas só **4** das 24 `Liberado` valiam naquele dia. As
outras já tinham `OsiActivityEndDateStr` no passado e simplesmente não
aparecem no "?" do dia. O caso canônico é a 82695: `Liberado`, janela
encerrada em 30/08.

Ou seja: **apontável = `Liberado` E dia dentro de
`OsiActivityStartDateStr`..`OsiActivityEndDateStr`.**

### As duas fontes não se contêm

Nenhuma é superconjunto da outra:

- só o **"?"** vê as OSI que o gestor abre para o time inteiro (elas têm outra
  pessoa como profissional, então `get-by-parameters` filtrado por você não as
  traz) — eram 13 das 17 linhas em 10/09;
- só a **listagem** vê status e período, e vê OSI que o "?" do dia não oferece.

## `calendar/get-holidays-by-period-for-user`

Existe (a tela de apontamento chama ao filtrar) e é claramente o calendário de
feriados **do usuário**. Chamada sem parâmetros responde
`ReturnCode: 1002` / *"Parameter count mismatch."* — a assinatura não foi
investigada, porque a palavra `FERIADO` que a própria tela escreve no painel
do dia já resolve (ver `pages/apontamento/README.md`). Fica anotado como a
fonte a investigar se um dia for preciso saber de feriados sem abrir a tela.

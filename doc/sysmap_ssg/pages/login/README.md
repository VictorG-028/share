# Login do portal (`portal.sysmap.com.br/wp-login.php`)

Sondado em 2026-08-27. Ver `../../../ROADMAP.md`'s seção "O alvo" para a
narrativa histórica completa — este arquivo é só a referência atual.

## Alvo

`https://portal.sysmap.com.br/wp-login.php` — WordPress atrás de
Cloudflare. O desafio do Cloudflare **passa sozinho** num browser real; a
primeira leitura da página pega "Executando verificação de segurança", a
seguinte já traz o formulário de login.

## Seletores

| campo | seletor |
| --- | --- |
| usuário | `#user_login` (já autopreenchido no perfil dedicado) |
| senha | `#user_pass` (já autopreenchida no perfil dedicado) |
| código do Google Authenticator | `#googleotp` |
| submit | `#wp-submit` |

## Login é sempre manual

O código do Google Authenticator (TOTP) não é gerado por esta automação —
a pessoa precisa digitar à mão. Por isso o login nunca é automatizado:
`SsgController.login()` só re-checa se a sessão ainda existe, e levanta
`SsgLoginRequired` se a tela de login aparecer. Ver
`../../sessao-e-rotas.md` para como a sessão persiste entre execuções.

"""
Entry point for creating a new OSI on the SSG site (``register-new-osi``).

Interactive by default: lists projects, asks which, probes every activity's
accepted period (each probe is a save the site rejects on purpose), asks
which activity, shows a summary and asks before the real "Gravar".
``--project``/``--activity``/``--yes`` skip the questions; ``--list`` stops
after the discovery and creates nothing.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from main import EXIT_ERROR, EXIT_NOTHING_TO_DO, EXIT_OK
from modules.osi_register import ActivityWindow, default_description, flow

_YES = {"s", "sim", "y", "yes"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="register-new-osi",
        description=(
            "Cadastra uma OSI nova no SSG. Descobre o periodo aceito de cada "
            "atividade e so grava depois de mostrar o resumo e perguntar."
        ),
    )
    parser.add_argument("--list", action="store_true", help="so listar projetos/atividades e periodos; nao grava")
    parser.add_argument("--project", help="projeto (numero, codigo ou trecho do nome); sem isso, pergunta")
    parser.add_argument("--activity", help="atividade (trecho do nome); sem isso, pergunta")
    parser.add_argument("--description", help='descricao; padrao: "Criando OSI do mes <mes do inicio>"')
    parser.add_argument("--yes", action="store_true", help="nao perguntar antes de gravar")
    parser.add_argument("--port", type=int, help="porta do CDP (padrao: 9222)")
    return parser


def _choose(options: list[str], what: str) -> str | None:
    """Numbered menu on the console; ``None`` when there is nobody to ask."""
    if not sys.stdin.isatty():
        print(f"Sem terminal interativo para escolher {what}. Use --project/--activity.")
        return None
    for index, option in enumerate(options, start=1):
        print(f"  {index}. {option}")
    while True:
        answer = input(f"{what.capitalize()} [1-{len(options)}, vazio cancela]: ").strip()
        if not answer:
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1]
        print("Opcao invalida.")


def _confirm(assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print("Sem terminal interativo para confirmar. Use --yes se e isso mesmo.")
        return False
    return input("Confirma a gravacao? [s/N] ").strip().lower() in _YES


def _describe(window: ActivityWindow) -> str:
    return f"{window.activity}   {window.start:%d/%m/%Y} a {window.end:%d/%m/%Y}"


def run(
    *,
    list_only: bool = False,
    project: str | None = None,
    activity: str | None = None,
    description: str | None = None,
    assume_yes: bool = False,
    port: int | None = None,
) -> int:
    from modules.browser.browsers import BrowserNotFound
    from modules.browser.cdp import CdpError
    from modules.browser.ssg_screen import SsgError, SsgLoginRequired

    try:
        form = flow.open_form(port)
    except SsgLoginRequired as error:
        print(f"Login necessario: {error}")
        return EXIT_ERROR
    except (BrowserNotFound, SsgError, CdpError) as error:
        print(f"Erro: {error}")
        return EXIT_ERROR

    try:
        form.pick_professional()
        projects = form.list_projects()
        if not projects:
            print("Nenhum projeto disponivel.")
            return EXIT_NOTHING_TO_DO
        chosen_project = project or _choose(projects, "projeto")
        if chosen_project is None:
            return EXIT_NOTHING_TO_DO

        provisional = description or default_description(date.today())
        chosen_project, activities = flow.prepare(form, chosen_project, provisional)
        print(f"Projeto: {chosen_project}")
        if not activities:
            print("Esse projeto nao tem atividade disponivel.")
            return EXIT_NOTHING_TO_DO
        if activity:
            activities = [name for name in activities if activity.lower() in name.lower()] or activities

        windows: list[ActivityWindow] = []
        for name in activities:
            print(f"Sondando o periodo de {name!r} (o site vai recusar um Gravar de proposito)...")
            windows.append(flow.discover_window(form, name))
        print("Atividades e periodos aceitos:")
        for window in windows:
            print("  " + _describe(window))
        if list_only:
            return EXIT_OK

        if len(windows) == 1:
            window = windows[0]
        else:
            picked = _choose([_describe(w) for w in windows], "atividade")
            if picked is None:
                return EXIT_NOTHING_TO_DO
            window = windows[[_describe(w) for w in windows].index(picked)]

        final_description = description or default_description(window.start)
        hours = flow.fill(form, window, final_description)
        print("Vou GRAVAR no SSG:")
        print(f"  Projeto:   {chosen_project}")
        print(f"  Atividade: {_describe(window)}")
        print(f"  Esforco:   {hours}h (8h por dia util, conferido no site)")
        print(f"  Descricao: {final_description}")
        if not _confirm(assume_yes):
            print("Nao gravei.")
            return EXIT_NOTHING_TO_DO
        result = flow.submit(form, final_description)
        print(f"GRAVADO. Resposta do site: {result}")
        code = form.read_code()
        if code and code != "-":
            print(f"Codigo da OSI: {code}")
        return EXIT_OK
    except SsgLoginRequired as error:
        print(f"Login necessario: {error}")
        return EXIT_ERROR
    except (BrowserNotFound, SsgError, CdpError) as error:
        print(f"Erro: {error}")
        return EXIT_ERROR
    finally:
        form.close()


def cli(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run(
        list_only=args.list,
        project=args.project,
        activity=args.activity,
        description=args.description,
        assume_yes=args.yes,
        port=args.port,
    )


if __name__ == "__main__":
    try:
        exit_code = cli()
    except Exception:
        import traceback

        traceback.print_exc()
        exit_code = EXIT_ERROR
    if getattr(sys, "frozen", False) and sys.stdin.isatty():
        try:
            input("\nPressione Enter para fechar...")
        except EOFError:
            pass
    sys.exit(exit_code)

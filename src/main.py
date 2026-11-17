"""Ponto de entrada do robô.

Exemplos:
    python -m src.main --check          # diagnóstico (não usa mouse/teclado)
    python -m src.main --dry-run        # só lê e mostra a planilha
    python -m src.main                  # executa o robô
    python -m src.main --limite 5       # executa só os 5 primeiros registros
"""

from __future__ import annotations

import argparse
import logging
import sys
import webbrowser
from collections import Counter
from datetime import datetime
from pathlib import Path

from .core.config import FROZEN, Settings, load_settings
from .core.exceptions import RobotError, RobotStopped
from .core.logger import setup_logging
from .core.recorder import ScreenRecorder
from .core.safety import EmergencyStop, interruptible_sleep, prepare_environment
from .pipeline import Robot, required_templates, run_pipeline
from .records import Record, SpreadsheetError, Status, read_records, save_results_csv
from .report import RunInfo, save_html_report

log = logging.getLogger("autopy")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="autopy", description="Robô RPA de cadastro em sistema legado")
    p.add_argument("--config", type=Path, help="arquivo de configuração (padrão: config/settings.yaml)")
    p.add_argument("--planilha", type=Path, help="planilha de entrada (sobrepõe a configuração)")
    p.add_argument("--inicio", type=int, default=2, metavar="LINHA",
                   help="primeira linha da planilha a processar (padrão: 2)")
    p.add_argument("--limite", type=int, metavar="N", help="processar no máximo N registros")
    p.add_argument("--contagem", type=int, default=5, metavar="S",
                   help="segundos de contagem regressiva antes de assumir o mouse (padrão: 5)")
    p.add_argument("--gravar", type=Path, metavar="ARQUIVO.gif",
                   help="grava a janela do sistema durante a execução em um GIF")
    p.add_argument("--nao-abrir", action="store_true",
                   help="não abrir o relatório no navegador ao final")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="verifica configuração, templates, planilha e janela, sem usar mouse/teclado")
    mode.add_argument("--dry-run", action="store_true",
                      help="lê a planilha e mostra o que seria cadastrado")
    return p.parse_args(argv)


def load_records(settings: Settings, args: argparse.Namespace) -> list[Record]:
    path = args.planilha or settings.input.spreadsheet
    records = [r for r in read_records(path, settings.input.sheet) if r.row >= args.inicio]
    if args.limite is not None:
        records = records[:args.limite]
    log.info("📋 %d registro(s) lido(s) de %s", len(records), path.name)
    return records


# -- modos ----------------------------------------------------------------------
def dry_run(records: list[Record]) -> int:
    for r in records:
        log.info("  linha %-3d %-22s %s  %s  %-3s", r.row, r.nome, r.cpf, r.nascimento, r.turma)
    return 0


def check(settings: Settings, records: list[Record]) -> int:
    """Diagnóstico somente leitura: ideal ao instalar o robô em outra máquina."""
    ok = True
    templates_dir = settings.vision.templates_dir
    missing = sorted(n for n in required_templates() if not (templates_dir / f"{n}.png").exists())
    if missing:
        ok = False
        log.error("❌ Templates ausentes em %s: %s", templates_dir, missing)
    else:
        log.info("✅ %d templates encontrados", len(required_templates()))
    log.info("✅ Planilha legível: %d registro(s)", len(records))

    robot = Robot.from_settings(settings)
    window = robot.window.find()
    if window is None:
        log.warning("⚠️  Janela '%s' não está aberta (o robô a abrirá com: %s)",
                    settings.app.window_title, settings.app.launch_command)
    else:
        log.info("✅ Janela encontrada: '%s' em %s", window.title, robot.window.region())
        visible = [n for n in ("login_btn_entrar", "menu_btn_cadastro", "cadastro_btn_salvar")
                   if robot.vision.exists(n)]
        if visible:
            log.info("✅ Tela reconhecida: %s", visible[0])
        else:
            ok = False
            log.error("❌ Nenhuma tela conhecida reconhecida. A escala do Windows ou o tema "
                      "podem ser diferentes dos templates; rode scripts/capturar_templates.py")
    log.info("Diagnóstico: %s", "OK" if ok else "PROBLEMAS ENCONTRADOS")
    return 0 if ok else 1


def run(settings: Settings, records: list[Record], args: argparse.Namespace) -> int:
    robot = Robot.from_settings(settings)
    recorder = None
    with EmergencyStop(settings.safety.stop_hotkey):
        robot.window.ensure_open()
        log.warning("🤖 O robô vai assumir o mouse e o teclado. Não use o computador "
                    "durante a execução. Para parar: '%s' ou mouse no canto superior "
                    "esquerdo.", settings.safety.stop_hotkey)
        for remaining in range(args.contagem, 0, -1):
            log.info("   começando em %d...", remaining)
            interruptible_sleep(1)
        robot.window.focus()
        if args.gravar:
            recorder = ScreenRecorder(robot.window.region).start()
        started_at = datetime.now()
        try:
            results = run_pipeline(robot, records)
        finally:
            if recorder:
                recorder.stop()
        finished_at = datetime.now()

    if recorder:
        recorder.save_gif(args.gravar)

    stamp = started_at.strftime("%Y%m%d_%H%M%S")
    reports = settings.output.reports_dir
    csv_path = save_results_csv(results, reports / f"resultado_{stamp}.csv")
    info = RunInfo((args.planilha or settings.input.spreadsheet).name, started_at, finished_at)
    html_path = save_html_report(results, info, reports / f"relatorio_{stamp}.html")

    counts = Counter(r.status for r in results)
    log.info("=" * 60)
    log.info("Resumo: ✅ %d sucesso | ❌ %d rejeitado(s) | 💥 %d falha(s) | ⏸️ %d não processado(s)",
             counts[Status.SUCESSO], counts[Status.REJEITADO], counts[Status.FALHA],
             counts[Status.NAO_PROCESSADO])
    log.info("📊 Relatório: %s", html_path)
    log.info("   Dados (CSV): %s", csv_path)
    if not args.nao_abrir:
        webbrowser.open(html_path.as_uri())
    return 0 if counts[Status.FALHA] == 0 and counts[Status.NAO_PROCESSADO] == 0 else 1


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # emojis/acentos no console do Windows
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args(argv)  # depois do reconfigure: o --help também tem acentos
    settings = load_settings(args.config)
    log_file = setup_logging(settings.output.logs_dir)
    log.debug("Log da execução: %s", log_file)
    prepare_environment(settings.safety.failsafe, settings.timing.action_pause)

    try:
        records = load_records(settings, args)
        if args.dry_run:
            return dry_run(records)
        if args.check:
            return check(settings, records)
        if not records:
            log.warning("Nenhum registro para processar")
            return 0
        return run(settings, records, args)
    except SpreadsheetError as exc:
        log.error("❌ %s", exc)
        return 2
    except RobotStopped as exc:
        log.warning("🛑 Robô interrompido antes de começar: %s", exc)
        return 130
    except RobotError as exc:
        log.error("❌ %s", exc)
        return 1


def entrypoint() -> None:
    try:
        code = main()
    except Exception:
        log.exception("Erro inesperado")
        code = 1
    # Aberto com dois cliques (sem argumentos): sem a pausa, a janela do
    # console fecharia antes de dar tempo de ler o resumo.
    if FROZEN and len(sys.argv) == 1 and sys.stdin and sys.stdin.isatty():
        try:
            input("\nPressione Enter para fechar...")
        except EOFError:  # ex.: entrada redirecionada para NUL, que finge ser terminal
            pass
    sys.exit(code)


if __name__ == "__main__":
    entrypoint()

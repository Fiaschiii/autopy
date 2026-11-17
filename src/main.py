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
from collections import Counter
from pathlib import Path

from .core.config import Settings, load_settings
from .core.exceptions import RobotError, RobotStopped
from .core.logger import setup_logging
from .core.safety import EmergencyStop, interruptible_sleep, prepare_environment
from .pipeline import Robot, default_results_path, required_templates, run_pipeline
from .records import Record, SpreadsheetError, Status, read_records, save_results_csv

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


def run(settings: Settings, records: list[Record], countdown: int) -> int:
    robot = Robot.from_settings(settings)
    with EmergencyStop(settings.safety.stop_hotkey):
        robot.window.ensure_open()
        log.warning("🤖 O robô vai assumir o mouse e o teclado. Não use o computador "
                    "durante a execução. Para parar: '%s' ou mouse no canto superior "
                    "esquerdo.", settings.safety.stop_hotkey)
        for remaining in range(countdown, 0, -1):
            log.info("   começando em %d...", remaining)
            interruptible_sleep(1)
        robot.window.focus()
        results = run_pipeline(robot, records)

    path = save_results_csv(results, default_results_path(settings))
    counts = Counter(r.status for r in results)
    log.info("=" * 60)
    log.info("Resumo: ✅ %d sucesso | ❌ %d rejeitado(s) | 💥 %d falha(s) | ⏸️ %d não processado(s)",
             counts[Status.SUCESSO], counts[Status.REJEITADO], counts[Status.FALHA],
             counts[Status.NAO_PROCESSADO])
    log.info("Resultado detalhado: %s", path)
    return 0 if counts[Status.FALHA] == 0 and counts[Status.NAO_PROCESSADO] == 0 else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # emojis/acentos no console do Windows
        sys.stderr.reconfigure(encoding="utf-8")
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
        return run(settings, records, args.contagem)
    except SpreadsheetError as exc:
        log.error("❌ %s", exc)
        return 2
    except RobotStopped as exc:
        log.warning("🛑 Robô interrompido antes de começar: %s", exc)
        return 130
    except RobotError as exc:
        log.error("❌ %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())

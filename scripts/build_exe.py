"""
Gera os executáveis com PyInstaller e monta o pacote de distribuição.

Saída:
    dist/autopy-<versão>-windows/      pasta pronta para uso
    dist/autopy-<versão>-windows.zip   o mesmo conteúdo compactado (para o GitHub Releases)

Uso:
    pip install -r requirements-dev.txt
    python scripts/build_exe.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import __version__  # noqa: E402

BUILD = ROOT / "build"
DIST = ROOT / "dist"
PACKAGE = DIST / f"autopy-{__version__}-windows"
DEMO_EXE = "SisEscola98.exe"


def pyinstaller(script: Path, name: str, *, windowed: bool) -> Path:
    print(f"\n=== Gerando {name}.exe ===")
    subprocess.run([
        sys.executable, "-m", "PyInstaller", str(script),
        "--name", name, "--onefile", "--noconfirm", "--clean",
        "--windowed" if windowed else "--console",
        "--paths", str(ROOT),
        "--distpath", str(BUILD / "exe"),
        "--workpath", str(BUILD / "work"),
        "--specpath", str(BUILD),
    ], check=True, cwd=ROOT)
    return BUILD / "exe" / f"{name}.exe"


def release_settings() -> str:
    """settings.example.yaml, mas abrindo o sistema pelo .exe (sem Python)."""
    text = (ROOT / "config" / "settings.example.yaml").read_text(encoding="utf-8")
    old = 'launch_command: "python demo_app/fake_erp.py"'
    if old not in text:
        raise SystemExit(f"Não encontrei '{old}' no settings.example.yaml")
    return text.replace(old, f'launch_command: "{DEMO_EXE}"')


def main() -> None:
    robot_exe = pyinstaller(ROOT / "packaging" / "autopy_entry.py", "autopy", windowed=False)
    demo_exe = pyinstaller(ROOT / "demo_app" / "fake_erp.py", DEMO_EXE[:-4], windowed=True)

    print(f"\n=== Montando {PACKAGE.name} ===")
    shutil.rmtree(PACKAGE, ignore_errors=True)
    (PACKAGE / "config").mkdir(parents=True)
    (PACKAGE / "data").mkdir()
    shutil.copy2(robot_exe, PACKAGE / "autopy.exe")
    shutil.copy2(demo_exe, PACKAGE / DEMO_EXE)
    (PACKAGE / "config" / "settings.yaml").write_text(release_settings(), encoding="utf-8")
    shutil.copytree(ROOT / "assets" / "templates", PACKAGE / "assets" / "templates",
                    ignore=shutil.ignore_patterns(".gitkeep"))
    shutil.copy2(ROOT / "data" / "exemplo.xlsx", PACKAGE / "data" / "exemplo.xlsx")
    shutil.copy2(ROOT / "packaging" / "LEIA-ME.txt", PACKAGE / "LEIA-ME.txt")

    archive = shutil.make_archive(str(PACKAGE), "zip", root_dir=DIST, base_dir=PACKAGE.name)
    size_mb = Path(archive).stat().st_size / 1_048_576
    print(f"\nPacote pronto: {PACKAGE}\nZip: {archive} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()

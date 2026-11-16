# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adota o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [0.2.0] - 2026-11-16

### Adicionado
- Núcleo do robô em `src/core/`:
  - `vision.py`: busca por imagem restrita à janela, `wait_for`, `wait_for_any`,
    `wait_until_gone` e prints de evidência.
  - `actions.py`: cliques e digitação com verificação de foco antes de cada ação;
    textos com acentos/teclas mortas são colados via área de transferência
    (restaurando o conteúdo original).
  - `window.py`: abertura, localização e foco da janela com contorno para o bug
    do `activate()` do PyGetWindow no Windows.
  - `safety.py`: parada de emergência por hotkey, failsafe, esperas
    interrompíveis e DPI awareness.
  - `retry.py`: novas tentativas com backoff exponencial.
  - `config.py` e `logger.py`: configuração tipada e logs por execução.
- `scripts/capturar_templates.py`: geração automática e reproduzível dos templates.
- 18 templates em `assets/templates/` e prints das telas em `tests/fixtures/screens/`.
- Suíte de testes com pytest (`requirements-dev.txt`), incluindo a matriz
  templates × telas contra falsos positivos.

### Alterado
- `pyperclip` passa a ser dependência direta.

## [0.1.0] - 2026-11-16

### Adicionado
- Sistema legado fictício **SisEscola 98** (`demo_app/fake_erp.py`) com login, menu,
  cadastro de alunos, validações, lentidão aleatória e pop-ups inesperados.
- Script `scripts/gerar_planilha_exemplo.py` e planilha `data/exemplo.xlsx` com
  24 alunos fictícios (4 inválidos de propósito).
- Modelo de configuração `config/settings.example.yaml`.
- `requirements.txt` com as dependências fixadas.
- Estrutura de pacotes `src/core` e `src/screens`.

# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adota o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado
- `src/main.py`: CLI com os modos `--check` (diagnóstico sem mouse/teclado),
  `--dry-run`, `--limite`, `--inicio` e contagem regressiva antes de assumir o PC.
- `src/pipeline.py`: o `Robot` navega até o cadastro venha de onde vier,
  processa cada registro com retry e classifica o resultado em sucesso,
  rejeitado, falha ou não processado. Também sinaliza possível duplicidade.
- `src/records.py`: leitura da planilha (cabeçalho flexível, linhas vazias,
  valores convertidos pelo Excel) e exportação do resultado em CSV.
- Page Objects em `src/screens/` (login, menu e cadastro), com fechamento
  automático de pop-ups e estabilização após trocar de tela.
- `LoginFailedError`: senha recusada encerra a execução sem insistir.
- Testes do pipeline com telas falsas, da leitura da planilha e dos pontos de
  clique dos campos.
- `src/report.py`: relatório HTML autocontido (prints embutidos, resumo,
  filtros por status, tema claro/escuro), aberto no navegador ao final.
  `--nao-abrir` desativa a abertura automática.
- `src/core/recorder.py` e `--gravar arquivo.gif`: grava a execução em GIF,
  somente a área da janela do sistema, com o ponteiro do mouse desenhado e
  quadros repetidos fundidos.
- `scripts/build_exe.py`: gera `autopy.exe` e `SisEscola98.exe` com PyInstaller
  e monta o pacote `dist/autopy-<versão>-windows.zip`, que roda sem Python.
- Suporte a execução empacotada: configuração, templates, planilha e saídas
  ficam ao lado do executável; pausa ao final quando aberto com dois cliques.

### Corrigido
- `AppWindow.is_active()` passa a considerar o processo da janela: com um
  diálogo do sistema aberto, o robô não tenta mais "roubar" o foco de volta
  para a janela principal.
- `Actions.clear_field()` não apagava o campo: o PyAutoGUI envia End/Home sem o
  marcador de "tecla estendida" e, com o NumLock ligado, o Windows solta o Shift
  (Shift+End vira End). A limpeza agora usa End + Backspace. O bug fazia o
  registro seguinte a uma recusa ser digitado por cima dos dados antigos.
- `AppWindow.region()` usa a área visível informada pelo DWM: o retângulo do
  PyGetWindow inclui bordas invisíveis, e a gravação mostrava pedaços de
  outras janelas.
- Foco da janela: quando o `activate()` esbarra na trava de primeiro plano do
  Windows, o robô usa `AttachThreadInput` antes de recorrer a minimizar/restaurar,
  e espera a janela estar pronta (não minimizada, tamanho real) antes de procurar
  imagens.
- `Vision.find()` trata "área de busca menor que o template" como "ainda não
  apareceu", em vez de encerrar o robô.
- Erros inesperados num registro passam a marcá-lo como falha (com print) e o
  robô segue para o próximo, em vez de encerrar sem relatório.

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

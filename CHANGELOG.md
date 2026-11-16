# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adota o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [0.1.0] - 2026-11-16

### Adicionado
- Sistema legado fictício **SisEscola 98** (`demo_app/fake_erp.py`) com login, menu,
  cadastro de alunos, validações, lentidão aleatória e pop-ups inesperados.
- Script `scripts/gerar_planilha_exemplo.py` e planilha `data/exemplo.xlsx` com
  24 alunos fictícios (4 inválidos de propósito).
- Modelo de configuração `config/settings.example.yaml`.
- `requirements.txt` com as dependências fixadas.
- Estrutura de pacotes `src/core` e `src/screens`.

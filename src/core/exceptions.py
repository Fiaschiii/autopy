"""Hierarquia de exceções do robô.

Ter exceções próprias permite que o pipeline decida o que fazer com cada
tipo de falha: tentar de novo, pular o registro ou abortar a execução.
"""


class RobotError(Exception):
    """Erro base do robô (falhas recuperáveis: o registro pode ser re-tentado)."""


class ElementNotFoundError(RobotError):
    """Uma imagem/elemento não apareceu na tela dentro do tempo limite."""


class WindowNotFoundError(RobotError):
    """A janela do sistema-alvo não foi encontrada."""


class WindowFocusError(RobotError):
    """Não foi possível colocar a janela do sistema-alvo em primeiro plano.

    O robô se recusa a digitar/clicar se o foco não estiver no sistema-alvo,
    para nunca enviar teclas para outro programa por engano.
    """


class LoginFailedError(Exception):
    """O sistema recusou usuário/senha. Fatal: não adianta tentar de novo."""


class TemplateNotFoundError(Exception):
    """A imagem de referência (template) não existe em disco. Erro de configuração."""


class RobotStopped(Exception):
    """Execução interrompida pelo usuário (hotkey ou failsafe). Nunca é re-tentada."""

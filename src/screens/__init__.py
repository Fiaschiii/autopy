"""Page Objects: uma classe por tela do sistema-alvo."""

from .base import Screen
from .cadastro import CadastroScreen, SaveResult
from .login import LoginScreen
from .menu import MenuScreen

__all__ = ["Screen", "LoginScreen", "MenuScreen", "CadastroScreen", "SaveResult"]

"""Manejo del navegador (Playwright) y login compartido para el MCP de Familia y Sucesiones.

Reusa el mismo mecanismo de login (login.justucuman.gov.ar con SAE_CUIL/SAE_PASSWORD) que
ya usa sae_checker.py, pero con un perfil de sesión propio para no pisar el de las
notificaciones automáticas.
"""
import atexit
import os
from pathlib import Path
from typing import Optional

from playwright.sync_api import BrowserContext, Page, sync_playwright

BASE_URL = "https://consultaexpedientes.justucuman.gov.ar"
BUSCADOR_URL = f"{BASE_URL}/familia/buscador"

_playwright = None
_context: Optional[BrowserContext] = None


def _profile_dir() -> str:
    d = Path(__file__).resolve().parent / "user_data"
    d.mkdir(exist_ok=True)
    return str(d)


def get_context(headless: bool = True) -> BrowserContext:
    """Devuelve un contexto de navegador persistente, reutilizándolo entre llamadas."""
    global _playwright, _context
    if _context is not None:
        return _context

    _playwright = sync_playwright().start()
    _context = _playwright.chromium.launch_persistent_context(
        user_data_dir=_profile_dir(),
        headless=headless,
        viewport={"width": 1280, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
    )
    return _context


def close_context() -> None:
    global _playwright, _context
    if _context is not None:
        try:
            _context.close()
        except Exception:
            pass
        _context = None
    if _playwright is not None:
        try:
            _playwright.stop()
        except Exception:
            pass
        _playwright = None


atexit.register(close_context)


def get_page(context: BrowserContext) -> Page:
    return context.pages[0] if context.pages else context.new_page()


def esta_logueado(page: Page) -> bool:
    try:
        return page.locator("text=/Iniciar sesión/i").count() == 0
    except Exception:
        return False


def asegurar_login(page: Page) -> bool:
    """Intenta loguearse con SAE_CUIL/SAE_PASSWORD (si están en el .env). Devuelve True si
    la página terminó en estado logueado (o ya lo estaba)."""
    if esta_logueado(page):
        return True

    cuil = os.getenv("SAE_CUIL")
    password = os.getenv("SAE_PASSWORD")
    if not cuil or not password:
        return False

    boton = page.locator("text=/Iniciar sesión/i").first
    if boton.count() == 0:
        return False

    try:
        with page.expect_navigation(timeout=30000):
            boton.click()
        page.wait_for_load_state("networkidle")

        if "/login" in page.url or page.locator("input[type='password']").count() > 0:
            page.locator("input#cuit, input[name='username']").fill(cuil)
            page.locator("input#password, input[name='password']").fill(password)
            with page.expect_navigation(timeout=30000):
                page.locator(
                    "button:has-text('Iniciar'), button[type='submit'], input[type='submit']"
                ).first.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1500)
    except Exception:
        pass

    return esta_logueado(page)

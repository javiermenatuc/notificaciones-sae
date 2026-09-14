"""Abre el navegador visible para iniciar sesión una vez (resolviendo CAPTCHA si lo pide)
y deja la sesión guardada en familia_mcp/user_data/ para que el servidor MCP la reuse.

Uso: python -m familia_mcp.login_interactivo
"""
from .browser import BUSCADOR_URL, close_context, esta_logueado, get_context, get_page


def main():
    context = get_context(headless=False)
    page = get_page(context)
    page.goto(BUSCADOR_URL)
    page.wait_for_load_state("networkidle")

    if esta_logueado(page):
        print("[Familia MCP] Ya había una sesión iniciada guardada. Nada que hacer.")
        close_context()
        return

    print("\n" + "=" * 70)
    print(" LOGIN MANUAL - Familia y Sucesiones (SAE Tucumán)")
    print("=" * 70)
    print("1. Hacé clic en 'Iniciar sesión' arriba a la derecha.")
    print("2. Ingresá tu CUIL y contraseña, resolvé el CAPTCHA si lo pide.")
    print("3. Esperá a volver a la pantalla del buscador de Familia y Sucesiones.")
    print("=" * 70 + "\n")
    input("Presioná [ENTER] acá una vez que hayas iniciado sesión...")

    if esta_logueado(page):
        print("[Familia MCP] ¡Sesión guardada con éxito!")
    else:
        print("[Familia MCP] [ADVERTENCIA] No se detectó sesión iniciada. Revisá e intentá de nuevo.")

    close_context()


if __name__ == "__main__":
    main()

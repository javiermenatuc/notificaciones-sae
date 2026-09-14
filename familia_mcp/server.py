"""Servidor MCP (stdio) para consultar el fuero Familia y Sucesiones del SAE de Tucumán."""
from mcp.server.fastmcp import FastMCP

from . import scraping

mcp = FastMCP("sae-familia-sucesiones")


@mcp.tool()
def sae_familia_buscar(numero: str = "", actor: str = "", demandado: str = "", unidad_judicial: str = "") -> list:
    """Busca expedientes en el fuero Familia y Sucesiones del SAE de Tucumán por número
    (ej '1/20'), actor y/o demandado (apellido). Sin sesión iniciada solo devuelve causas
    de Sucesión (las de Familia son confidenciales); configurá SAE_CUIL y SAE_PASSWORD en
    el .env para que también intente entrar a causas de Familia donde seas parte o letrado."""
    return scraping.buscar(
        numero=numero or None,
        actor=actor or None,
        demandado=demandado or None,
        unidad_judicial=unidad_judicial or None,
    )


@mcp.tool()
def sae_familia_consultar_causa(url: str = "", numero: str = "", max_movimientos: int = 25) -> dict:
    """Trae carátula y movimientos de un expediente de Familia y Sucesiones. Pasá la 'url'
    del expediente (la que devuelve sae_familia_buscar) o el 'numero' para buscarlo primero.
    Si la causa es de Familia y no tenés acceso, devuelve acceso_restringido=true con el motivo."""
    return scraping.consultar_causa(url=url or None, numero=numero or None, max_movimientos=max_movimientos)


@mcp.tool()
def sae_familia_traer_documento(url_causa: str, histid: int, max_caracteres: int = 40000) -> dict:
    """Descarga el PDF de un movimiento (#histid, tal como lo devuelve
    sae_familia_consultar_causa) de un expediente de Familia y Sucesiones y devuelve su texto."""
    return scraping.traer_documento(url_causa=url_causa, histid=histid, max_caracteres=max_caracteres)


if __name__ == "__main__":
    mcp.run()

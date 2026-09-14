# MCP Familia y Sucesiones (SAE Tucumán)

Servidor MCP (stdio) que consulta el buscador de **Familia y Sucesiones** de
`consultaexpedientes.justucuman.gov.ar/familia/buscador`. Sin sesión iniciada solo ves causas
de **Sucesión** (las de Familia son confidenciales); si configurás `SAE_CUIL` y `SAE_PASSWORD`
en el `.env` de la raíz del repo, el servidor intenta loguearse para que también aparezcan las
causas de Familia donde seas parte o letrado.

Corre siempre con navegador real (Playwright), así que **tiene que ejecutarse en tu máquina**,
no en un servidor/datacenter — el portal del Poder Judicial filtra ese tipo de tráfico.

## Instalación

```bash
pip install -r requirements.txt
playwright install chromium
```

## Primer login (una sola vez, si vas a usar SAE_CUIL/SAE_PASSWORD)

```bash
python -m familia_mcp.login_interactivo
```

Se abre un navegador visible: iniciá sesión manualmente (resolviendo el CAPTCHA si lo pide) y
la sesión queda guardada en `familia_mcp/user_data/` para las próximas corridas.

## Tools expuestas

- `sae_familia_buscar(numero?, actor?, demandado?, unidad_judicial?)` — busca expedientes.
- `sae_familia_consultar_causa(url? | numero?, max_movimientos?)` — carátula y movimientos;
  si la causa es de Familia y no tenés acceso, devuelve `acceso_restringido: true`.
- `sae_familia_traer_documento(url_causa, histid, max_caracteres?)` — texto del PDF de un
  movimiento.

## Configurar en un cliente MCP (Claude Desktop, Cowork, etc.)

```json
{
  "mcpServers": {
    "sae-familia": {
      "command": "python",
      "args": ["-m", "familia_mcp.server"],
      "cwd": "/ruta/a/notificaciones-sae"
    }
  }
}
```

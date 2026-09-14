"""Lógica de scraping del buscador de Familia y Sucesiones del SAE de Tucumán."""
import os
import re
import tempfile
import urllib.parse
from typing import Optional

import requests

from .browser import BUSCADOR_URL, asegurar_login, get_context, get_page


def _ir_a_buscador(page):
    if BUSCADOR_URL not in page.url:
        page.goto(BUSCADOR_URL)
        page.wait_for_load_state("networkidle")


def _fill_by_label(page, label_text: str, value: str) -> bool:
    """Completa el input asociado a un label (por atributo for/id o, si no, el input más
    cercano después del texto del label)."""
    try:
        loc = page.get_by_label(label_text, exact=False)
        if loc.count() > 0:
            loc.first.fill(value)
            return True
    except Exception:
        pass
    try:
        loc = page.locator(
            f"xpath=//*[normalize-space(text())='{label_text}']/following::input[1]"
        )
        if loc.count() > 0:
            loc.first.fill(value)
            return True
    except Exception:
        pass
    return False


def buscar(
    numero: Optional[str] = None,
    actor: Optional[str] = None,
    demandado: Optional[str] = None,
    unidad_judicial: Optional[str] = None,
    headless: bool = True,
) -> list:
    """Busca expedientes en el buscador de Familia y Sucesiones. Sin sesión iniciada,
    el portal solo devuelve causas de Sucesión; las de Familia requieren login con acceso
    a esa causa puntual (se intenta automáticamente si SAE_CUIL/SAE_PASSWORD están seteados)."""
    if not any([numero, actor, demandado]):
        raise ValueError("Pasá al menos uno de: numero, actor, demandado.")

    context = get_context(headless=headless)
    page = get_page(context)
    _ir_a_buscador(page)
    asegurar_login(page)
    _ir_a_buscador(page)

    if numero:
        _fill_by_label(page, "No. Expt.", numero)
    if actor:
        _fill_by_label(page, "Actor", actor)
    if demandado:
        _fill_by_label(page, "Demandado", demandado)
    if unidad_judicial:
        try:
            page.locator("select").first.select_option(label=unidad_judicial)
        except Exception:
            pass

    page.locator("button:has(svg), button.btn-primary, button[type='submit']").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)

    if page.locator("text=/No se encontraron resultados/i").count() > 0:
        return []

    resultados = []
    for fila in page.locator("table tbody tr").all():
        celdas = fila.locator("td").all()
        if len(celdas) < 4:
            continue
        link = fila.locator("a").last
        href = link.get_attribute("href") if link.count() > 0 else None
        url_abs = urllib.parse.urljoin(page.url, href) if href else None
        resultados.append(
            {
                "numero": celdas[0].inner_text().strip(),
                "caratula": celdas[1].inner_text().strip(),
                "proceso": celdas[2].inner_text().strip(),
                "unidad_judicial": celdas[3].inner_text().strip(),
                "url": url_abs,
            }
        )
    return resultados


def consultar_causa(
    url: Optional[str] = None,
    numero: Optional[str] = None,
    max_movimientos: int = 25,
    headless: bool = True,
) -> dict:
    context = get_context(headless=headless)
    page = get_page(context)

    if not url:
        if not numero:
            raise ValueError("Pasá 'url' o 'numero'.")
        resultados = buscar(numero=numero, headless=headless)
        if not resultados:
            return {"encontrado": False, "motivo": "No se encontró ningún expediente con ese número."}
        if len(resultados) > 1:
            return {
                "encontrado": False,
                "motivo": "Hay más de un expediente con ese número.",
                "candidatos": resultados,
            }
        url = resultados[0]["url"]
        if not url:
            return {
                "encontrado": False,
                "motivo": "No se pudo obtener el link del expediente en los resultados.",
            }

    page.goto(url)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)

    sin_acceso = page.locator(
        "text=/no tiene permisos|acceso denegado|no autorizado|debe iniciar sesión|no posee acceso/i"
    ).count() > 0
    if sin_acceso:
        return {
            "encontrado": True,
            "acceso_restringido": True,
            "motivo": (
                "Esta causa es de Familia y requiere ser parte/letrado logueado con acceso "
                "a este expediente puntual."
            ),
            "url": url,
        }

    caratula = ""
    try:
        caratula = page.locator("h1, h2, .caratula").first.inner_text().strip()
    except Exception:
        pass

    movimientos = []
    for fila in page.locator("table tbody tr").all()[:max_movimientos]:
        if not fila.locator("td").count():
            continue
        histid = None
        link = fila.locator("a").first
        if link.count() > 0:
            href = link.get_attribute("href") or ""
            m = re.search(r"histid=(\d+)", href)
            if m:
                histid = int(m.group(1))
        movimientos.append({"texto": fila.inner_text().strip(), "histid": histid})

    return {
        "encontrado": True,
        "acceso_restringido": False,
        "url": url,
        "caratula": caratula,
        "movimientos": movimientos,
    }


def traer_documento(
    url_causa: str,
    histid: int,
    max_caracteres: int = 40000,
    headless: bool = True,
) -> dict:
    context = get_context(headless=headless)
    page = get_page(context)
    page.goto(url_causa)
    page.wait_for_load_state("networkidle")

    link = page.locator(f"a[href*='histid={histid}']").first
    if link.count() == 0:
        return {"encontrado": False, "motivo": f"No se encontró el movimiento #{histid} en esta causa."}

    href = link.get_attribute("href")
    abs_url = href if href.startswith("http") else urllib.parse.urljoin(page.url, href)

    session = requests.Session()
    for c in context.cookies():
        session.cookies.set(c["name"], c["value"], domain=c.get("domain"), path=c.get("path", "/"))

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": page.url,
    }
    resp = session.get(abs_url, headers=headers, timeout=30)
    if resp.status_code != 200:
        return {"encontrado": False, "motivo": f"HTTP {resp.status_code} al descargar el documento."}

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name

        import fitz

        doc = fitz.open(tmp_path)
        texto = "\n".join(pagina.get_text() for pagina in doc)
        doc.close()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    texto = texto.strip()
    return {
        "encontrado": True,
        "texto": texto[:max_caracteres],
        "truncado": len(texto) > max_caracteres,
        "url_documento": abs_url,
    }

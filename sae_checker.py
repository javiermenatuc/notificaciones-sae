import os
import sys
import re
import argparse
import datetime
import smtplib
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import holidays
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env
load_dotenv()

# Configuración de notificaciones
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

WHATSAPP_PHONE = os.getenv("WHATSAPP_PHONE")
WHATSAPP_APIKEY = os.getenv("WHATSAPP_APIKEY")

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

NOTIFICATION_URL = os.getenv("NOTIFICATION_URL")
SEND_ON_NO_NOVELTY = os.getenv("SEND_ON_NO_NOVELTY", "True").lower() in ("true", "1", "yes")

def check_execution_time(time_arg):
    """Verifica si el scraper debe ejecutarse según el trigger de tiempo, fines de semana y feriados en Tucumán/Argentina."""
    today = datetime.date.today()
    # 0 = Lunes, ..., 5 = Sábado, 6 = Domingo
    is_weekend = today.weekday() in (5, 6)
    
    # Cargar feriados de Argentina para el año actual con la subdivisión de Tucumán ('T')
    ar_holidays = holidays.Argentina(subdiv='T', years=today.year)
    is_holiday = today in ar_holidays
    feriado_nombre = ar_holidays.get(today) if is_holiday else ""
    
    print(f"[SAE] Verificando reglas de ejecución:")
    print(f"  Fecha: {today.strftime('%d/%m/%Y')} | Fin de semana: {'Sí' if is_weekend else 'No'} | Feriado: {'Sí (' + feriado_nombre + ')' if is_holiday else 'No'}")
    
    if time_arg == 8:
        # Tarea de las 8:00 AM (Lunes a Viernes no feriados)
        if is_weekend or is_holiday:
            razon = "Fin de semana" if is_weekend else f"Feriado ({feriado_nombre})"
            print(f"[SAE] Omitiendo ejecución de las 8:00 AM por ser {razon}. Se posterga para las 11:00 AM.")
            return False
        print("[SAE] Ejecutando revisión programada de las 8:00 AM (Día laborable).")
        return True
        
    elif time_arg == 11:
        # Tarea de las 11:00 AM (Sábados, Domingos y Feriados de Argentina/Tucumán)
        if is_weekend or is_holiday:
            tipo = "Fin de semana" if is_weekend else f"Feriado ({feriado_nombre})"
            print(f"[SAE] Ejecutando revisión programada de las 11:00 AM por ser {tipo}.")
            return True
        print("[SAE] Omitiendo ejecución de las 11:00 AM por ser día laborable (ya se ejecutó a las 8:00 AM).")
        return False
        
    else:
        # Ejecución manual u otros
        print("[SAE] Ejecución sin filtro de tiempo o manual. Corriendo scraper...")
        return True

def escape_html(text):
    """Escapa caracteres especiales para evitar errores en la API de Telegram con parse_mode=HTML."""
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def enviar_mensaje_telegram(mensaje_html):
    """Envía un mensaje formateado en HTML a Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or "tu_token" in TELEGRAM_BOT_TOKEN or "tu_chat" in TELEGRAM_CHAT_ID:
        print("[Telegram] Configuración incompleta. Saltando...")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Controlar límite de tamaño de Telegram (4096 caracteres)
    if len(mensaje_html) > 4000:
        print("[Telegram] Mensaje demasiado largo. Recortando...")
        mensaje_html = mensaje_html[:3900] + "\n\n⚠️ <i>Mensaje recortado por límite de tamaño de Telegram. Revisa el portal para ver todo.</i>"
        
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje_html,
        "parse_mode": "HTML"
    }
    
    try:
        print("[Telegram] Enviando notificación...")
        response = requests.post(url, json=payload, timeout=10)
        res_json = response.json()
        if response.status_code == 200 and res_json.get("ok"):
            print("[Telegram] Mensaje enviado correctamente.")
            return True
        else:
            print(f"[Telegram] [ERROR] Error en respuesta: {res_json}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[Telegram] [ERROR] No se pudo enviar el mensaje: {e}", file=sys.stderr)
        return False

def html_to_whatsapp(html_text):
    """Convierte tags HTML básicos en formato de Markdown de WhatsApp y limpia tags residuales."""
    if not html_text:
        return ""
    text = html_text
    text = re.sub(r'</?(b|strong)>', '*', text)
    text = re.sub(r'</?(i|em)>', '_', text)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    return text

def enviar_mensaje_whatsapp(mensaje_html):
    """Envía un mensaje a WhatsApp utilizando CallMeBot."""
    if not WHATSAPP_PHONE or not WHATSAPP_APIKEY or "tu_apikey" in WHATSAPP_APIKEY or "XXXXX" in WHATSAPP_PHONE:
        print("[WhatsApp] Configuración incompleta. Saltando...")
        return False
        
    url = "https://api.callmebot.com/whatsapp.php"
    mensaje_wa = html_to_whatsapp(mensaje_html)
    
    # Limitar longitud para WhatsApp para evitar que falle (Límite sugerido ~900 caracteres para CallMeBot)
    if len(mensaje_wa) > 900:
        print("[WhatsApp] Mensaje demasiado largo. Recortando...")
        mensaje_wa = mensaje_wa[:850] + "\n\n*⚠️ Mensaje recortado por límite de WhatsApp. Revisa el portal.*"
        
    params = {
        "phone": WHATSAPP_PHONE,
        "text": mensaje_wa,
        "apikey": WHATSAPP_APIKEY
    }
    
    try:
        print("[WhatsApp] Enviando notificación a CallMeBot...")
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            print("[WhatsApp] Mensaje enviado correctamente.")
            return True
        else:
            print(f"[WhatsApp] [ERROR] Código de estado: {response.status_code}. Respuesta: {response.text}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[WhatsApp] [ERROR] No se pudo enviar el mensaje: {e}", file=sys.stderr)
        return False

def enviar_correo(asunto, html_contenido):
    """Envía un correo electrónico con formato HTML usando el SMTP de Gmail."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD or not RECIPIENT_EMAIL:
        print("[Gmail] Configuración incompleta. Saltando correo...")
        return False
        
    msg = MIMEMultipart('alternative')
    msg['Subject'] = asunto
    msg['From'] = f"Automatización SAE <{GMAIL_USER}>"
    msg['To'] = RECIPIENT_EMAIL

    part = MIMEText(html_contenido, 'html')
    msg.attach(part)

    try:
        print("[SMTP] Conectando al servidor seguro de Gmail...")
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        print("[SMTP] Autenticación exitosa. Enviando correo...")
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
        server.quit()
        print("[SMTP] Correo enviado correctamente.")
        return True
    except Exception as e:
        print(f"[SMTP] [ERROR] No se pudo enviar el correo: {e}", file=sys.stderr)
        return False

def enviar_notificaciones(asunto, mensaje_html, html_correo):
    """Centraliza el envío a todos los canales configurados."""
    enviado_ok = False
    
    # Intentar Telegram
    if enviar_mensaje_telegram(mensaje_html):
        enviado_ok = True
        
    # Intentar WhatsApp
    if enviar_mensaje_whatsapp(mensaje_html):
        enviado_ok = True
        
    # Intentar Gmail
    if GMAIL_USER and GMAIL_APP_PASSWORD and RECIPIENT_EMAIL:
        if enviar_correo(asunto, html_correo):
            enviado_ok = True
            
    if not enviado_ok:
        print("[SISTEMA] [ADVERTENCIA] No se pudo enviar la notificación por ningún canal activo.", file=sys.stderr)

def enviar_alerta_sesion_expirada():
    """Envía un mensaje urgente informando al usuario que debe re-autenticarse en el portal."""
    asunto = "⚠️ [SAE] Acción Requerida: Iniciar Sesión en el Portal"
    
    mensaje_html = (
        "⚠️ <b>Sesión del Portal SAE Expirada o CAPTCHA Requerido</b>\n\n"
        "La tarea automática diaria no pudo revisar tus notificaciones.\n\n"
        "<b>¿Cómo solucionarlo?</b>\n"
        "1. En tu PC, ve a la carpeta del script: <code>C:\\Users\\javie\\.gemini\\antigravity\\scratch\\NOTIFICACION SAE POR WP TELEGRAM</code>\n"
        "2. Haz doble clic en <b>run.bat</b>.\n"
        "3. Selecciona la opción <b>[1] Iniciar Sesión</b>.\n"
        "4. En la ventana visible que se abre, ingresa tus datos, resuelve el CAPTCHA e inicia sesión.\n"
        "5. El script guardará la sesión y podrás cerrar el navegador."
    )
    
    html_correo = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
        <div style="background-color: #f59e0b; color: white; padding: 15px; border-radius: 6px; margin-bottom: 20px; text-align: center;">
          <h2 style="margin: 0; font-size: 20px;">⚠️ Sesión del Portal SAE Expirada</h2>
        </div>
        <p>Hola,</p>
        <p>La tarea automática diaria de revisión de notificaciones del <b>Portal SAE de Tucumán</b> no pudo ejecutarse hoy.</p>
        <p><b>Razón:</b> La sesión guardada ha expirado o requiere que resuelvas un CAPTCHA manualmente.</p>
        <div style="background-color: #f3f4f6; border-left: 4px solid #3b82f6; padding: 15px; margin: 20px 0; border-radius: 0 6px 6px 0;">
          <h4 style="margin-top: 0; margin-bottom: 8px;">¿Cómo solucionarlo?</h4>
          <ol style="margin: 0; padding-left: 20px;">
            <li>En tu computadora, ve a la carpeta: <code>C:\\Users\\javie\\.gemini\\antigravity\\scratch\\NOTIFICACION SAE POR WP TELEGRAM</code></li>
            <li>Haz doble clic en el archivo <b><code>run.bat</code></b>.</li>
            <li>Selecciona la opción [1] e inicia sesión manualmente resolviendo el CAPTCHA.</li>
          </ol>
        </div>
      </body>
    </html>
    """
    
    enviar_notificaciones(asunto, mensaje_html, html_correo)

def normalizar_notificaciones(raw_list):
    """Normaliza las columnas del scraping para asegurar compatibilidad con la UI de SAE."""
    normalized = []
    for raw in raw_list:
        fecha = ""
        expediente = ""
        caratula = ""
        detalle = ""
        fuero = raw.get("_fuero", "General")
        estado = "No leída" if raw.get("_is_unread", False) else "Leída"
        
        for k, v in raw.items():
            if k.startswith("_"):
                continue
            k_lower = k.lower()
            if "fecha" in k_lower:
                fecha = v
            elif "expediente" in k_lower or "numero" in k_lower or "nº" in k_lower or "nro" in k_lower or "expte" in k_lower:
                expediente = v
            elif "caratula" in k_lower or "juicio" in k_lower or "causa" in k_lower:
                caratula = v
            elif any(x in k_lower for x in ["detalle", "actuacion", "tramite", "resumen", "asunto", "providencia", "texto", "tipo"]):
                if detalle:
                    detalle += " | " + v
                else:
                    detalle = v
        
        if not fecha and raw:
            for k, v in raw.items():
                if not k.startswith("_") and k.lower() not in ['l', 'ver']:
                    fecha = v
                    break
        if not expediente:
            expediente = raw.get("expediente", "N/D")
        if not caratula:
            caratula = raw.get("caratula", "N/D")
        if not detalle:
            other_vals = [f"{k.capitalize()}: {v}" for k, v in raw.items() if not k.startswith("_") and v not in [fecha, expediente, caratula] and k.lower() not in ['l', 'ver']]
            detalle = " | ".join(other_vals) if other_vals else "Sin detalle disponible"
            
        normalized.append({
            "fecha": fecha,
            "expediente": expediente,
            "caratula": caratula,
            "detalle": detalle,
            "estado": estado,
            "fuero": fuero,
            "is_unread": raw.get("_is_unread", False),
            "texto_documento": raw.get("_texto_documento", "")
        })
    return normalized


def armar_reporte_texto(notificaciones, total_unread):
    """Genera la representación estructurada en formato texto enriquecido (HTML para Telegram)."""
    fecha_actual = datetime.datetime.now().strftime("%d/%m/%Y a las %H:%M")
    
    if total_unread > 0:
        msg = f"🔴 <b>[SAE] Tienes {total_unread} notificaciones nuevas</b>\n"
    else:
        msg = f"🟢 <b>[SAE] Sin notificaciones nuevas hoy</b>\nTodo al día en tu casillero.\n"
        
    msg += f"<i>Generado el {fecha_actual}</i>\n\n"
    
    if not notificaciones:
        return msg
        
    # Agrupar notificaciones por fuero
    notif_por_fuero = {}
    for item in notificaciones:
        fuero = item["fuero"]
        if fuero not in notif_por_fuero:
            notif_por_fuero[fuero] = []
        notif_por_fuero[fuero].append(item)
        
    for fuero, items in notif_por_fuero.items():
        msg += f"📁 <b>FUERO: {escape_html(fuero)}</b>\n"
        for item in items:
            status_tag = "🔴" if item["is_unread"] else "🔹"
            msg += f"{status_tag} <b>Fecha:</b> {escape_html(item['fecha'])}\n"
            msg += f"   <b>Exp:</b> {escape_html(item['expediente'])}\n"
            msg += f"   <b>Carátula:</b> {escape_html(item['caratula'])}\n"
            msg += f"   <b>Detalle:</b> {escape_html(item['detalle'])}\n\n"
        msg += "----------------------------------\n"
        
    return msg

def armar_reporte_html(notificaciones, total_unread):
    """Genera el contenido HTML con diseño premium para el email de reporte."""
    fecha_actual = datetime.datetime.now().strftime("%d/%m/%Y a las %H:%M")
    
    if total_unread > 0:
        badge_color = "#ef4444"
        badge_text = f"{total_unread} Nuevas"
        resumen_titulo = f"🔴 Tienes {total_unread} notificaciones pendientes de lectura"
    else:
        badge_color = "#10b981"
        badge_text = "Sin novedades"
        resumen_titulo = "🟢 Todo al día - No se encontraron notificaciones pendientes"
        
    filas_html = ""
    if not notificaciones:
        filas_html = """
        <tr>
            <td colspan="5" style="padding: 20px; text-align: center; color: #6b7280; font-style: italic;">
                No hay notificaciones cargadas en el portal.
            </td>
        </tr>
        """
    else:
        notif_por_fuero = {}
        for item in notificaciones:
            fuero = item["fuero"]
            if fuero not in notif_por_fuero:
                notif_por_fuero[fuero] = []
            notif_por_fuero[fuero].append(item)
            
        for fuero, items in notif_por_fuero.items():
            filas_html += f"""
            <tr style="background-color: #f1f5f9; border-bottom: 2px solid #cbd5e1;">
                <td colspan="5" style="padding: 10px; font-size: 13px; font-weight: bold; color: #1e3a8a; text-transform: uppercase; letter-spacing: 0.05em; background-color: #e2e8f0;">
                    📁 Fuero: {fuero}
                </td>
            </tr>
            """
            
            for idx, item in enumerate(items):
                bg_color = "#ffffff" if idx % 2 == 0 else "#f9fafb"
                text_weight = "bold" if item["is_unread"] else "normal"
                text_color = "#111827" if item["is_unread"] else "#4b5563"
                
                estado_style = ""
                if item["is_unread"]:
                    estado_style = "background-color: #fee2e2; color: #ef4444; font-weight: bold; border-radius: 4px; padding: 2px 6px; display: inline-block; font-size: 11px;"
                else:
                    estado_style = "background-color: #f3f4f6; color: #6b7280; border-radius: 4px; padding: 2px 6px; display: inline-block; font-size: 11px;"
                    
                filas_html += f"""
                <tr style="background-color: {bg_color}; font-weight: {text_weight}; color: {text_color}; border-bottom: 1px solid #e5e7eb;">
                    <td style="padding: 12px 10px; font-size: 13px; white-space: nowrap;">{item["fecha"]}</td>
                    <td style="padding: 12px 10px; font-size: 13px; font-weight: bold; color: #1e3a8a;">{item["expediente"]}</td>
                    <td style="padding: 12px 10px; font-size: 13px;">{item["caratula"]}</td>
                    <td style="padding: 12px 10px; font-size: 13px; max-width: 250px; word-wrap: break-word;">{item["detalle"]}</td>
                    <td style="padding: 12px 10px; text-align: center;"><span style="{estado_style}">{item["estado"]}</span></td>
                </tr>
                """

    # Generar la sección de contenido de decretos/resoluciones nuevos en el email
    documentos_html = ""
    unread_docs = [item for item in notificaciones if item.get("is_unread") and item.get("texto_documento")]
    if unread_docs:
        documentos_html += """
        <h2 style="font-size: 16px; color: #334155; margin-top: 30px; margin-bottom: 12px; font-weight: 700; border-bottom: 2px solid #f1f5f9; padding-bottom: 8px;">Contenido de Decretos / Resoluciones Nuevos</h2>
        """
        for item in unread_docs:
            documentos_html += f"""
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
                <h4 style="margin: 0 0 10px 0; color: #1e3a8a; font-size: 13px; font-weight: bold;">
                    📄 Expte: {escape_html(item['expediente'])} | Fuero: {escape_html(item['fuero'])} | Fecha: {escape_html(item['fecha'])}
                </h4>
                <p style="margin: 0 0 5px 0; font-size: 12px; color: #111827; font-weight: bold;">
                    Carátula: {escape_html(item['caratula'])}
                </p>
                <p style="margin: 0 0 10px 0; font-size: 12px; color: #4b5563; font-weight: 500;">
                    Detalle: {escape_html(item['detalle'])}
                </p>
                <div style="background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 12px; font-family: monospace; font-size: 11px; white-space: pre-wrap; color: #1e293b; max-height: 350px; overflow-y: auto; line-height: 1.4;">
                    {escape_html(item['texto_documento'])}
                </div>
            </div>
            """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Notificaciones SAE Tucumán</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6; margin: 0; padding: 20px;">
        <div style="max-width: 800px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06); overflow: hidden; border: 1px solid #e5e7eb;">
            <div style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); color: #ffffff; padding: 25px; text-align: left;">
                <p style="margin: 0; font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em; color: #93c5fd; font-weight: bold;">Poder Judicial de Tucumán</p>
                <h1 style="margin: 5px 0 0 0; font-size: 24px; font-weight: 800;">Reporte de Notificaciones SAE</h1>
                <p style="margin: 10px 0 0 0; font-size: 13px; color: #bfdbfe;">Generado el {fecha_actual}</p>
            </div>
            
            <div style="padding: 25px;">
                <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; margin-bottom: 25px; display: flex; align-items: center; justify-content: space-between;">
                    <div style="flex: 1;">
                        <h3 style="margin: 0; color: #1e293b; font-size: 16px;">{resumen_titulo}</h3>
                    </div>
                    <div style="margin-left: 15px;">
                        <span style="background-color: {badge_color}; color: #ffffff; padding: 6px 12px; font-weight: bold; border-radius: 20px; font-size: 13px; display: inline-block;">
                            {badge_text}
                        </span>
                    </div>
                </div>
                
                <h2 style="font-size: 16px; color: #334155; margin-bottom: 12px; font-weight: 700; border-bottom: 2px solid #f1f5f9; padding-bottom: 8px;">Listado de Actuaciones</h2>
                
                <div style="overflow-x: auto; width: 100%;">
                    <table style="width: 100%; border-collapse: collapse; text-align: left;">
                        <thead>
                            <tr style="background-color: #f1f5f9; border-bottom: 2px solid #cbd5e1; color: #475569; font-size: 12px; font-weight: bold; text-transform: uppercase;">
                                <th style="padding: 10px; font-weight: 600;">Fecha</th>
                                <th style="padding: 10px; font-weight: 600;">Expediente</th>
                                <th style="padding: 10px; font-weight: 600;">Carátula / Juicio</th>
                                <th style="padding: 10px; font-weight: 600;">Detalle / Actuación</th>
                                <th style="padding: 10px; text-align: center; font-weight: 600;">Estado</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filas_html}
                        </tbody>
                    </table>
                </div>
                
                {documentos_html}
            </div>
        </div>
    </body>
    </html>
    """
    return html

def guardar_notification_url(url):
    """Guarda o actualiza la variable NOTIFICATION_URL en el archivo .env."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    lines = []
    updated = False
    
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        for idx, line in enumerate(lines):
            if line.strip().startswith("NOTIFICATION_URL="):
                lines[idx] = f"NOTIFICATION_URL={url}\n"
                updated = True
                break
                
    if not updated:
        lines.append(f"\nNOTIFICATION_URL={url}\n")
        
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
        
    os.environ["NOTIFICATION_URL"] = url
    print(f"[SAE] URL de notificaciones guardada de forma permanente: {url}")

def run_scraper(headless=True):
    """Función principal que ejecuta Playwright para verificar las notificaciones."""
    from playwright.sync_api import sync_playwright

    print(f"\n[SAE] Iniciando revisión de notificaciones (Modo Invisible = {headless})...")
    
    load_dotenv()
    notification_url = os.getenv("NOTIFICATION_URL")
    
    user_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_data")
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
        print(f"[SAE] Carpeta de perfil creada en: {user_data_dir}")

    with sync_playwright() as p:
        print("[SAE] Lanzando el navegador...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        try:
            page = context.pages[0] if context.pages else context.new_page()
            
            # --- MODO INTERACTIVO ---
            if not headless:
                print("[SAE] Navegando al portal...")
                if notification_url:
                    print(f"[SAE] Probando URL guardada: {notification_url}")
                    page.goto(notification_url)
                else:
                    page.goto("https://login.justucuman.gov.ar/login")
                
                page.wait_for_load_state("networkidle")
                
                print("\n" + "="*75)
                print(" CONFIGURACIÓN INTERACTIVA DE TU PORTAL SAE")
                print("="*75)
                print("Por favor, realiza los siguientes pasos en la ventana del navegador abierta:")
                print("1. Si te lo pide, ingresa tu CUIL y Contraseña, y resuelve el CAPTCHA.")
                print("2. En la página de inicio, haz clic en el botón 'ACCEDER' de la tarjeta")
                print("   de 'Notificaciones Digitales'.")
                print("3. Asegúrate de estar viendo la página que tiene el título")
                print("   'Notificaciones Bandeja de Entrada' (donde figuran la lista de fueros).")
                print("\nUNA VEZ QUE ESTÉS EN ESA PÁGINA DE FUEROS:")
                print("Regresa a esta consola y presiona ENTER.")
                print("="*75 + "\n")
                
                input("Presiona [ENTER] aquí una vez que estés visualizando los fueros...")
                
                print(f"[SAE] Analizando {len(context.pages)} pestañas abiertas...")
                pagina_correcta = None
                
                for idx_p, p_tab in enumerate(context.pages):
                    try:
                        title_text = p_tab.title()
                    except Exception:
                        title_text = "Desconocido"
                    print(f"  Pestaña [{idx_p}]: URL={p_tab.url} | Título={title_text}")
                    
                    url_lower = p_tab.url.lower()
                    title_lower = title_text.lower()
                    
                    if any(kw in url_lower or kw in title_lower for kw in ["notific", "bandeja", "entrada", "fueros"]):
                        if pagina_correcta is None:
                            pagina_correcta = p_tab
                            print(f"    -> Coincidencia por palabra clave identificada en pestaña [{idx_p}]!")
                
                if not pagina_correcta:
                    for idx_p, p_tab in enumerate(context.pages):
                        if "/login" not in p_tab.url and "about:blank" not in p_tab.url:
                            pagina_correcta = p_tab
                            print(f"    -> Seleccionando pestaña [{idx_p}] como alternativa (no es login ni blanca)")
                            break
                            
                if pagina_correcta:
                    page = pagina_correcta
                    print(f"[SAE] Pestaña seleccionada para configurar: {page.url}")
                else:
                    print("[SAE] No se detectó ninguna pestaña con la sesión activa. Evaluando pestaña por defecto.")
                    
                url_actual = page.url
                print(f"[SAE] URL detectada final: {url_actual}")
                
                if "/login" in url_actual:
                    print("[SAE] [ERROR] Sigues en la página de login o no has accedido a la bandeja de notificaciones.")
                    return
                    
                guardar_notification_url(url_actual)
                notification_url = url_actual
                print("[SAE] ¡Sesión y URL guardadas con éxito!")
                print("[SAE] Iniciando raspado de prueba en esta pantalla...")
                
            # --- MODO AUTOMÁTICO ---
            else:
                if not notification_url:
                    print("[SAE] [ERROR] No se ha configurado la URL de notificaciones.")
                    print("Por favor, abre 'run.bat' en tu PC y selecciona la opción [1] primero.")
                    enviar_alerta_sesion_expirada()
                    return
                    
                print(f"[SAE] Navegando de forma directa a: {notification_url}")
                page.goto(notification_url)
                page.wait_for_load_state("networkidle")
            
            # --- COMPROBACIÓN DE SESIÓN VÁLIDA / AUTO-LOGIN ---
            if "/login" in page.url or page.locator("input[type='password']").count() > 0:
                sae_cuil = os.getenv("SAE_CUIL")
                sae_password = os.getenv("SAE_PASSWORD")
                
                if sae_cuil and sae_password:
                    print("[SAE] La sesión expiró o no ha iniciado. Intentando inicio de sesión automático...")
                    try:
                        # Ir explícitamente a la página de login si no estamos ahí
                        if "/login" not in page.url:
                            page.goto("https://login.justucuman.gov.ar/login")
                            page.wait_for_load_state("networkidle")
                            
                        # Llenar los campos de credenciales
                        page.locator("input#cuit, input[name='username']").fill(sae_cuil)
                        page.locator("input#password, input[name='password']").fill(sae_password)
                        
                        # Hacer clic en Iniciar Sesión y esperar a que navegue
                        with page.expect_navigation(timeout=30000):
                            page.locator("button:has-text('Iniciar'), button[type='submit'], input[type='submit']").first.click()
                        
                        page.wait_for_load_state("networkidle")
                        page.wait_for_timeout(2000)
                        
                        # Si no estamos en la página del casillero, navegar al URL de inicialización
                        if "casillero" not in page.url:
                            print("[SAE] Estableciendo sesión en Notificaciones Digitales...")
                            page.goto("https://portaldelsae.justucuman.gov.ar/inicializando?module=notificaciones-digitales")
                            page.wait_for_load_state("networkidle")
                            page.wait_for_timeout(2000)
                            
                        # Verificar de nuevo si el login fue exitoso
                        if "/login" in page.url or page.locator("input[type='password']").count() > 0:
                            raise Exception("Las credenciales ingresadas son incorrectas o falló el redireccionamiento.")
                            
                        print("[SAE] ¡Inicio de sesión automático exitoso!")
                        # Guardar la URL del casillero si cambió o si no estaba configurada
                        if page.url != notification_url:
                            guardar_notification_url(page.url)
                            notification_url = page.url
                            
                    except Exception as e_login:
                        print(f"[SAE] [ERROR] Falló el inicio de sesión automático: {e_login}")
                        enviar_alerta_sesion_expirada()
                        return
                else:
                    print("[SAE] [SESIÓN] La sesión ha expirado y no se configuraron SAE_CUIL / SAE_PASSWORD en .env.")
                    enviar_alerta_sesion_expirada()
                    return
                
            print("[SAE] Sesión confirmada en el Portal del SAE.")
            
            # --- DETECCIÓN DE FUEROS CON PUNTOS AZULES ---
            print("[SAE] Buscando fueros con notificaciones nuevas...")
            page.wait_for_timeout(2000)
            
            botones = page.locator("text=/VER TODOS/i").all()
            print(f"[SAE] Se encontraron {len(botones)} fueros en total.")
            
            fueros_con_novedades = []
            
            for idx, boton in enumerate(botones):
                fila = None
                temp_el = boton
                for _ in range(6):
                    try:
                        parent = temp_el.locator("xpath=..").first
                        if parent.count() == 0 or not parent.is_visible():
                            break
                        
                        txt = parent.inner_text().strip()
                        txt_clean = txt.replace("VER TODOS", "").replace("Ver todos", "").strip()
                        
                        if len(txt_clean) > 2 and parent.locator("text=/VER TODOS/i").count() == 1:
                            fila = parent
                            break
                        temp_el = parent
                    except Exception:
                        break
                
                if not fila:
                    fila = boton.locator("xpath=..")
                    
                texto_fila = fila.inner_text().strip()
                nombre_fuero = texto_fila.replace("VER TODOS", "").replace("Ver todos", "").strip()
                nombre_fuero = " ".join(nombre_fuero.split())
                
                tiene_novedad = False
                for sel in [".dot", ".bullet", ".badge-primary", ".badge-info", ".circle", ".fa-circle", "[class*='blue']", "[class*='primary']", "[class*='dot']"]:
                    try:
                        el_punto = fila.locator(sel).first
                        if el_punto.count() > 0 and el_punto.is_visible() and el_punto.inner_text().strip() == "":
                            tiene_novedad = True
                            break
                    except Exception:
                        pass
                        
                if not tiene_novedad:
                    try:
                        tiene_novedad = fila.evaluate(r"""
                            (container) => {
                                const elementos = container.querySelectorAll('span, div, i, svg, img, badge, b');
                                for (const el of elementos) {
                                    const rect = el.getBoundingClientRect();
                                    if (rect.width > 2 && rect.width < 25 && rect.height > 2 && rect.height < 25) {
                                        const style = window.getComputedStyle(el);
                                        const bgColor = style.backgroundColor;
                                        const color = style.color;
                                        
                                        let rgbMatch = bgColor.match(/rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)/);
                                        if (!rgbMatch) {
                                            rgbMatch = color.match(/rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)/);
                                        }
                                        
                                        if (rgbMatch) {
                                            const r = parseInt(rgbMatch[1]);
                                            const g = parseInt(rgbMatch[2]);
                                            const b = parseInt(rgbMatch[3]);
                                            if (b > 120 && b > r && (b > g || (b - g) < 60)) {
                                                return true;
                                            }
                                        }
                                        
                                        const html = el.outerHTML.toLowerCase();
                                        if (html.includes('blue') || html.includes('azul') || html.includes('dot') || html.includes('bullet') || html.includes('circle')) {
                                            return true;
                                        }
                                    }
                                }
                                return false;
                            }
                        """)
                    except Exception:
                        pass
                
                status_str = "CON NOVEDADES 🔵" if tiene_novedad else "sin novedades"
                print(f"  Fuero [{idx}]: '{nombre_fuero}' -> {status_str}")
                
                if tiene_novedad:
                    fueros_con_novedades.append(nombre_fuero)
                    
            print(f"[SAE] Fueros a verificar hoy (tienen punto azul): {fueros_con_novedades}")
            
            notificaciones_crudas = []
            
            # --- ITERACIÓN DE FUEROS CON NOVEDADES ---
            for nombre_fuero in fueros_con_novedades:
                print(f"\n[SAE] Accediendo a fuero: '{nombre_fuero}'...")
                
                botones_actuales = page.locator("text=/VER TODOS/i").all()
                boton_a_clickear = None
                
                for b in botones_actuales:
                    fila_act = None
                    temp_el = b
                    for _ in range(6):
                        try:
                            parent = temp_el.locator("xpath=..").first
                            if parent.count() == 0 or not parent.is_visible():
                                break
                            
                            txt = parent.inner_text().strip()
                            txt_clean = txt.replace("VER TODOS", "").replace("Ver todos", "").strip()
                            
                            if len(txt_clean) > 2 and parent.locator("text=/VER TODOS/i").count() == 1:
                                fila_act = parent
                                break
                            temp_el = parent
                        except Exception:
                            break
                    
                    if not fila_act:
                        fila_act = b.locator("xpath=..")
                        
                    txt_fila = fila_act.inner_text().strip()
                    nom_fuero_act = txt_fila.replace("VER TODOS", "").replace("Ver todos", "").strip()
                    nom_fuero_act = " ".join(nom_fuero_act.split())
                    
                    if nom_fuero_act == nombre_fuero:
                        boton_a_clickear = b
                        break
                        
                if boton_a_clickear:
                    try:
                        boton_a_clickear.click()
                        page.wait_for_load_state("networkidle")
                        page.wait_for_timeout(2000)
                        
                        tablas = page.locator("table").all()
                        print(f"[SAE] Buscando tabla de notificaciones (tablas: {len(tablas)})")
                        
                        tabla_encontrada = False
                        for tabla in tablas:
                            encabezados = []
                            th_elementos = tabla.locator("thead th, tr th").all()
                            if not th_elementos:
                                th_elementos = tabla.locator("tr").first.locator("td").all()
                                
                            for el in th_elementos:
                                encabezados.append(el.inner_text().strip().lower())
                                
                            palabras_clave = {"fecha", "expte", "tipo", "descrip", "destinatario", "unidad", "ver", "l", "expediente", "juicio", "caratula", "trámite", "actuacion", "detalle", "estado"}
                            coincidencias = [h for h in encabezados if any(pc in h for pc in palabras_clave)]
                            
                            if len(coincidencias) < 2:
                                continue
                                
                            tabla_encontrada = True
                            filas = tabla.locator("tbody tr, tr").all()
                            salto_fila = 1 if not tabla.locator("thead").count() > 0 else 0
                            
                            print(f"[SAE] Raspando {len(filas) - salto_fila} actuaciones del fuero '{nombre_fuero}'...")
                            
                            for f_idx in range(salto_fila, len(filas)):
                                fila_el = filas[f_idx]
                                celdas = fila_el.locator("td").all()
                                if not celdas or len(celdas) < len(encabezados):
                                    continue
                                    
                                datos_fila = {}
                                for c_idx, col_nombre in enumerate(encabezados):
                                    if c_idx < len(celdas):
                                        datos_fila[col_nombre] = celdas[c_idx].inner_text().strip()
                                        
                                if datos_fila:
                                    # Detectar si es no leída buscando el punto rojo/círculo en la columna 'L' (columna 0)
                                    es_no_leida = False
                                    if len(celdas) > 0:
                                        first_col_html = celdas[0].inner_html()
                                        if "fa-circle" in first_col_html or "text-danger" in first_col_html:
                                            es_no_leida = True
                                    
                                    # Respaldo con estilo bold
                                    if not es_no_leida:
                                        fila_texto = fila_el.inner_text().lower()
                                        fila_html = fila_el.inner_html().lower()
                                        if "no leída" in fila_texto or "no leida" in fila_texto:
                                            es_no_leida = True
                                        elif "bold" in fila_html or "font-weight:bold" in fila_html or "font-weight: 700" in fila_html:
                                            if "leída" not in fila_texto and "leida" not in fila_texto:
                                                es_no_leida = True
                                                
                                    texto_documento = ""
                                    if es_no_leida:
                                        # Buscar el enlace 'Ver' (la lupa azul)
                                        ver_cell_idx = -1
                                        for c_idx, col_nombre in enumerate(encabezados):
                                            if "ver" in col_nombre:
                                                ver_cell_idx = c_idx
                                                break
                                        
                                        ver_link = None
                                        if ver_cell_idx != -1 and ver_cell_idx < len(celdas):
                                            ver_link = celdas[ver_cell_idx].locator("a").first
                                        else:
                                            ver_link = fila_el.locator("a").last
                                            
                                        if ver_link and ver_link.count() > 0:
                                            href = ver_link.get_attribute("href")
                                            if href:
                                                abs_url = urllib.parse.urljoin(page.url, href)
                                                print(f"[SAE] Notificación nueva detectada para Expte. {datos_fila.get('expte.', 'N/D')}. Descargando documento...")
                                                
                                                temp_dir = os.path.dirname(os.path.abspath(__file__))
                                                # Generar un nombre de archivo temporal único
                                                temp_pdf_name = f"temp_{datos_fila.get('expte.', 'doc').replace('/', '_').replace('.', '_')}.pdf"
                                                temp_pdf_path = os.path.join(temp_dir, temp_pdf_name)
                                                
                                                try:
                                                    # Obtener cookies de Playwright y preparar sesión de requests
                                                    cookies_playwright = context.cookies()
                                                    session = requests.Session()
                                                    for c in cookies_playwright:
                                                        session.cookies.set(c['name'], c['value'], domain=c.get('domain'), path=c.get('path', '/'))
                                                    
                                                    headers = {
                                                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                                                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                                                        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3",
                                                        "Referer": page.url
                                                    }
                                                    
                                                    print(f"[SAE] Descargando de forma directa vía requests: {abs_url}")
                                                    response = session.get(abs_url, headers=headers, timeout=30)
                                                    
                                                    if response.status_code == 200:
                                                        # Guardar archivo PDF
                                                        with open(temp_pdf_path, 'wb') as f:
                                                            f.write(response.content)
                                                        
                                                        # Extraer texto usando PyMuPDF
                                                        try:
                                                            import fitz
                                                            doc = fitz.open(temp_pdf_path)
                                                            paginas_texto = []
                                                            for pag in doc:
                                                                paginas_texto.append(pag.get_text())
                                                            doc.close()
                                                            
                                                            raw_text = "\n".join(paginas_texto)
                                                            lineas = [l.strip() for l in raw_text.split("\n")]
                                                            lineas_limpias = []
                                                            for l in lineas:
                                                                if l:
                                                                    lineas_limpias.append(l)
                                                                elif lineas_limpias and lineas_limpias[-1] != "":
                                                                    lineas_limpias.append("")
                                                            texto_documento = "\n".join(lineas_limpias).strip()
                                                            print(f"[SAE] Texto extraído con éxito ({len(texto_documento)} caracteres).")
                                                        except Exception as e_pdf:
                                                            print(f"[SAE] [ERROR] No se pudo leer el PDF: {e_pdf}")
                                                            texto_documento = f"(Error leyendo PDF del decreto: {e_pdf})"
                                                        finally:
                                                            if os.path.exists(temp_pdf_path):
                                                                try:
                                                                    os.remove(temp_pdf_path)
                                                                except Exception:
                                                                    pass
                                                    else:
                                                        raise Exception(f"HTTP Status {response.status_code}")
                                                        
                                                except Exception as e_dl:
                                                    print(f"[SAE] [ERROR] Error durante la descarga: {e_dl}")
                                                    texto_documento = f"(Error descargando PDF del decreto: {e_dl})"
                                                
                                    datos_fila["_is_unread"] = es_no_leida
                                    datos_fila["_fuero"] = nombre_fuero
                                    datos_fila["_texto_documento"] = texto_documento
                                    notificaciones_crudas.append(datos_fila)
                                    
                            if tabla_encontrada:
                                break
                                
                        if not tabla_encontrada:
                            print(f"[SAE] [WARN] No se pudo mapear la tabla para '{nombre_fuero}'.")
                            
                    except Exception as e_fuero:
                        print(f"[SAE] [ERROR] Excepción al procesar fuero '{nombre_fuero}': {e_fuero}")
                        
                    print(f"[SAE] Volviendo a la bandeja de fueros...")
                    page.goto(notification_url)
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(1000)
                else:
                    print(f"[SAE] [WARN] No se localizó el botón para el fuero '{nombre_fuero}'.")
            
            # --- CONSOLIDACIÓN DE REPORTES ---
            if not notificaciones_crudas:
                print("[SAE] Sin actuaciones nuevas encontradas en ningún fuero.")
                notificaciones_normalizadas = []
                total_no_leidas = 0
            else:
                print(f"\n[SAE] Consolidadas {len(notificaciones_crudas)} actuaciones.")
                notificaciones_normalizadas = normalizar_notificaciones(notificaciones_crudas)
                total_no_leidas = sum(1 for n in notificaciones_normalizadas if n["is_unread"])
                
            # Solo enviar si hay notificaciones o si se configuró enviar incluso sin novedades
            if total_no_leidas > 0 or SEND_ON_NO_NOVELTY:
                # Definir asunto para correos
                if total_no_leidas > 0:
                    asunto = f"🔴 [SAE] Tienes {total_no_leidas} Notificaciones Nuevas"
                else:
                    asunto = "🟢 [SAE] Sin notificaciones nuevas hoy"
                    
                # Crear reporte en texto (para Telegram/WhatsApp) y HTML (para Email)
                mensaje_texto = armar_reporte_texto(notificaciones_normalizadas, total_no_leidas)
                html_correo = armar_reporte_html(notificaciones_normalizadas, total_no_leidas)
                
                enviar_notificaciones(asunto, mensaje_texto, html_correo)
                
                # Si hay notificaciones no leídas con texto extraído, enviar un mensaje individual por cada una
                unread_docs = [n for n in notificaciones_normalizadas if n["is_unread"] and n.get("texto_documento")]
                if unread_docs:
                    print(f"\n[SAE] Se encontraron {len(unread_docs)} documentos nuevos. Enviando contenidos individuales a Telegram y WhatsApp...")
                    import time
                    for idx, doc in enumerate(unread_docs):
                        doc_html = (
                            f"📄 <b>Nueva Notificación SAE</b>\n"
                            f"<b>Fecha:</b> {escape_html(doc['fecha'])}\n"
                            f"<b>Expte:</b> {escape_html(doc['expediente'])}\n"
                            f"<b>Carátula:</b> {escape_html(doc['caratula'])}\n"
                            f"<b>Fuero:</b> {escape_html(doc['fuero'])}\n"
                            f"<b>Detalle:</b> {escape_html(doc['detalle'])}\n\n"
                            f"📝 <b>Texto del Documento:</b>\n"
                            f"{escape_html(doc['texto_documento'])}"
                        )
                        print(f"[SAE] Enviando contenido del documento para Expte {doc['expediente']} ({idx+1}/{len(unread_docs)})...")
                        
                        # Esperar 2 segundos para evitar rate limit de CallMeBot y Telegram
                        time.sleep(2)
                        enviar_mensaje_telegram(doc_html)
                        
                        time.sleep(2)
                        enviar_mensaje_whatsapp(doc_html)
            else:
                print("[SAE] Sin novedades. Se omitió el envío de notificaciones (SEND_ON_NO_NOVELTY=False).")
                
            print("[SAE] Flujo completado de manera exitosa.")
            
        except Exception as e_principal:
            print(f"[SAE] [ERROR] Error durante la ejecución: {e_principal}")
            raise e_principal
        finally:
            print("[SAE] Cerrando el navegador...")
            context.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automatización de revisión de Notificaciones del Portal SAE por WP/Telegram.")
    parser.add_argument("--interactive", action="store_true", help="Ejecuta en modo visible para resolver CAPTCHAs e iniciar sesión.")
    parser.add_argument("--time", type=int, choices=[8, 11], help="Indica si se ejecuta bajo el trigger de las 8 AM o de las 11 AM.")
    args = parser.parse_args()
    
    # Si se especificó filtro de hora, verificar si corresponde ejecutar hoy
    if args.time is not None:
        if not check_execution_time(args.time):
            print("[SAE] Finalizando ejecución por no cumplir regla de tiempo hoy.")
            sys.exit(0)
            
    headless_mode = not args.interactive
    
    try:
        run_scraper(headless=headless_mode)
    except Exception as e:
        import traceback
        error_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error_log.txt")
        print(f"\n[SAE] [ERROR] Registrando detalles del error en: {error_file}")
        try:
            with open(error_file, "w", encoding="utf-8") as f:
                f.write(f"Fecha: {datetime.datetime.now()}\n")
                f.write(f"Error: {str(e)}\n")
                f.write("="*40 + "\n")
                traceback.print_exc(file=f)
        except Exception as log_err:
            print(f"[SAE] No se pudo guardar el archivo de log: {log_err}")
        raise

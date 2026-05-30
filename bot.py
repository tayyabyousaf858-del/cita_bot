"""
Cita Previa Extranjeria Monitor Bot
Structure matches Extranjería Notify Bot screenshots
"""
import os
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv

import requests
from bs4 import BeautifulSoup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler,
)

load_dotenv()
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))
BASE_URL = "https://icp.administracionelectronica.gob.es/icpco"

# Conversation states
SELECT_PROVINCE, SELECT_TRAMITE, SELECT_OFFICE, CONFIRM = range(4)

# In-memory user configs
user_configs: dict = {}

# ─── DATA ─────────────────────────────────────────────────────────────────────
PROVINCES = {
    "A Coruña": "15", "Albacete": "02", "Alicante": "03", "Almería": "04",
    "Araba": "01", "Asturias": "33", "Ávila": "05", "Badajoz": "06",
    "Barcelona": "08", "Bizkaia": "48", "Burgos": "09", "Cáceres": "10",
    "Cádiz": "11", "Cantabria": "39", "Castellón": "12", "Ceuta": "51",
    "Ciudad Real": "13", "Córdoba": "14", "Cuenca": "16", "Gipuzkoa": "20",
    "Girona": "17", "Granada": "18", "Guadalajara": "19", "Huelva": "21",
    "Huesca": "22", "Illes Balears": "07", "Jaén": "23", "La Rioja": "26",
    "Las Palmas": "35", "León": "24", "Lleida": "25", "Lugo": "27",
    "Madrid": "28", "Málaga": "29", "Melilla": "52", "Murcia": "30",
    "Navarra": "31", "Ourense": "32", "Palencia": "34", "Pontevedra": "36",
    "Salamanca": "37", "S.Cruz Tenerife": "38", "Segovia": "40", "Sevilla": "41",
    "Soria": "42", "Tarragona": "43", "Teruel": "44", "Toledo": "45",
    "Valencia": "46", "Valladolid": "47", "Zamora": "49", "Zaragoza": "50",
}

# All tramites combined (no category split — shown as one list like screenshot)
ALL_TRAMITES = [
    "POLICIA-CERTIFICADO DE REGISTRO DE CIUDADANO DE LA U.E.",
    "POLICIA - RECOGIDA DE TARJETA DE IDENTIDAD DE EXTRANJERO (TIE)",
    "POLICÍA TARJETA CONFLICTO UCRANIA–ПОЛІЦІЯ -КАРТКА ДЛЯ ПЕРЕМІЩЕНИХ ОСІБ ВНАСЛІДОК КОНФЛІКТУ В УКРАЇНІ",
    "POLICÍA-EXP.TARJETA ASOCIADA AL ACUERDO DE RETIRADA CIUDADANOS BRITÁNICOS Y SUS FAMILIARES (BREXIT)",
    "POLICÍA-EXPEDICIÓN DE TARJETAS CUYA AUTORIZACIÓN RESUELVE LA DIRECCIÓN GENERAL DE GESTIÓN MIGRATORIA",
    "POLICÍA-TOMA DE HUELLAS (EXPEDICIÓN DE TARJETA) INICIAL, RENOVACIÓN, DUPLICADO Y LEY 14/2013",
    "AUTORIZACIÓN DE REGRESO",
    "POLICIA - CERTIFICADOS CONCORDANCIA",
    "POLICIA- EXPEDICIÓN/RENOVACIÓN DE DOCUMENTOS DE SOLICITANTES DE ASILO",
    "POLICIA-CARTA DE INVITACIÓN",
    "POLICIA-CERTIFICADOS (DE RESIDENCIA, DE NO RESIDENCIA Y DE CONCORDANCIA)",
    "POLICIA-CERTIFICADOS Y ASIGNACION NIE (NO COMUNITARIOS)",
    "POLICIA-ASIGNACIÓN DE NIE",
    "POLICIA-AUTORIZACIÓN DE REGRESO",
    "POLICÍA-PRORROGA DE ESTANCIA",
    "POLICÍA-RECOGIDA DE TARJETA ROJA (PROTECCIÓN INTERNACIONAL)",
    "POLICÍA-SOLICITUD TARJETA ROJA",
    "POLICIA- SOLICITUD ASILO",
    "POLICIA-ASILO INFORMACION",
    "POLICIA - TÍTULOS DE VIAJE",
    "POLICÍA - SOLICITUD DE APATRIDA",
    "POLICÍA - CÉDULA DE INSCRIPCIÓN",
    "POLICIA - OTROS TRÁMITES COMISARIA",
    "ASIGNACION NIE CIUDADANOS COMUNITARIOS",
    "POLICÍA - COMUNICACIÓN DE CAMBIO DE DOMICILIO",
    "POLICÍA - PRORROGA DE ESTANCIA CON VISADO",
    "POLICÍA - PRORROGA DE ESTANCIA SIN VISADO",
    "POLICÍA - UCRANIA : SOLICITUD PROTECCIÓN TEMPORAL DESPLAZADOS",
    "POLICÍA-CONSULTA N.º DE NIE ASIGNADO",
    "POLICÍA-DECLARACIÓN DE ENTRADA",
    "POLICÍA-CERTIFICADOS UE",
    "POLICÍA-CERTIFICADOS (RESIDENCIA Y CONCORDANCIA)",
    "POLICÍA-ASIGNACIÓN NIE NO RESIDENTE NO COMUNITARIO",
    "POLICÍA-INFORMACION DE TRÁMITES DE LA COMISARÍA DE POLICIA",
    "Asignación de N.I.E.",
    "Certificado de residente o no residente",
    "AUTORIZACIONES EXTRAORDINARIAS: RESIDENCIA CIR. EXC. POR RAZÓN DE ARRAIGO Y ARRAIGO EXTRAORDINARIO",
    "AUT. DE RESIDENCIA TEMPORAL POR CIRCUNS. EXCEPCIONALES POR ARRAIGO",
    "FAMILIARES DE RESIDENTES COMUNITARIOS",
    "INFORMACIÓN",
    "SOLICITUD DE AUTORIZACIONES",
    "SOLICITUD DE AUTORIZACIONES INICIALES",
    "ACCESO A 1ª AUT. DE RESIDENCIA DE LARGA DURACIÓN Y LARGA DURACIÓN UE",
    "AUTORIZACIONES DE RESIDENCIA TEMPORAL Y PERMANENTE DE FAMILIAR DE CIUDADANO DE LA UNION EUROPEA",
    "AUTORIZACIONES DE RESIDENCIA TEMPORAL POR MOTIVOS DE ARRAIGO Y OTRAS CIRCUNSTANCIAS EXCEPCIONALES",
    "AUTORIZACIONES DE TRABAJO, RENOVACIONES, PRÓRROGAS Y MODIFICACIONES",
    "RENOVACIONES, PRÓRROGAS O MODIFICACIONES",
    "AUTORIZACIÓN DE RESIDENCIA DE MENORES O INCAPACITADOS NACIDOS EN ESPAÑA",
    "AUTORIZACIÓN DE RESIDENCIA DE MENORES O INCAPACITADOS NO NACIDOS EN ESPAÑA",
    "AUTORIZACIÓN DE RESIDENCIA TEMPORAL POR REAGRUPACIÓN FAMILIAR",
    "ESTANCIA POR ESTUDIOS",
    "MODIFICACIÓN de las SITUACIONES (sujeto legitimado EXTRANJERO)",
    "REGISTRO",
    "RENOVACIONES DE RESIDENCIA",
    "RESIDENCIA TEMPORAL DE FAMILIARES DE PERSONAS CON NACIONALIDAD ESPAÑOLA",
    "REAGRUPACIÓN FAMILIAR",
    "RENOVACIONES DE AUT. DE RESIDENCIA y/o AUT. DE RESIDENCIA Y TRABAJO",
    "RENOVACIÓN AUTORIZACIÓN RESIDENCIA POR REAGRUPACIÓN FAMILIAR",
    "AUTORIZACIONES DE TRABAJO POR ESTUDIOS",
    "RECUPERACIÓN DE LA AUTORIZACIÓN DE LARGA DURACIÓN",
]

OFFICES_BY_PROVINCE = {
    "15": ["CNP SANTIAGO COMPOSTELA EXTRANJEROS, AVD RODRIGO DE PADRON, SN, SANTIAGO DE COMPOSTELA","CNP COMISARIA A CORUÑA - LONZAS, C/ Médico Devesa Núñez, 4, A Coruña","CNP FERROL, AVENIDA DE SAN AMARO, S/N, FERROL","CNP Santa Uxía de Ribeira, Av/ Das Airos, 21, Ribeira","INSS - A Coruña - CAISS Nº 1, Avenida Pedro Barrié de la Maza, 18, A Coruña","Oficina de Correos-A CORUÑA OP-1500010, RUA ALCALDE MANUEL CASAS, S/N, CORUÑA (A)","Oficina de Correos-FERROL OP-1500011, PRA. GALICIA, S/N, FERROL","Oficina de Correos-SANTIAGO DE COMPOSTELA OP-1500012, RUA. DO FRANCO, 4, SANTIAGO DE COMPOSTELA","Oficina de Extranjería en A Coruña, C/ Real, 53, A CORUÑA"],
    "02": ["CNP ALBACETE BPEF, Buen Pastor, 1, Albacete","CNP HELLIN, FORTUNATO ARIAS, 2, HELLIN","CNP TARJETAS Expedición, CALDERON DE LA BARCA, 2, ALBACETE","Oficina de Correos-ALBACETE OP-200010, DIONISIO GUARDIOLA, 24-26, ALBACETE","TGSS - Administración 02/01, Avenida de España, 27, Albacete"],
    "03": ["CNP Alcoy, Placeta Les Xiques, S/N, Alcoy","CNP Alicante NIE, Ebanistería, 4-6, Alicante","CNP Alicante TIE, Campo de Mirra, 6, Alicante","CNP Benidorm, Apolo XI, 36, Benidorm","CNP Comisaría Provincial, C/ Isabel la Católica, 25, Alicante","CNP Denia, Avda Marquesado, 53, Denia","CNP Elche, El Abeto, 1, Elche","CNP Elda, Lamberto Amat, 26, Elda","CNP Orihuela, Sol, 34, Orihuela","CNP Torrevieja, Arquitecto Larramendi, 3, Torrevieja","OEX ALICANTE, EBANISTERIA, 4-6, ALICANTE","OEX ALTEA, SAN ISIDRO LABRADOR, 1, ALTEA"],
    "04": ["Almería OUE, C/ Marruecos, 1, Almeria","CNP ALMERIA, AVENIDA DEL MEDITERRANEO, 201, ALMERIA","CNP EL EJIDO, Avenida del bulevar, 117, El Ejido","CNP ROQUETAS DE MAR, Avda. Curro Romero, 46, Roquetas de Mar","INSS - Almería - CAISS Nº 1, Ctra. Sierra de Alhamilla, 170, Almería","Oficina de Correos-ALMERIA OP-0400010, AV SAN JUAN BOSCO, 35, ALMERÍA"],
    "01": ["CNP Comisaría Oficina de tramitación, Olaguibel, 15, Vitoria-Gasteiz","INSS - Araba - CAISS Nº 0, C/ Eduardo Dato, 36, Vitoria-Gasteiz","Oficina de Correos - VITORIA-GASTEIZ OP-0100010, KAL POSTAS, 9, VITORIA-GASTEIZ","Subdelegación del Gobierno en Alava, Olaguibel, 1, Vitoria-Gasteiz"],
    "33": ["CNP AVILES, Río San Martín, 2, AVILES","CNP GIJÓN, Plaza Máximo Gonzalez, s/n, Gijón","CNP OVIEDO - EXPEDICION TIE, Plaza de España, 3, Oviedo","CNP OVIEDO - OTROS DOCUMENTOS, PLAZA DE ESPAÑA, 3, OVIEDO","Oficina de Extranjería en Oviedo, Plaza de España, 3, Oviedo","SOLICITUD INICIAL ASILO, OFICINA DE EXTRANJEROS, PLAZA DE ESPAÑA 3, OVIEDO"],
    "05": ["CNP ÁVILA, PASEO SAN ROQUE, 34, ÁVILA","INSS - Ávila - CAISS Nº 1, Plaza Claudio Sánchez Albornoz, 2, Ávila","Oficina de Correos-AVILA OP-500010, PZ CATEDRAL, 2, ÁVILA","Oficina de Extranjería en Ávila, Hornos Caleros, 1, Ávila"],
    "06": ["BRIGADA PROVINCIAL EXTRANJERÍA Y FRONTERAS BADAJOZ CNP, AVD. RAMÓN Y CAJAL, S/N, BADAJOZ","CNP ALMENDRALEJO, Benito Pérez Galdós, S/N, ALMENDRALEJO","CNP BADAJOZ, Avenida Ramón y Cajal, s/n, BADAJOZ","CNP BADAJOZ CITA PREVIA POLICÍA TARJETAS, LA BOMBA, 9, BADAJOZ","CNP DON BENITO, AVENIDA DE CORDOBA, S/N, DON BENITO","CNP MÉRIDA BRIGADA, AVENIDA VALHONDO, 8, MERIDA-BADAJOZ","CNP MÉRIDA TARJETAS, AVENIDA VALHONDO, 8, MÉRIDA-BADAJOZ","CNP ZAFRA, PLAZA DEL PILAR REDONDO S/N, ZAFRA","OFICINA DE EXTRANJERÍA, CALLE LA BOMBA, 9, BADAJOZ"],
    "08": ["CNP RAMBLA GUIPUSCOA 74, RAMBLA GUIPUSCOA, 74, BARCELONA","CNP MALLORCA GRANADOS, MALLORCA, 213, BARCELONA","CNP PSJ PLANTA BAJA, PASSEIG SANT JOAN, 189, BARCELONA","CNP GUADALAJARA, Guadalajara, 1, Barcelona","CNP COMISARIA LHOSPITALET DE LLOBREGAT, Rbla. Just Oliveres, 43, L'HOSPITALET DE LLOBREGAT","CNP COMISARIA BADALONA, AVDA. DELS VENTS, 9, BADALONA","CNP COMISARIA CASTELLDEFELS, PLAÇA DE L'ESPERANTO, 4, CASTELLDEFELS","CNP COMISARIA CERDANYOLA DEL VALLES, VERGE DE LES FEIXES, 4, CERDANYOLA DEL VALLES","CNP COMISARIA CORNELLA DE LLOBREGAT, AV. SANT ILDEFONS, S/N, CORNELLA DE LLOBREGAT","CNP COMISARIA SANT FELIU DE LLOBREGAT, CARRERETES, 9, SANT FELIU DE LLOBREGAT","CNP COMISARIA EL PRAT DE LLOBREGAT, CENTRE, 4, EL PRAT DE LLOBREGAT","CNP COMISARIA SANT BOI DE LLOBREGAT, RIERA BASTÉ, 43, SANT BOI DE LLOBREGAT","CNP COMISARIA VILADECANS, AVDA. BALLESTER, 2, VILADECANS","CNP COMISARIA IGUALADA, PRAT DE LA RIBA, 13, IGUALADA","CNP COMISARIA MATARO, AV. GATASSA, 15, MATARO","CNP COMISARIA GRANOLLERS, RICOMA, 65, GRANOLLERS","CNP COMISARIA RUBI, TERRASSA, 16, RUBI","CNP COMISARIA SABADELL, BATLLEVELL, 115, SABADELL","CNP COMISARIA MONTCADA I REIXAC, MAJOR, 38, MONTCADA I REIXAC","CNP COMISARIA RIPOLLET, TAMARIT, 78, RIPOLLET","CNP COMISARIA SANT ADRIA DEL BESOS, AV. JOAN XXIII, 2, SANT ADRIA DEL BESOS","CNP COMISARIA SANT CUGAT DEL VALLES, VALLES, 1, SANT CUGAT DEL VALLES","CNP COMISARIA SANTA COLOMA DE GRAMENET, IRLANDA, 67, SANTA COLOMA DE GRAMENET","CNP COMISARIA TERRASSA, BALDRICH, 13, TERRASSA","CNP COMISARIA VIC, BISBE MORGADES, 4, VIC","CNP COMISARIA VILAFRANCA DEL PENEDES, Avinguda Ronda del Mar, 109, VILAFRANCA DEL PENEDES","CNP COMISARIA VILANOVA I LA GELTRU, CARRER D'OLÈRDOLA, 47, Vilanova i la Geltrú","CNP COMISARIA MANRESA, SOLER I MARCH, 5, MANRESA","TGSS - DIRECCIÓN PROVINCIAL, C/ Aragón, 273-275, Barcelona"],
    "48": ["CNP BILBAO JSP del País Vasco, Gordóniz, 8, Bilbao","INSS - Bizkaia - CAISS Nº 1, Avenida Sabino Arana, 3, Bilbao","Oficina Extranjería Bizkaia, Barroeta Aldamar, 1, Bilbao"],
    "09": ["CNP ARANDA DE DUERO, SAN FRANCISCO, 92, ARANDA DE DUERO","CNP COMISARIA BURGOS, Avenida Castilla y León, 3, BURGOS","CNP MIRANDA DE EBRO, ANTONIO CABEZON, 14, MIRANDA DE EBRO","Oficina de Extranjeria en Burgos, Vitoria, 34, Burgos"],
    "10": ["CNP CACERES BPEF, Avenida Pierre de Coubertin, 13, Cáceres","CNP PLASENCIA, CUEVA DE LA SERRANA, S/N, PLASENCIA","OFICINA DE EXTRANJERIA EN CACERES, C/Catedrático Antonio Silva, 7, CACERES"],
    "11": ["ALGECIRAS TR OFICINA EXRANJERÍA, P. Juan de Lima, 5, Algeciras","CÁDIZ COMISARÍA CUERPO N. DE POLICÍA, Avenida de Andalucía, 28, Cádiz","CÁDIZ OFICINA DE EXTRANJERÍA, Acacias, 2, Cádiz","CNP ALGECIRAS, AV. FUERZAS ARMADAS, 6, ALGECIRAS","CNP CHICLANA DE LA FRONTERA, LA FUENTE, 7, CHICLANA DE LA FRONTERA","CNP JEREZ DE LA FRONTERA, Avenida de la Universidad, 10, JEREZ DE LA FRONTERA","CNP LA LINEA CONCEPCIÓN, AVENIDA MENENDEZ PELAYO, S/N, LA LÍNEA DE LA CONCEPCIÓN","CNP PUERTO SANTA MARIA PUERTO REAL, Carpintero de rivera, s/n, Puerto Real","CNP ROTA, AVENIDA PRINCIPES DE ESPAÑA, 113, ROTA","CNP SAN FERNANDO, Avenida Constitución de 1978, S/N, SAN FERNANDO"],
}


# ─── WEB FETCH OFFICES ────────────────────────────────────────────────────────
def fetch_offices_from_web(province_code: str) -> list:
    try:
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        session.get(f"{BASE_URL}/index", timeout=15)
        r = session.post(f"{BASE_URL}/citar", data={"form": province_code, "btnAceptar": "Aceptar"}, timeout=15)
        soup = BeautifulSoup(r.text, "html5lib")
        sede_select = soup.find("select", {"name": "sede"})
        if not sede_select:
            return []
        return [opt.get_text(strip=True) for opt in sede_select.find_all("option")
                if opt.get("value", "").strip() not in ("", "0")]
    except Exception as e:
        logger.warning(f"Web fetch offices failed for {province_code}: {e}")
        return []


def get_offices(province_code: str) -> list:
    return OFFICES_BY_PROVINCE.get(province_code) or fetch_offices_from_web(province_code)


# ─── AVAILABILITY CHECK ───────────────────────────────────────────────────────
def check_availability(province_code: str, tramite: str, office_name: str) -> dict:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "es-ES,es;q=0.9",
    })
    result = {
        "available": False,
        "offices_found": [],
        "error": None,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        session.get(f"{BASE_URL}/index", timeout=15)
        r = session.post(f"{BASE_URL}/citar",
                         data={"form": province_code, "btnAceptar": "Aceptar"}, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html5lib")

        sede_select = soup.find("select", {"name": "sede"})
        if not sede_select:
            result["error"] = "No se encontró selector de oficina"
            return result

        # Build office value map
        office_map = {}
        for opt in sede_select.find_all("option"):
            val = opt.get("value", "").strip()
            text = opt.get_text(strip=True)
            if val and val != "0":
                office_map[text] = val

        # Determine which offices to check
        if office_name == "CUALQUIERA":
            offices_to_check = list(office_map.items())
        else:
            matched_val = office_map.get(office_name)
            if not matched_val:
                # partial match fallback
                for k, v in office_map.items():
                    if office_name[:25].lower() in k.lower():
                        matched_val = v
                        office_name = k
                        break
            offices_to_check = [(office_name, matched_val)] if matched_val else []

        if not offices_to_check:
            result["error"] = "Oficina no encontrada"
            return result

        available_offices = []
        for off_name, off_val in offices_to_check:
            try:
                r2 = session.post(f"{BASE_URL}/citar",
                                  data={"sede": off_val, "tramiteGrupo[0]": tramite, "btnAceptar": "Aceptar"},
                                  timeout=15)
                page_text = r2.text.lower()
                if "no hay citas disponibles" not in page_text and \
                   "en este momento no" not in page_text:
                    soup2 = BeautifulSoup(r2.text, "html5lib")
                    title = soup2.find("title")
                    title_text = (title.get_text() if title else "").lower()
                    if any(k in title_text for k in ["datos", "solicitante", "citar"]) or \
                       any(k in page_text for k in ["nombre", "apellido", "nie", "pasaporte"]):
                        available_offices.append(off_name)
            except Exception:
                continue

        if available_offices:
            result["available"] = True
            result["offices_found"] = available_offices

    except requests.RequestException as e:
        result["error"] = f"Error de red: {str(e)[:80]}"

    return result


# ─── SCHEDULER ────────────────────────────────────────────────────────────────
async def run_check_for_user(app: Application, chat_id: int):
    config = user_configs.get(chat_id)
    if not config or not config.get("active"):
        return

    result = await asyncio.get_event_loop().run_in_executor(
        None, check_availability,
        config["province_code"], config["tramite"], config["office"]
    )

    config["check_count"] = config.get("check_count", 0) + 1
    count = config["check_count"]
    now = result["checked_at"]

    if result["error"]:
        logger.warning(f"[{chat_id}] Error: {result['error']}")
        return

    if result["available"]:
        offices_text = "\n".join([f"✅Oficinas\n\n{o}" for o in result["offices_found"]])
        msg = (
            f"🔔<b>Cita encontrada</b>🔔\n\n"
            f"✅Provincia {config['province_name']}\n\n"
            f"✅Tramite {config['tramite']}\n\n"
            f"{offices_text}\n\n"
            f"<a href='https://icp.administracionelectronica.gob.es/icpco/index'>"
            f"Haz clic en este enlace para acceder al sitio oficial</a>\n\n"
            f"⏰ {now}"
        )
        await app.bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML",
                                   disable_web_page_preview=True)
        logger.info(f"✅ CITA FOUND → {chat_id}")
    else:
        logger.info(f"❌ No cita [{chat_id}] #{count} @ {now}")
        if count % 10 == 0:
            await app.bot.send_message(
                chat_id=chat_id,
                text=f"🔄 Monitoreando... {count} checks\n⏰ Último: {now}\n❌ Sin citas aún",
            )


# ─── HANDLERS ─────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>Extranjería Notify Bot</b>\n\n"
        "Te aviso cuando haya cita disponible.\n\n"
        "/agregar_aviso — Añadir aviso\n"
        "/stop — Detener monitoreo\n"
        "/estado_cuenta — Ver estado",
        parse_mode="HTML"
    )


async def estado_cuenta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    config = user_configs.get(chat_id)
    if not config:
        await update.message.reply_text("No tienes ningún aviso activo.\n\nUsa /agregar_aviso para empezar.")
        return
    estado = "🟢 Activo" if config.get("active") else "🔴 Detenido"
    await update.message.reply_text(
        f"<b>Estado:</b> {estado}\n\n"
        f"📍 <b>Provincia:</b> {config['province_name']}\n"
        f"📋 <b>Trámite:</b> {config['tramite']}\n"
        f"🏢 <b>Oficina:</b> {config['office']}\n\n"
        f"🔢 Checks: {config.get('check_count', 0)}\n"
        f"🕐 Iniciado: {config.get('started_at', 'N/A')}\n"
        f"⏱ Cada {CHECK_INTERVAL}s",
        parse_mode="HTML"
    )


async def agregar_aviso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 1: Show provinces in 3-column grid like screenshot."""
    prov_list = sorted(PROVINCES.keys())
    keyboard = []
    for i in range(0, len(prov_list), 3):
        row = []
        for j in range(3):
            if i + j < len(prov_list):
                name = prov_list[i + j]
                row.append(InlineKeyboardButton(name, callback_data=f"prov|{name}"))
        keyboard.append(row)

    await update.message.reply_text(
        "Selecciona la provincia requerida",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_PROVINCE


async def province_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 2: Show all tramites as single list."""
    query = update.callback_query
    await query.answer()
    province_name = query.data.split("|", 1)[1]
    context.user_data["province_name"] = province_name
    context.user_data["province_code"] = PROVINCES[province_name]

    keyboard = [[InlineKeyboardButton(
        t[:55] + "…" if len(t) > 55 else t,
        callback_data=f"tram|{i}"
    )] for i, t in enumerate(ALL_TRAMITES)]

    await query.edit_message_text(
        "Selecciona el trámite",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_TRAMITE


async def tramite_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 3: Show offices with 'Cualquiera' on top."""
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split("|")[1])
    context.user_data["tramite"] = ALL_TRAMITES[idx]

    province_code = context.user_data["province_code"]
    province_name = context.user_data["province_name"]

    await query.edit_message_text(f"⏳ Cargando oficinas de {province_name}...")

    offices = get_offices(province_code)

    keyboard = []
    # "Cualquiera" (Any office) — full width on top, bold
    keyboard.append([InlineKeyboardButton("Cualquiera", callback_data="office|CUALQUIERA")])
    # Individual offices
    for i, office in enumerate(offices):
        label = office[:55] + "…" if len(office) > 55 else office
        keyboard.append([InlineKeyboardButton(label, callback_data=f"office|{i}")])

    context.user_data["offices"] = offices

    await query.edit_message_text(
        "Selecciona la oficina",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_OFFICE


async def office_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 4: Confirm."""
    query = update.callback_query
    await query.answer()
    val = query.data.split("|", 1)[1]

    if val == "CUALQUIERA":
        office = "CUALQUIERA"
        office_display = "Cualquiera (todas las oficinas)"
    else:
        offices = context.user_data["offices"]
        office = offices[int(val)]
        office_display = office

    context.user_data["office"] = office

    province_name = context.user_data["province_name"]
    tramite = context.user_data["tramite"]

    keyboard = [[
        InlineKeyboardButton("✅ Confirmar", callback_data="confirm|yes"),
        InlineKeyboardButton("❌ Cancelar", callback_data="confirm|no"),
    ]]
    await query.edit_message_text(
        f"<b>Confirmar aviso:</b>\n\n"
        f"📍 <b>Provincia:</b> {province_name}\n"
        f"📋 <b>Trámite:</b> {tramite}\n"
        f"🏢 <b>Oficina:</b> {office_display}\n\n"
        f"⏱ Verificando cada {CHECK_INTERVAL}s",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return CONFIRM


async def confirm_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split("|")[1]
    chat_id = query.message.chat_id

    if choice == "yes":
        user_configs[chat_id] = {
            "province_name": context.user_data["province_name"],
            "province_code": context.user_data["province_code"],
            "tramite": context.user_data["tramite"],
            "office": context.user_data["office"],
            "active": True,
            "check_count": 0,
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        await query.edit_message_text(
            "✅ <b>Aviso añadido correctamente</b>\n\n"
            f"📍 {context.user_data['province_name']}\n"
            f"📋 {context.user_data['tramite'][:60]}\n"
            f"🏢 {context.user_data['office'][:60]}\n\n"
            "🔔 Te avisaré en cuanto haya cita disponible.",
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text("❌ Cancelado. Usa /agregar_aviso para volver a intentarlo.")

    return ConversationHandler.END


async def stop_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in user_configs and user_configs[chat_id].get("active"):
        user_configs[chat_id]["active"] = False
        await update.message.reply_text("⏹ Monitoreo detenido.\n\nUsa /agregar_aviso para reiniciar.")
    else:
        await update.message.reply_text("No hay monitoreo activo.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelado.")
    return ConversationHandler.END


# ─── SCHEDULER ────────────────────────────────────────────────────────────────
def setup_scheduler(app: Application):
    scheduler = AsyncIOScheduler()

    async def check_all():
        for chat_id in list(user_configs.keys()):
            await run_check_for_user(app, chat_id)

    scheduler.add_job(check_all, "interval", seconds=CHECK_INTERVAL)
    scheduler.start()
    logger.info(f"Scheduler started — every {CHECK_INTERVAL}s")


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set!")

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("agregar_aviso", agregar_aviso)],
        states={
            SELECT_PROVINCE: [CallbackQueryHandler(province_selected, pattern=r"^prov\|")],
            SELECT_TRAMITE:  [CallbackQueryHandler(tramite_selected,  pattern=r"^tram\|")],
            SELECT_OFFICE:   [CallbackQueryHandler(office_selected,   pattern=r"^office\|")],
            CONFIRM:         [CallbackQueryHandler(confirm_selection, pattern=r"^confirm\|")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("estado_cuenta", estado_cuenta))
    app.add_handler(CommandHandler("stop", stop_monitor))
    app.add_handler(conv)

    setup_scheduler(app)
    logger.info("Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

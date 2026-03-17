import os
import asyncio
import feedparser
import logging
from dotenv import load_dotenv
from curl_cffi import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ContextTypes, ApplicationBuilder, CommandHandler

# ==============================================================================
# --- IMPORTS DE LÓGICA EXTERNA Y MÓDULOS DE BASE DE DATOS ---
# ==============================================================================
# Estos módulos deben residir en las carpetas /bot y /database respectivamente.
# Asegúrate de que existan los archivos __init__.py en cada directorio.
from bot.motor_reglas import analizar_filtracion_y_recomendar
from database.crud import (
    registrar_suscriptor, 
    obtener_suscriptores, 
    obtener_suscriptores_separados, 
    contar_jugadores, 
    buscar_jugador_por_nombre
)

# Variable global para evitar duplicidad en el envío de filtraciones
ultima_filtracion_vista = None

# ==============================================================================
# --- 1. CONFIGURACIÓN DE ENTORNO Y SISTEMA DE LOGGING (KAN-11) ---
# ==============================================================================
# El logging es vital para auditar el comportamiento del bot en producción.
logging.basicConfig(
    filename='bot.log', 
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Cargamos las variables de entorno desde el archivo .env
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# ==============================================================================
# --- 2. FUNCIONES DE BÚSQUEDA AVANZADA (SCRAPING ESTRUCTURAL) ---
# ==============================================================================
def get_player_price_futwiz(player_id, player_slug, fc_version=25):
    """
    Función de legado del jefe para obtener precios en versiones específicas de FC.
    Utiliza curl_cffi para saltar protecciones de tipo anti-bot.
    """
    url = f"https://www.futwiz.com/en/fc{fc_version}/player/{player_slug}/{player_id}"
    logging.info(f"Iniciando scraping avanzado en Futwiz para ID: {player_id}")
    
    try:
        # Simulamos un navegador Chrome actualizado para evitar bloqueos
        response = requests.get(url, impersonate="chrome110", timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            precio_element = soup.select_one('.price-num')
            
            if precio_element:
                precio_raw = precio_element.text.strip()
                logging.info(f"Precio obtenido exitosamente: {precio_raw}")
                return precio_raw
            else:
                return "No listado / Extinto"
        elif response.status_code == 404:
            logging.warning(f"Jugador no encontrado (404) en URL: {url}")
            return "Error 404: El jugador no existe en la base de datos de Futwiz."
        else:
            return f"Error de servidor HTTP: {response.status_code}"
            
    except Exception as e:
        logging.error(f"Fallo crítico en get_player_price_futwiz: {str(e)}")
        return f"Error de conexión: {str(e)}"

# ==============================================================================
# --- 3. PROCESAMIENTO Y LIMPIEZA DE DATOS DE MERCADO (KAN-8 y KAN-9) ---
# ==============================================================================
def limpiar_precio(precio_texto):
    """
    Transforma strings de precio (ej: '1.2M' o '55K') en valores enteros.
    Es fundamental para cálculos matemáticos posteriores en el motor de reglas.
    """
    if not precio_texto or any(x in precio_texto for x in ["No listado", "Error", "Extinto"]):
        return 0
    
    # Limpiamos caracteres no numéricos comunes
    p = precio_texto.strip().upper().replace(',', '').replace(' ', '')
    
    try:
        if 'M' in p:
            return int(float(p.replace('M', '')) * 1000000)
        if 'K' in p:
            return int(float(p.replace('K', '')) * 1000)
        return int(p)
    except Exception as e:
        logging.error(f"Error parseando el precio '{precio_texto}': {e}")
        return 0

def obtener_precio_actual(url_jugador):
    """Realiza un scrapeo rápido para la visualización del usuario."""
    try:
        logging.info(f"Consultando precio rápido para: {url_jugador}")
        response = requests.get(url_jugador, impersonate="chrome110", timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            precio_element = soup.select_one('.price-num')
            if precio_element:
                return limpiar_precio(precio_element.text.strip())
        return 0
    except Exception as e:
        logging.error(f"Excepción en obtener_precio_actual: {e}")
        return 0

# ==============================================================================
# --- 4. GESTIÓN DE ALERTAS SEGMENTADAS (KAN-31, KAN-32) ---
# ==============================================================================
async def enviar_alerta_retrasada(context: ContextTypes.DEFAULT_TYPE):
    """
    KAN-31: Ejecuta el envío a usuarios Free tras cumplirse el delay de 15 minutos.
    KAN-32: Añade el texto publicitario para fomentar la conversión a VIP.
    """
    datos = context.job.data
    chat_ids_gratis = datos['ids']
    mensaje_original = datos['mensaje']
    
    # KAN-32: Mensaje de monetización
    footer_vip = (
        "\n\n⏳ *Recibiste esta alerta con 15 min de retraso. "
        "Para recibirla al instante y asegurar tu ganancia, actualizá a VIP con /vip*"
    )
    
    mensaje_final = f"{mensaje_original}{footer_vip}"
    
    logging.info(f"Procesando envío programado (KAN-31) para {len(chat_ids_gratis)} usuarios.")
    
    for chat_id in chat_ids_gratis:
        try:
            await context.bot.send_message(chat_id=chat_id, text=mensaje_final, parse_mode='Markdown')
        except Exception as e:
            logging.error(f"No se pudo entregar alerta programada al chat {chat_id}: {e}")

async def chequear_feed_periodico(context: ContextTypes.DEFAULT_TYPE):
    """Revisa el feed RSS de noticias cada minuto en búsqueda de Leaks o SBCs."""
    global ultima_filtracion_vista
    url_feed = "https://www.fifaultimateteam.it/en/feed/"
    
    try:
        feed = feedparser.parse(url_feed)
        if feed.entries:
            entrada = feed.entries[0]
            titulo = entrada.title
            link = entrada.link
            
            # Filtro de relevancia: solo noticias de mercado y nuevas filtraciones
            if ("SBC" in titulo.upper() or "LEAK" in titulo.upper()) and link != ultima_filtracion_vista:
                ultima_filtracion_vista = link
                
                logging.info(f"Nueva filtración detectada en el feed: {titulo}")
                
                # Procesamos con el motor de reglas externo
                recomendacion = analizar_filtracion_y_recomendar(titulo)
                full_msg = f"🚨 **ALERTA: NUEVA FILTRACIÓN DETECTADA** 🚨\n\n{titulo}\n🔗 {link}"
                
                if recomendacion:
                    full_msg += f"\n\n💡 **Análisis del Motor:**\n{recomendacion}"
                
                # Obtención de usuarios segmentados desde la base de datos
                listas = obtener_suscriptores_separados()
                vips = listas.get('vip', [])
                gratis = listas.get('gratis', [])
                
                # 1. Envío PRIORITARIO a usuarios VIP (Sin delay)
                for chat_id in vips:
                    await context.bot.send_message(chat_id=chat_id, text=full_msg, parse_mode='Markdown')
                
                # 2. Programación (KAN-31) para usuarios Free: 15 minutos (900s)
                if gratis:
                    context.job_queue.run_once(
                        enviar_alerta_retrasada, 
                        when=900, 
                        data={'ids': gratis, 'mensaje': full_msg}
                    )
                    logging.info("Alerta programada en JobQueue para segmento gratuito.")
                        
    except Exception as e:
        logging.error(f"Error crítico en el bucle de feed: {e}")

# ==============================================================================
# --- 5. COMANDOS DE USUARIO (KAN-12, KAN-33) ---
# ==============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando de inicio y registro de usuarios."""
    user = update.effective_chat
    if registrar_suscriptor(user.id, user.username, user.type):
        await update.message.reply_text("¡Hola! Estás suscrito correctamente. Recibirás alertas de mercado aquí. 🛎️")
    else:
        await update.message.reply_text("Ya te encuentras registrado en nuestra base de datos. 🛎️")

async def vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    KAN-33: Comando informativo sobre la suscripción VIP.
    """
    beneficios_msg = (
        "💎 **MEMBRESÍA PREMUM (VIP)** 💎\n\n"
        "✨ **Beneficios Exclusivos:**\n"
        "• Alertas de filtraciones al instante (0 delay).\n"
        "• Recomendaciones de inversión detalladas.\n"
        "• Acceso a comandos de búsqueda ilimitados.\n\n"
        "💰 **Costo Mensual:** $5 USD / 5.000 ARS\n\n"
        "💳 **Métodos de Pago:**\n"
        "• **Alias Mercado Pago:** tu.bot.pago\n"
        "• **Binance ID:** 12345678\n\n"
        "👉 *Envía el comprobante de transferencia a @TuUsuario para activar tu rango VIP.*"
    )
    await update.message.reply_text(beneficios_msg, parse_mode='Markdown')

async def precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Consulta manual de precios vía URL."""
    if not context.args:
        await update.message.reply_text("⚠️ Uso: /precio <URL_DE_FUTWIZ>")
        return
    await update.message.reply_text("⏳ Consultando servidores externos...")
    p = obtener_precio_actual(context.args[0])
    await update.message.reply_text(f"💰 El precio actual es: **{p}** monedas.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el estado actual del bot."""
    total_j = contar_jugadores()
    total_s = len(obtener_suscriptores())
    await update.message.reply_text(f"📊 **Estado del Bot:**\n- Jugadores rastreados: {total_j}\n- Suscriptores totales: {total_s}")

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Busca un jugador en la base de datos local."""
    if not context.args:
        await update.message.reply_text("⚠️ Uso: /buscar <Nombre>")
        return
    query = " ".join(context.args)
    resultados = buscar_jugador_por_nombre(query)
    if not resultados:
        await update.message.reply_text(f"❌ No se encontró a '{query}'.")
        return
    
    lista_res = f"🔍 **Resultados para '{query}':**\n\n"
    for r in resultados[:10]:
        lista_res += f"• {r['nombre']} ({r['rating']}) | {r['precio_actual']} 🪙\n"
    await update.message.reply_text(lista_res, parse_mode='Markdown')

# ==============================================================================
# --- 6. PUNTO DE ENTRADA PRINCIPAL ---
# ==============================================================================
if __name__ == "__main__":
    if TOKEN:
        print("🚀 Bot iniciado. Cargando KAN-31, KAN-32 y KAN-33...")
        logging.info("Sistema arrancado. Iniciando JobQueue y manejadores.")
        
        # Construcción de la aplicación de Telegram
        app = ApplicationBuilder().token(TOKEN).build()
        
        # Programamos el chequeo de filtraciones cada 60 segundos
        app.job_queue.run_repeating(chequear_feed_periodico, interval=60, first=10)
        
        # Registro de comandos de la interfaz de usuario
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("vip", vip))
        app.add_handler(CommandHandler("precio", precio))
        app.add_handler(CommandHandler("stats", stats))
        app.add_handler(CommandHandler("buscar", buscar))
        
        # Inicio del modo escucha
        app.run_polling()
    else:
        print("❌ Error: TELEGRAM_TOKEN no definido en el archivo .env")
        logging.error("No se pudo iniciar el bot por falta de credenciales.")
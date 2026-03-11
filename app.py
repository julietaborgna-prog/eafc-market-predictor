import os
import asyncio
from dotenv import load_dotenv
from curl_cffi import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- 1. CONFIGURACIÓN (KAN-11) ---
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# --- 2. LÓGICA DE PRECIOS (KAN-8 y KAN-9) ---
def limpiar_precio(precio_texto):
    """Lógica de la KAN-8: Convierte texto (ej: '15.5K') a número real"""
    if not precio_texto or any(x in precio_texto for x in ["No listado", "Error"]):
        return 0
    p = precio_texto.strip().upper().replace(',', '')
    try:
        if 'K' in p:
            return int(float(p.replace('K', '')) * 1000)
        return int(p)
    except:
        return 0

def obtener_precio_actual(url_jugador):
    """Lógica de la KAN-9: Extrae el precio real de la web"""
    try:
        # Usamos impersonate para evitar que la web nos bloquee
        response = requests.get(url_jugador, impersonate="chrome110", timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Selector para FutWiz (asegúrate de que coincida con la web)
            precio_element = soup.select_one('.price-num')
            if precio_element:
                return limpiar_precio(precio_element.text.strip())
        return 0
    except Exception as e:
        print(f"Error en scraping: {e}")
        return 0

# --- 3. COMANDOS DEL BOT (KAN-12 y KAN-14) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Respuesta de la KAN-12"""
    await update.message.reply_text("Hola, estoy listo para predecir el mercado")

async def precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Integración KAN-14: Lee la URL y busca el precio real"""
    
    # Verificamos si hay una URL después del comando /precio
    if not context.args:
        await update.message.reply_text(
            "⚠️ Uso incorrecto. Debes enviar la URL así:\n"
            "/precio https://www.futwiz.com/en/fc25/player/lionel-messi/45"
        )
        return

    url_usuario = context.args[0]
    await update.message.reply_text("⏳ Conectando con FutWiz para obtener el precio real...")

    # Ejecutamos la lógica de scraping (Ticket 3.5)
    precio_encontrado = obtener_precio_actual(url_usuario)

    if precio_encontrado > 0:
        await update.message.reply_text(f"💰 El precio real actual es: **{precio_encontrado}** monedas.")
    else:
        await update.message.reply_text("❌ No pude obtener el precio. Verifica que la URL sea válida.")

# --- 4. EJECUCIÓN ---
if __name__ == "__main__":
    if TOKEN:
        print("🚀 Bot KAN-14 en línea. Esperando comandos...")
        app = ApplicationBuilder().token(TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("precio", precio))
        
        app.run_polling()
    else:
        print("❌ Error crítico: No se encontró el TOKEN en el .env")
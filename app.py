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
    """Lógica de la KAN-8: Limpia el texto de la web"""
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
    """Lógica de la KAN-9: Extrae el precio real"""
    try:
        response = requests.get(url_jugador, impersonate="chrome110", timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            precio_element = soup.select_one('.price-num')
            if precio_element:
                return limpiar_precio(precio_element.text.strip())
        return 0
    except:
        return 0

# --- 3. COMANDOS DEL BOT (KAN-12 y KAN-13) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Respuesta de la KAN-12"""
    await update.message.reply_text("Hola, estoy listo para predecir el mercado")

async def precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando Mock de la KAN-13: Siempre responde 1000"""
    await update.message.reply_text("El jugador cuesta 1000 monedas")

# --- 4. EJECUCIÓN ---
if __name__ == "__main__":
    if TOKEN:
        print("🚀 Bot iniciado correctamente...")
        app = ApplicationBuilder().token(TOKEN).build()
        
        # Registro de comandos 
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("precio", precio))
        
        app.run_polling()
    else:
        print("❌ Error: No se encontró el TOKEN en el archivo .env")
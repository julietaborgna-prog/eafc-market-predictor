import os
import asyncio
import feedparser
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
    try:
        response = requests.get(url_jugador, impersonate="chrome110", timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            precio_element = soup.select_one('.price-num')
            if precio_element:
                return limpiar_precio(precio_element.text.strip())
        return 0
    except Exception as e:
        print(f"Error en scraping: {e}")
        return 0

# --- 3. LÓGICA DE FEED CON FILTRO DE RUIDO (KAN-15 y KAN-16) ---
def obtener_ultimo_filtrado():
    """Se conecta al feed y filtra solo mensajes con 'SBC' o 'Leak'"""
    url_feed = "https://www.fifaultimateteam.it/en/feed/"
    feed = feedparser.parse(url_feed)
    
    if feed.entries:
        # KAN-16: Buscamos en las últimas 5 entradas para encontrar algo relevante
        for entrada in feed.entries[:5]:
            titulo = entrada.title
            # Filtro: Solo si contiene SBC o Leak (insensible a mayúsculas/minúsculas)
            if "SBC" in titulo.upper() or "LEAK" in titulo.upper():
                return f"🔥 **FILTRACIÓN IMPORTANTE (SBC/Leak):**\n\n{titulo}\n\n🔗 {entrada.link}"
        
        return "🤫 Por ahora no hay filtraciones críticas. Todo está tranquilo."
    
    return "📭 No se pudo acceder al feed de noticias."

# --- 4. COMANDOS DEL BOT (KAN-12, KAN-14) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hola, estoy listo para predecir el mercado y darte filtraciones.")

async def precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """KAN-14: Integración de precios"""
    if not context.args:
        await update.message.reply_text("⚠️ Envía una URL después de /precio")
        return
    url_usuario = context.args[0]
    await update.message.reply_text("⏳ Buscando precio real...")
    p = obtener_precio_actual(url_usuario)
    await update.message.reply_text(f"💰 El precio es: {p} monedas.")

async def filtrados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """KAN-16: Comando filtrado"""
    await update.message.reply_text("📡 Conectando con el servidor de filtraciones...")
    noticia = obtener_ultimo_filtrado()
    await update.message.reply_text(noticia, parse_mode='Markdown')

# --- 5. EJECUCIÓN ---
if __name__ == "__main__":
    if TOKEN:
        print("🚀 Bot KAN-16 en línea. Comandos: /start, /precio, /filtrados")
        app = ApplicationBuilder().token(TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("precio", precio))
        app.add_handler(CommandHandler("filtrados", filtrados))
        
        app.run_polling()
    else:
        print("❌ Error: TOKEN no encontrado.")
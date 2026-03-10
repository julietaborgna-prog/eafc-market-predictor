# print("Hola mundo")

from curl_cffi import requests
from bs4 import BeautifulSoup

def limpiar_precio(precio_texto):
    """Lógica de la KAN-8: Convierte texto a entero (ej: '15.5K' -> 15500)"""
    if not precio_texto or any(x in precio_texto for x in ["No listado", "Error", "incorrecta"]):
        return 0
    p = precio_texto.strip().upper().replace(',', '')
    try:
        if 'K' in p:
            return int(float(p.replace('K', '')) * 1000)
        return int(p)
    except:
        return 0

# --- NUEVA FUNCIÓN KAN-9 ---
def obtener_precio_actual(url_jugador):
    """
    KAN-9: Envuelve la extracción y la limpieza en una sola función.
    Retorna el precio como un número entero.
    """
    print(f"Buscando y procesando: {url_jugador}")
    
    try:
        # 1. Extracción (Lógica de Santiago con curl_cffi)
        response = requests.get(url_jugador, impersonate="chrome110", timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            precio_element = soup.select_one('.price-num')
            
            if precio_element:
                texto_sucio = precio_element.text.strip()
                # 2. Limpieza (Lógica KAN-8 integrada)
                return limpiar_precio(texto_sucio)
        
        return 0 # Si algo falla, retorna 0 como número entero
            
    except Exception as e:
        print(f"Error de conexión: {e}")
        return 0

if __name__ == "__main__":
    # URL de prueba para Messi en FC25
    url_messi = "https://www.futwiz.com/en/fc25/player/lionel-messi/45"
    
    print("--- Ejecutando KAN-9 ---")
    
    # Ahora la llamada es mucho más limpia
    precio_final = obtener_precio_actual(url_messi)
    
    print(f"Resultado final (Entero): {precio_final}")
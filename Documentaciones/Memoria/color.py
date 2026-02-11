import fitz  # PyMuPDF
from itertools import groupby
from operator import itemgetter
import os

def is_page_colored(page, tolerance=2):
    """
    Analiza si una página tiene color real comparando los canales R, G y B.
    'tolerance' ayuda a ignorar ruidos mínimos o suavizados de fuentes.
    """
    # Obtenemos la imagen de la página en RGB
    pix = page.get_pixmap(colorspace=fitz.csRGB)
    
    # Extraemos los canales como una lista de bytes [R, G, B, R, G, B...]
    samples = pix.samples
    
    # Comparamos los canales de 3 en 3
    for i in range(0, len(samples), 3):
        r, g, b = samples[i], samples[i+1], samples[i+2]
        
        # Si la diferencia entre los canales es mayor a la tolerancia, hay color
        if abs(r - g) > tolerance or abs(g - b) > tolerance or abs(r - b) > tolerance:
            return True
            
    return False

def get_color_pages(pdf_path):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"No se encontró el archivo: {pdf_path}")

    doc = fitz.open(pdf_path)
    color_pages = []

    print(f"Analizando: {pdf_path} ({len(doc)} páginas)...")
    print("Esto puede tardar un poco más porque estamos analizando píxel a píxel.")

    for page_num in range(len(doc)):
        page = doc[page_num]
        
        if is_page_colored(page):
            color_pages.append(page_num + 1)
        
        # Indicador de progreso simple
        if (page_num + 1) % 20 == 0:
            print(f"Progreso: {page_num + 1}/{len(doc)} páginas analizadas...")

    doc.close()
    return color_pages

def format_intervals(data):
    if not data:
        return "Ninguna"
    ranges = []
    for k, g in groupby(enumerate(data), lambda x: x[0] - x[1]):
        group = list(map(itemgetter(1), g))
        if len(group) > 1:
            ranges.append(f"{group[0]}-{group[-1]}")
        else:
            ranges.append(str(group[0]))
    return ", ".join(ranges)

# --- CONFIGURACIÓN ---
archivo_pdf = "TFG IMPRIMIR BN.pdf" 

try:
    paginas_color = get_color_pages(archivo_pdf)
    total_color = len(paginas_color)

    print("\n" + "="*40)
    print(f"RESUMEN PARA IMPRESIÓN:")
    print(f"Total páginas a color detectadas: {total_color}")
    print(f"Intervalos a color: {format_intervals(paginas_color)}")
    print("="*40)

except Exception as e:
    print(f"Error: {e}")
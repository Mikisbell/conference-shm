"""
tools/bibliography_engine.py — Motor de Citas Dinámicas para el EIU
===================================================================
Este módulo inyecta de forma autónoma las referencias académicas en el 
artículo Markdown final, basándose en los comandos y bases de datos 
utilizadas durante la campaña de Research Director.
"""

from pathlib import Path

# Base de datos maestra de referencias (Cofre del Conocimiento)
CITATION_VAULT = {
    "peer_berkeley": (
        "PEER (Pacific Earthquake Engineering Research Center), "
        "'NGA-West2 Ground Motion Database', UC Berkeley, 2014. "
        "Available: https://ngawest2.berkeley.edu."
    ),
    "cismid_peru": (
        "CISMID (Centro Peruano Japonés de Investigaciones Sísmicas), "
        "'Red Acelerográfica Nacional del Perú (REDACIS)', UNI, Lima, Perú. "
        "Available: http://www.cismid.uni.edu.pe."
    ),
    "usgs": (
        "USGS (United States Geological Survey), "
        "'Earthquake Hazards Program - Strong Motion Data'. "
        "Available: https://earthquake.usgs.gov."
    ),
    "belico_stack": (
        "Belico Stack Architecture, "
        "'Cryptographic Edge-AI Structural Health Monitoring via LoRa IoT', "
        "GitHub Open Source Initiative, 2026."
    ),
    "lstm_ttf": (
        "Hochreiter, S., & Schmidhuber, J. (1997). "
        "'Long short-term memory'. Neural computation, 9(8), 1735-1780."
    )
}

def generate_bibliography(sources_used: list) -> str:
    """
    Construye la sección de referencias final del Markdown
    según las bases metodológicas consumidas.
    """
    bib_text = "\n## References\n"
    
    # Fuentes base siempre presentes en el Bélico Stack
    default_sources = ["belico_stack", "lstm_ttf"]
    
    # Combinar reduciendo duplicados
    all_sources = list(set(default_sources + sources_used))
    
    for idx, source_key in enumerate(all_sources, 1):
        if source_key in CITATION_VAULT:
            bib_text += f"[{idx}] {CITATION_VAULT[source_key]}\n"
        else:
            bib_text += f"[{idx}] Unknown Citation Key: {source_key}\n"
            
    return bib_text

if __name__ == "__main__":
    test_bib = generate_bibliography(["peer_berkeley"])
    print(test_bib)

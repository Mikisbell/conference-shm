# Dockerfile base del Ecosistema Búnker
# Provee un entorno reproducible para correr OpenSeesPy, Serial virtual y simulaciones 
# independientemente del SO anfitrión del investigador.

FROM python:3.10-slim

# 1. Configurar Usuario y Directorio
RUN useradd -m -s /bin/bash investigador
WORKDIR /home/investigador/bunker

# 2. Dependencias del Sistema (Linux riguroso)
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 3. Entorno de Python Virtual Integrado
ENV VIRTUAL_ENV=/home/investigador/bunker/.venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 4. Inyección de Librerías Core (El Stack Matemático - Bélico)
COPY simulation/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Instalamos librerías accesorias (Matplotlib, PyYAML, etc.)
RUN pip install --no-cache-dir \
    matplotlib \
    pandas \
    pyserial \
    pyyaml

# 5. Punto de inyección del código del dominio
COPY . .

# 6. Permisos y Entorno de Ejecución
RUN chown -R investigador:investigador /home/investigador/bunker
USER investigador

# Mantener el contenedor activo para recibir directivas del Bridge (Agent Teams)
CMD ["tail", "-f", "/dev/null"]

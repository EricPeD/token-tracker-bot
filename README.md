# Token Tracker Bot & Dashboard

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](https://github.com/EricPeD/token-tracker-bot/actions)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Linting: ruff](https://img.shields.io/badge/linting-ruff-blue.svg)](https://github.com/astral-sh/ruff)

Bot de Telegram y dashboard web para notificaciones y visualización de depósitos de tokens ERC-20 en la red Polygon.

## 🚀 Descripción del Proyecto

El **Token Tracker Bot** es una herramienta robusta y escalable diseñada para monitorizar direcciones de wallet en la red Polygon y notificar a los usuarios sobre depósitos de tokens ERC-20 específicos.

Además del bot, el proyecto incluye un **dashboard web interactivo** que ofrece una visualización de datos más rica, con autenticación segura vinculada a la cuenta de Telegram del usuario.

**Propósito:** Proporcionar un sistema completo que incluye alertas instantáneas a través de Telegram y una plataforma web para el análisis visual de la actividad de la wallet.

## ✨ Características Principales

### Comandos del Bot de Telegram

El bot ofrece una serie de comandos intuitivos para interactuar con él:

*   `/start`: Inicia la conversación con el bot.
*   `/help`: Muestra una lista detallada de todos los comandos disponibles.
*   `/setwallet <direccion>`: Configura o actualiza tu dirección de wallet de Polygon.
*   `/wallet`: Muestra la dirección de wallet que tienes configurada.
*   `/addtoken <direccion_contrato>`: Añade un token ERC-20 a tu lista de monitoreo.
*   `/removetoken <direccion_contrato|all>`: Elimina un token específico o todos los tokens de tu lista.
*   `/tokens`: Muestra una lista de todos los tokens que estás monitorizando.
*   `/check`: Ejecuta una comprobación manual de nuevos depósitos.
*   `/stats`: Muestra un resumen de tus balances de tokens y el valor neto estimado.
*   `/reset`: Borra el registro de la última transacción vista (útil para pruebas).

### 📊 Dashboard Web

El proyecto cuenta con un dashboard web accesible desde el navegador para una experiencia de usuario más visual.

*   **Autenticación Segura**: Inicia sesión usando tu cuenta de Telegram a través del widget oficial.
*   **Gestión de Sesión**: Utiliza JSON Web Tokens (JWT) para mantener la sesión segura y persistente en el frontend.
*   **Visualización de Datos**: 
    *   Muestra estadísticas generales como el número total de usuarios y transacciones.
    *   Muestra una lista de los tokens específicos que el usuario autenticado está monitorizando.
*   **Arquitectura Unificada**: El dashboard es servido directamente por FastAPI, lo que garantiza un rendimiento óptimo y elimina problemas de CORS o contenido mixto.

### Funcionalidades Clave del Sistema

*   **Soporte Multi-Usuario:** Cada usuario gestiona su propia configuración de forma independiente.
*   **Notificaciones Automáticas:** Un `polling_job` en segundo plano busca proactivamente nuevos depósitos.
*   **Interacción Robusta con APIs Externas:**
    *   **Paginación:** Manejo eficiente de grandes volúmenes de datos de Moralis para evitar la pérdida de transacciones.
    *   **Reintentos Automáticos:** Utiliza `tenacity` para reintentar llamadas a la API en caso de fallos transitorios.
*   **Gestión Asíncrona Eficiente:** Construido sobre `asyncio` y con `SQLAlchemy` asíncrono para operaciones no bloqueantes.

## 🏛️ Arquitectura y Tecnologías Clave

El proyecto sigue una arquitectura modular con separación de responsabilidades:

*   **`src/`**: Contiene toda la lógica del bot (manejadores, modelos, servicios, etc.).
*   **`static/dashboard/`**: Contiene los archivos del frontend (HTML, CSS, JS).
*   **`dashboardApp.py`**: Aplicación FastAPI que sirve tanto la API del dashboard como los archivos estáticos del frontend.

**Stack Tecnológico:**

*   **Python 3.12+**
*   **`python-telegram-bot`**: Framework para la interacción con la API de Telegram.
*   **`FastAPI`**: Framework web para crear la API del dashboard.
*   **`SQLAlchemy` (2.0 Async)**: ORM para la gestión de la base de datos SQLite.
*   **`aiohttp`**: Cliente HTTP asíncrono para llamadas a la API de Moralis.
*   **`pydantic-settings`**: Para una gestión de configuración estructurada.
*   **`python-jose`**: Para la creación y validación de JSON Web Tokens (JWT).
*   **`tenacity`**: Para implementar lógicas de reintentos robustas.
*   **`ruff` & `black`**: Herramientas para asegurar la calidad y el estilo del código.

## ⚙️ Instalación y Configuración Rápida

1.  **Clonar el Repositorio:**
    ```bash
    git clone https://github.com/EricPeD/token-tracker-bot.git
    cd token-tracker-bot
    ```

2.  **Crear y Activar un Entorno Virtual:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # En Linux/macOS
    # .venv\Scripts\activate   # En Windows
    ```

3.  **Instalar Dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configurar Variables de Entorno:**
    *   Copia el archivo de ejemplo: `cp .env.example .env`
    *   Edita el archivo `.env` y añade tus claves:
        ```
        TOKEN_TRACKER_BOT_TELEGRAM_TOKEN="TU_TELEGRAM_BOT_TOKEN"
        TOKEN_TRACKER_BOT_MORALIS_API_KEY="TU_MORALIS_API_KEY"
        # Opcional: Para depuración de SQLAlchemy, puedes añadir:
        # TOKEN_TRACKER_BOT_SQLALCHEMY_ECHO=True
        ```

5.  **Inicializar la Base de Datos:**
    ```bash
    python -c "import asyncio; from src.models import init_db; asyncio.run(init_db())"
    ```
    Esto creará el archivo `tx_storage.db` si no existe.

6.  **Ejecutar la Aplicación (Bot y Dashboard)**:
    Necesitarás **dos terminales** para ejecutar ambos componentes simultáneamente.

    **Terminal 1: Ejecutar el Bot de Telegram**
    ```bash
    python -m src.bot.main
    ```

    **Terminal 2: Ejecutar el Servidor del Dashboard**
    ```bash
    uvicorn dashboardApp:app --reload
    ```
    
    Una vez ejecutado, puedes acceder al dashboard en `http://127.0.0.1:8000/`.

## ✅ Principales Desafíos Resueltos

Durante el desarrollo, se abordaron y resolvieron varios desafíos técnicos críticos:

*   **Gestión Robusta de Sesiones de SQLAlchemy:** Se implementó un patrón explícito para la gestión de sesiones y transacciones asíncronas, evitando errores de concurrencia y fugas de conexión.
*   **Precisión con Números Grandes:** Se estableció un sistema para manejar y mostrar correctamente los montos de tokens, que son números extremadamente grandes, evitando "integer overflow" en la base de datos y usando el tipo `Decimal` en Python para la precisión.
*   **Resiliencia y Depuración de APIs Externas:** Se implementaron reintentos automáticos, paginación, y un sistema de logging para depurar y robustecer la comunicación con la API de Moralis.
*   **Autenticación y Arquitectura Web**: Se superaron desafíos de CORS y Contenido Mixto (Mixed Content) al refactorizar la aplicación para que FastAPI sirva tanto la API como el frontend, creando una arquitectura de origen único.
*   **Manejo de JWT**: Se corrigió un bug sutil de expiración de tokens (`Signature has expired`) relacionado con el manejo de zonas horarias en la generación de timestamps.

## 🗺️ Roadmap (Próximos Pasos)

El proyecto está en un estado funcional, pero hay muchas áreas para futuras mejoras:

*   **Dashboard**:
    *   Crear un endpoint y una vista para el historial de transacciones del usuario (`/api/me/transactions`).
    *   Integrar una librería de gráficos como `Chart.js` para visualizaciones de datos.
    *   Mejorar la UI/UX con indicadores de carga y una presentación más refinada de los datos.
*   **Bot**:
    *   Mejorar la precisión del formateo de tokens usando los decimales reales de cada contrato.
    *   Refinar los mensajes de error al usuario para que sean más específicos.
*   **Infraestructura y Despliegue**:
    *   Crear un `Dockerfile` para contenerizar la aplicación.
    *   Configurar un pipeline de CI/CD básico con GitHub Actions.

## 🙌 Contribuciones

¡Las contribuciones son bienvenidas! Este proyecto sirve como una excelente base de estudio y desarrollo. Si tienes ideas para mejoras, correcciones de errores o nuevas funcionalidades, no dudes en abrir un *issue* o *pull request*.
# Token Tracker Bot

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Tests](https://github.com/EricPeD/token-tracker-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/EricPeD/token-tracker-bot/actions)
[![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen)](https://codecov.io/gh/EricPeD/token-tracker-bot)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Linting: ruff](https://img.shields.io/badge/linting-ruff-blue.svg)](https://github.com/astral-sh/ruff)

Bot de Telegram para notificaciones en tiempo real de depósitos de tokens ERC-20 en la red Polygon.

## 🚀 Descripción del Proyecto

El **Token Tracker Bot** es una herramienta robusta y escalable diseñada para monitorizar **una única dirección de wallet** en la red Polygon y notificar a múltiples usuarios sobre depósitos de tokens ERC-20 específicos. Evolucionó de un prototipo básico a una aplicación con soporte multi-usuario, persistencia de datos y alta fiabilidad, asegurando que cada usuario reciba notificaciones precisas y oportunas de sus transacciones.

**Propósito:** Proporcionar a los usuarios de Telegram un sistema automatizado para rastrear y recibir alertas instantáneas sobre la entrada de tokens ERC-20 en **su wallet configurada** de Polygon.

## ✨ Características Principales

### Comandos de Usuario

El bot ofrece una serie de comandos intuitivos para interactuar con él:

*   `/start`: Inicia la conversación con el bot y muestra un mensaje de bienvenida.
*   `/help`: Muestra una lista detallada de todos los comandos disponibles y su uso.
*   `/setwallet <direccion>`: Configura tu dirección de wallet de Polygon para que el bot la monitorice. **Ten en cuenta que esto reemplazará cualquier wallet configurada previamente.**
*   `/wallet`: Muestra la dirección de wallet que tienes configurada actualmente.
*   `/addtoken <direccion_contrato>`: Añade un token ERC-20 específico (por su dirección de contrato) a la lista de monitoreo de **tu wallet configurada**.
*   `/tokens`: Muestra una lista de todos los tokens que tienes configurados para monitorizar en **tu wallet actual**.
*   `/check`: Ejecuta una comprobación manual de nuevos depósitos para **tu wallet y tokens monitorizados**.
*   `/stats`: Muestra un resumen de tus depósitos totales, agrupados por token, para **tu wallet configurada**.
*   `/reset`: Borra el registro de la última transacción vista (útil para pruebas, forzando notificaciones de transacciones antiguas).

### Funcionalidades Clave

*   **Soporte Multi-Usuario:** Cada usuario gestiona su propia configuración de wallet y tokens de forma independiente.
*   **Notificaciones en Tiempo Real:** Sistema de sondeo automático en segundo plano para notificaciones proactivas de nuevos depósitos.
*   **Validación Robusta:** Validación de formato para direcciones de wallet y contratos ERC-20, previniendo errores de entrada.
*   **Interacción Robusta con Moralis API:**
    *   **Paginación:** Manejo eficiente de grandes volúmenes de datos para evitar la pérdida de transacciones.
    *   **Reintentos Automáticos:** Utiliza `tenacity` para reintentar llamadas a la API en caso de fallos transitorios de red o servicio.
*   **Gestión Asíncrona Eficiente:** Construido sobre `asyncio` de Python y con `SQLAlchemy` asíncrono para operaciones de base de datos no bloqueantes.

### Limitaciones Actuales

Es importante destacar las limitaciones actuales del bot:

*   **Una Sola Wallet por Usuario:** Actualmente, cada usuario solo puede configurar y monitorizar una única dirección de wallet. Al usar `/setwallet`, cualquier dirección configurada previamente es reemplazada.
*   **Red Fija (Polygon):** Las operaciones del bot (monitoreo de depósitos, balances) están centradas exclusivamente en la red Polygon. No hay soporte nativo para monitorear tokens o wallets en otras redes blockchain simultáneamente.


## 🏛️ Arquitectura 

El bot sigue una arquitectura modular con separación de responsabilidades:

*   **`src/bot/`**: Contiene la lógica principal de la interfaz de Telegram, incluyendo los manejadores de comandos y el punto de entrada del bot.
*   **`src/watcher/`**: Implementa la lógica de negocio para interactuar con APIs de blockchain (Moralis) y gestionar el estado de las transacciones.
*   **`src/models/`**: Define el esquema de la base de datos utilizando SQLAlchemy ORM para la persistencia de usuarios, tokens y transacciones.
*   **`src/config/`**: Gestiona la carga de la configuración y las credenciales sensibles del bot desde variables de entorno.
*   **`src/utils/`**: Proporciona funciones de utilidad generales, como el formateo de mensajes para Telegram.

**Tecnologías Clave Utilizadas:**

*   **Python 3.12+**
*   **`python-telegram-bot`**: Framework para la interacción con la API de Telegram.
*   **`SQLAlchemy` (2.0 Async)**: ORM para la gestión de la base de datos (SQLite).
*   **`aiohttp`**: Cliente HTTP asíncrono para llamadas a la API de Moralis.
*   **`pydantic-settings`**: Para una gestión de configuración estructurada y segura.
*   **`tenacity`**: Para implementar lógicas de reintentos robustas en llamadas a API.
*   **`ruff` & `black`**: Herramientas para asegurar la calidad y el estilo del código.

## ⚙️ Instalación y Configuración Rápida

Sigue estos pasos para poner en marcha el Token Tracker Bot en tu entorno local:

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
    pip install -e .
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
    *   Puedes obtener el `TELEGRAM_BOT_TOKEN` de BotFather en Telegram.
    *   Puedes obtener la `MORALIS_API_KEY` registrándote en Moralis.

5.  **Inicializar la Base de Datos:**
    ```bash
    python -c "import asyncio; from src.models import init_db; asyncio.run(init_db())"
    ```
    Esto creará el archivo `tx_storage.db` y las tablas necesarias.

6.  **Ejecutar el Bot:**
    ```bash
    python -m src.bot.main
    ```
    Una vez ejecutado, el bot debería estar activo en Telegram. Puedes enviarle el comando `/start`.

## ✅ Principales Desafíos Resueltos

Durante el desarrollo, se abordaron y resolvieron varios desafíos técnicos críticos que son comunes en el desarrollo de bots y sistemas con bases de datos:

*   **Gestión Robusta de Sesiones y Transacciones (SQLAlchemy):**
    *   **Problema:** Errores como "A transaction is already begun on this Session" y advertencias de fugas de conexión.
    *   **Solución:** Se implementó un patrón estandarizado y explícito para la gestión de sesiones y transacciones asíncronas de SQLAlchemy, asegurando el aislamiento transaccional y la correcta liberación de recursos en manejadores y el `polling_job`.
*   **Precisión con Números Grandes (Tokens ERC-20):**
    *   **Problema:** "Integer overflow" al sumar grandes montos de tokens en la base de datos (SQLite). Los montos raw de tokens pueden ser números extremadamente grandes sin decimales explícitos.
    *   **Solución:** Los montos se almacenan como `String` para máxima precisión. La suma en SQL se realiza con un casting explícito a `REAL` para evitar el desbordamiento, y el formateo en Python se hace con el tipo `Decimal` para mantener la precisión y presentar un valor legible al usuario.
*   **Mensajes Formateados en Telegram (MarkdownV2):**
    *   **Problema:** Errores de parseo (`Can't parse entities: character 'X' is reserved...`) al enviar mensajes con formato MarkdownV2 que contenían caracteres especiales (`.`, `(`, `-`) no escapados en datos dinámicos o texto estático.
    *   **Solución:** Se desarrolló una utilidad `escape_md2` para escapar automáticamente caracteres reservados en datos dinámicos, y se implementó el escapado manual para caracteres reservados en texto estático dentro de las f-strings.
*   **Resiliencia en la Interacción con APIs Externas (Moralis):**
    *   **Problema:** Falta de robustez ante fallos transitorios de red, límites de velocidad o grandes volúmenes de datos.
    *   **Solución:** Integración de la librería `tenacity` para reintentos automáticos con backoff exponencial, y un sistema de paginación basado en cursor para asegurar la obtención completa de datos sin pérdidas.
*   **Ejecución y Estructura del Proyecto Python:**
    *   **Problema:** Problemas de `ModuleNotFoundError` y `IndentationError` debido a importaciones relativas y ejecución incorrecta del script.
    *   **Solución:** Se estandarizó la ejecución del bot como un módulo de Python (`python -m src.bot.main`) desde la raíz del proyecto, resolviendo problemas de rutas de importación.

## 🗺️ Roadmap (Próximos Pasos)

El proyecto está en constante evolución. Aquí se detallan algunas áreas clave para futuras mejoras:

### Fase 3: Mejoras de Funcionalidad y UX (Continuación)

*   [ ] Mejorar el formato de los números y fechas (especialmente fechas, más allá de los montos totales).
*   [ ] Almacenar y utilizar los decimales reales de cada token para un formateo preciso (actualmente se asume 18).
*   [ ] Refinar mensajes de error al usuario para mayor especificidad (en lugar de genéricos).

### Fase 4: Robustez y Despliegue

*   [ ] **CRÍTICO:** Añadir logging estructurado para producción. (Sustituir `print` por `logging` para una captura y gestión de errores más eficaz, con niveles y destinos configurables).
*   [ ] Evaluar la implementación de un conjunto mínimo de tests de integración para los comandos principales (ej. `/setwallet`, `/addtoken`, `/check` con mocks para Moralis y DB).
*   [ ] Renombrar `TxStorage.reset()` a `reset_last_timestamp()` para mayor claridad.
*   [ ] Crear un `Dockerfile` para contenerizar la aplicación.
*   [ ] Configurar un pipeline de CI/CD básico con GitHub Actions (linter, tests).
*   **Nota:** La resolución de `telegram.error.Conflict` (problema operacional al desplegar si hay otra instancia del bot activa) sigue siendo una preocupación de alta prioridad para un despliegue estable.

### Fase 5: Soporte Multi-Wallet y Multi-Chain (Major Feature)

*   [ ] **Rediseño del Esquema de la Base de Datos:**
    *   Introducir un nuevo modelo `Wallet` (`id`, `user_id`, `address`, `chain_id`).
    *   Modificar los modelos `UserToken` y `Transaction` para vincularse a `Wallet` en lugar de directamente a `User`.
    *   Añadir `chain_id` a `UserToken` y `Transaction`.
    *   Actualizar `LastTx` para guardar el último timestamp por wallet y chain.
*   [ ] **Modificación de la Lógica de Integración con APIs Externas (Moralis):**
    *   Adaptar `get_myst_deposits` y `get_wallet_token_balances` para aceptar `chain_id` dinámicamente, permitiendo consultar datos de diferentes redes.
*   [ ] **Rediseño de los Comandos del Bot:**
    *   Introducir nuevos comandos como `/addwallet <address> <chain>` y `/removewallet`.
    *   Permitir a los usuarios seleccionar una wallet activa o especificar la wallet/chain para comandos como `/addtoken`, `/check`, `/stats`.
    *   Implementar un comando `/listwallets` para mostrar las wallets configuradas.
*   [ ] **Mecanismo de Configuración de Cadenas:**
    *   Permitir la configuración de las cadenas soportadas, sus nombres y sus equivalentes en las APIs externas (ej., "polygon" para Moralis).

## 🙌 Contribuciones

¡Las contribuciones son bienvenidas! Este proyecto sirve como una excelente base de estudio y desarrollo. Si tienes ideas para mejoras, correcciones de errores o nuevas funcionalidades, no dudes en abrir un *issue* o *pull request*.

---
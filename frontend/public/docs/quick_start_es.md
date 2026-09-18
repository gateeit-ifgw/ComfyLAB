# ComfyLAB: Guía de Inicio Rápido y Resumen General
*Comfortable Lab Automation Blocks — Manual de Usuario, Resumen del Software y Referencia Práctica*

---

## 1. Introducción y Filosofía

### 1.1 ¿Qué es ComfyLAB?
**ComfyLAB** (**Comf**ortable **L**ab **A**utomation **B**locks) es una plataforma de programación visual de código abierto, diseñada específicamente para la automatización de experimentos científicos, prueba y medición, adquisición de datos (DAQ) y visualización en tiempo real.

En laboratorios de investigación modernos, los sistemas de medición automatizados a menudo requieren conectarse con hardware diverso (osciloscopios, fuentes de alimentación, multímetros, generadores de funciones, sensores personalizados) a través de varios protocolos (VISA, SCPI, Serial RS-232/RS-485, Ethernet, bibliotecas nativas DLL de C/C++). Escribir scripts de automatización tradicionales frecuentemente resulta en código repetitivo (boilerplate) para gestión de bucles, sincronización entre hilos, manejo de excepciones, análisis de datos y desarrollo de interfaces gráficas.

ComfyLAB resuelve este desafío proporcionando una interfaz gráfica limpia y modular, donde los usuarios arrastran **Bloques** funcionales a un lienzo digital, los conectan mediante **Cables** visuales y organizan los resultados en un **Dashboard** interactivo al instante.

---

### 1.2 Arquitectura Dual: Interfaz Web + Motor de Servidor en Python
ComfyLAB opera bajo un modelo cliente-servidor desacoplado, separando la interacción del usuario de la ejecución y comunicación de hardware:

| Capa | Rol Principal | Características Clave | Tecnologías |
| :--- | :--- | :--- | :--- |
| **Interfaz Web (Front-End)** | Interacción y Visualización | • Lienzo infinito con conexión visual drag-and-drop<br>• Cockpit dedicado de Dashboard del Operador (`D`)<br>• Gráficos 2D/3D en vivo y pizarra digital | React, XY Flow, Plotly |
| **API de Comunicación** | Transporte de Datos | • Transmisión bidireccional de telemetría vía WebSocket<br>• Endpoints REST para control de ejecución y estado | WebSockets, FastAPI |
| **Servidor (Back-End)** | Ejecución y Hardware | • Ejecutor de máquina de estados híbrida push/pull<br>• Gestor de bloqueos VISA y puertos serie<br>• Servidor de Instrumentos Virtuales integrados (SCPI)<br>• Matemática NumPy/SciPy y scripts políglotas | Python, PyVISA, NumPy, SciPy |

* **Lienzo Front-End & Dashboard**: Se ejecuta en navegadores web modernos (o como aplicación de escritorio compilada). Proporciona manipulación gráfica fluida, herramientas de auto-organización, zoom/pan interactivo en gráficos, capa de pizarra digital y un **Dashboard del Operador** que organiza tarjetas fijadas, controles y monitores en una sala de control simplificada.
* **Servidor Back-End**: Impulsado por Python y FastAPI. Administra bloqueos de hardware en tiempo real, consultas VISA/SCPI, cálculos matriciales pesados, ejecución multihilo, persistencia de archivos, entornos virtuales de Python y un proceso en segundo plano para **Instrumentos Virtuales**.

---

### 1.3 Seguridad y Protección Integradas

* **Protección de Instrumentos y Rutinas de Apagado Seguro (Teardown)**: El hardware físico de laboratorio (láseres, fuentes de alto voltaje, generadores RF) requiere una gestión estricta de seguridad. Si una ejecución de medición encuentra un error, se detiene manualmente o se pierde la conexión, ComfyLAB ejecuta automáticamente rutinas de apagado seguro (shutdown hooks) para desactivar salidas activas y devolver los instrumentos a estados seguros.
* **Verificación de Seguridad de Blueprints**: Al abrir blueprints de fuentes externas, ComfyLAB ejecuta comprobaciones de seguridad para evitar la ejecución no autorizada de scripts, ofreciendo confirmación rápida y control total antes de ejecutar código.
* **Acceso Remoto Seguro**: ComfyLAB admite la operación remota segura a través de la red mediante autenticación por token, lo que permite a los investigadores supervisar y controlar experimentos que se ejecutan en computadoras de laboratorio desde estaciones de trabajo remotas.
* **Comprobador Integrado de Actualizaciones**: Administrador de versiones en el diálogo *Acerca de* (About) que comprueba automáticamente nuevas versiones en PyPI / GitHub, muestra notas de versión y permite la actualización con un clic.

<div style="page-break-before: always; break-before: page;"></div>

---

## 2. Capacidades y Flexibilidad: Lo que Puede (y No Puede) Hacerse

ComfyLAB fue diseñado desde cero para ofrecer máxima flexibilidad sin limitar a los usuarios avanzados a plantillas rígidas.

### 2.1 Qué se Puede Hacer con ComfyLAB

| Área de Recurso | Capacidades y Puntos Clave |
| :--- | :--- |
| **Control de Hardware** | Soporte completo a VISA (GPIB, USB-TMC, TCP/IP, Serie RS-232/485) y SCPI. Drivers integrados para osciloscopios, DMMs, fuentes y espectrómetros. |
| **Instrumentos Virtuales** | Osciloscopio (`virt_osc`), generador de señales (`virt_siggen`) y circuito RC simulados. Pruebas y educación offline sin hardware físico. |
| **Dashboard del Operador** | Vista dedicada en cockpit (atajo `D`). Fija bloques o gráficos en Tarjetas de Control y Monitoreo organizadas. |
| **Tiempo y Progreso** | Bloque Countdown Wait (con botón saltar), barras de progreso (0–100%), reloj ETR y bucles inteligentes con salidas de `%` y ETR. |
| **Gráficos Científicos** | 2D y 3D en tiempo real: XY (lineal/log), Dual-Y, Barras, Box plot, Histograma, Superficie/Dispersión 3D, Polar, Cascada y Heatmaps. |
| **Bibliotecas Nativas** | Invocación directa de C/C++ (`.dll` en Windows, `.so` en Linux/macOS) mediante Editor de Firmas interactivo, sin código wrapper. |
| **Scripts Políglotas** | Bloques de script en 9 lenguajes: Python, Rust, JS, TS, Julia, R, Lua, Octave y Wolfram. Acceso a `COMFYLAB_WORKSPACE`. |
| **Ecosistema Python** | Conexión directa con entornos virtuales (`.venv`), permitiendo cualquier paquete PyPI (`scipy`, `pandas`, `torch`, `opencv`). |
| **Publicación y Paquetes** | Publica bloques de script directamente en la paleta lateral o empaqueta flujos completos en paquetes `.cfy`. |
| **Procesamiento de Señales** | Operaciones matriciales NumPy, espectro FFT, ajuste de curvas (Gaussiana, exponencial, polinómica), filtros digitales y detección de picos. |
| **Sub-Lienzos** | Agrupación de sub-grafos complejos en bloques de Clúster modulares y reutilizables con pines dinámicos de E/S. |
| **Capa de Pizarra** | Dibujos libres, notas y cajas geométricas de agrupación directamente sobre el lienzo (atajo `4`). |

---

### 2.2 Límites Realistas: Qué No Se Puede (o No Se Debe) Hacer

Aunque ComfyLAB maneja prácticamente cualquier tarea de medición científica, automatización y procesamiento de datos, es útil reconocer sus límites:

* **Determinismo de Tiempo Real Estricto en Microsegundos**: ComfyLAB se ejecuta sobre sistemas operativos estándar (Windows/Linux/macOS) mediante servidores Python/FastAPI. Está diseñado para bucles de automatización y muestreo en la escala de milisegundos a sub-segundos. **No** está destinado a lógica bare-metal en FPGA ni a bucles deterministas de sub-microsegundos (ej. control PWM de motores a 100 kHz). Para esas tareas, microcontroladores RTOS o placas FPGA deben gestionar la temporización de bajo nivel, comunicándose con ComfyLAB por serial/USB para supervisión, almacenamiento y gráficos.

> **Resumen**: Fuera del determinismo en microsegundos vía hardware FPGA, **prácticamente cualquier flujo de medición científica, automatización de laboratorio, adquisición de datos o graficado puede construirse en ComfyLAB**.

<div style="page-break-before: always; break-before: page;"></div>

---

## 3. Comparación con Paradigmas Alternativos

Comprender cómo se compara ComfyLAB con las herramientas de laboratorio tradicionales destaca sus ventajas tanto para la enseñanza como para la investigación:

| Característica / Aspecto | Python Puro | NI LabVIEW | MATLAB / Simulink | ComfyLAB |
| :--- | :--- | :--- | :--- | :--- |
| **Licencia y Costo** | Gratuito y Código Abierto | Comercial de alto costo | Comercial de alto costo | **Gratuito y Código Abierto (GPLv3)** |
| **Paradigma** | Script textual | Gráfico propietario G | Diagrama de bloques / script | **Diagrama Web + Código Políglota** |
| **Curva de Aprendizaje** | Alta (sintaxis, APIs) | Empinada (convenciones G) | Moderada (toolboxes) | **Baja (Drag-and-drop visual)** |
| **Interfaz y Gráficos** | Manual (PyQt, Tkinter) | Panel Frontal Integrado | Ventanas de Figura | **Gráficos 2D/3D & Dashboard (`D`)** |
| **Simulación Offline** | Mocks manuales | Mocks de software básicos | Motor físico de Simulink | **Instrumentos Virtuales SCPI Integrados** |
| **Archivos y Git** | Texto plano `.py` (Git-friendly) | Binario `.vi` (Conflictos en Git)| `.m` / Binario `.slx` | **Blueprints JSON Limpios (Git-friendly)** |
| **Código Personalizado** | Nativo en Python | Nodos complejos C/Python | Funciones S / MATLAB | **Scripts en 9 Lenguajes y DLL/SO** |
| **Arquitectura** | Script monolítico | Aplicación desktop pesada | Entorno desktop pesado | **Interfaz Web + Servidor FastAPI** |
| **Bloqueos de Hardware** | Implementación manual | Integrado en DAQmx | Instrument Toolbox | **Gestor de Bloqueo VISA Asíncrono** |

### Conclusiones Principales:
1. **Vs. Python Puro**: Python es sumamente potente, pero construir interfaces gráficas, gráficos interactivos en tiempo real, bucles de hardware y diagramas visuales exige cientos de líneas de código repetitivo. ComfyLAB mantiene todo el poder analítico de Python ofreciendo una interfaz visual inmediata y cockpit de operación.
2. **Vs. LabVIEW**: LabVIEW es ampliamente utilizado, pero sufre de costos elevados de licencia, archivos binarios propietarios que dificultan el control de versiones y dependencia de proveedor. ComfyLAB ofrece una alternativa moderna y libre con blueprints en JSON, instrumentos virtuales embebidos e integración web nativa.
3. **Vs. MATLAB**: MATLAB sobresale en álgebra matricial pero tiene licencias costosas. ComfyLAB aprovecha motores gratuitos y abiertos de NumPy/SciPy bajo el capó.

<div style="page-break-before: always; break-before: page;"></div>

---

## 4. Diseño de la Interfaz y Conceptos Fundamentales

### 4.1 Resumen del Diseño de la Interfaz

La interfaz de ComfyLAB consta de tres áreas funcionales principales rodeadas por controles superiores:

```
┌──────────────────────────────────────────────────────────────┐
│ BARRA SUPERIOR: [🟰][⚙️] | [▶ Ejecutar/⏸ Pausa] [🛑 Parar] | [📊 Dash]│
├────────────────┬──────────────────────────────┬──────────────┤
│ BARRA LATERAL  │ ÁREA PRINCIPAL / DASHBOARD   │ INSPECTOR    │
│ (Paleta Bloques│                              │ (Valores)    │
│                │  ┌───────┐   Cable Ejecución │              │
│ Buscar...      │  │ Entry │▶───┐              │ Entradas     │
│ Control Flujo  │  └───────┘    │              │ Datos en Vivo│
│ Matemáticas    │            ┌──▼────────────┐ │ Consola Logs │
│ VISA / Virtual │ Cable Datos│ Bloque Math   │ │              │
│ Instrumentos   │ ──────────▶└───────────────┘ │              │
│ Visualización  │                              │              │
│                │ [Minimapa]       [Herram 1-4]│              │
└────────────────┴──────────────────────────────┴──────────────┘
```

#### Descripción Detallada de la Interfaz:
* **Barra Superior**: Controles para ejecutar (▶️ / `Ctrl+R`), pausar (⏸️) y detener (🛑 / `Ctrl+Shift+R`) blueprints, abrir el **Dashboard del Operador** (📊 / `D`), acceder a la **ComfyLAB Store** (🛍️), guardar blueprints (`Ctrl+S`), cambiar temas de color y configurar opciones de VISA y diagnósticos.
* **Barra Lateral (Izquierda)**: Paleta con buscador que contiene todos los bloques nativos, bloques publicados, instrumentos virtuales y nodos de script agrupados por categoría.
* **Lienzo Principal (Centro)**: Espacio de trabajo infinito con zoom y desplazamiento para arrastrar y conectar bloques.
* **Inspector de Bloques (Derecha)**: Panel contextual que se abre al seleccionar un bloque. Muestra valores de pines en tiempo real, parámetros, notas de documentación y registros de consola.
* **Barra de Pestañas y Migas de Pan**: Permite navegar entre múltiples blueprints y profundizar en clústeres.

<div style="page-break-before: always; break-before: page;"></div>
---

### 4.2 Pines y Cables: Flujo de Ejecución vs. Valores de Datos

Las conexiones entre bloques en ComfyLAB se dividen estrictamente en dos categorías:

```
  Salida Ejec ▶══════════════════════════════▶ Entrada Ejec
              (Línea Violeta: Controla CUÁNDO se ejecutan los bloques)

  Salida Datos●──────────────────────────────● Entrada Datos
              (Línea Sólida: Transfiere VALORES bajo demanda)
```

1. **Pines de Ejecución (Flujo)**:
   * Representados por **conectores en forma de triángulo/flecha** y conectados mediante **líneas violetas (🟪)**.
   * Determinan el **orden temporal y flujo de control** (cuándo se ejecutan los pasos, repiten bucles o activan ramas).

2. **Pines de Datos (Valores)**:
   * Representados por **pines circulares de colores** y conectados mediante **líneas sólidas**.
   * Transportan **valores** (números, cadenas de texto, arreglos NumPy, diccionarios, identificadores de hardware).
   * Se evalúan bajo demanda cuando un bloque de ejecución solicita datos de entrada.

#### Referencia de Colores de Pines de Datos:
* 🟧 **Número (Naranja)**: Valores escalares enteros o decimales.
* 🟩 **Booleano (Verde)**: Banderas lógicas `True` o `False`.
* 🟪 **Cadena / String (Rosa)**: Textos, cadenas formateadas o comandos SCPI.
* 🟨 **Arreglo (Amarillo)**: Arreglos y matrices numéricas NumPy 1D/2D de alto rendimiento.
* 🟦 **Lista (Cian)**: Colecciones ordenadas de elementos.
* 🟫 **Diccionario (Marrón)**: Mapeos clave-valor.

---

### 4.3 Lógica de Ejecución y Cadenas Independientes
* **Disparo de Ejecución**: Al hacer clic en **Ejecutar Blueprint** (▶️ o `Ctrl+R`), la ejecución comienza en los bloques raíz (sin cables de ejecución entrantes) y avanza siguiendo los cables violetas.
* **Cadenas de Ejecución Independientes**: Si el lienzo contiene grupos de bloques aislados sin cables entre sí, ComfyLAB los trata automáticamente como cadenas paralelas que se ejecutan concurrentemente.
* **Bloques de Control de Flujo y Temporización**:
  * **Bucle For**: Ejecuta un sub-bucle una cantidad fija de iteraciones, emitiendo el índice actual, porcentaje de completitud (`%`) y tiempo restante estimado (`ETR`).
  * **Bucle Para Cada (For Each)**: Itera sobre cada elemento de una lista o arreglo, proporcionando elemento, índice, porcentaje y ETR.
  * **Bucle While**: Ejecuta continuamente un sub-bucle mientras una condición booleana permanezca en `True`.
  * **Bifurcación If / Else**: Enruta la ejecución hacia una salida `True` o `False` según una condición.
  * **Retraso / Sleep**: Pausa el flujo de ejecución durante un tiempo determinado (ms o segundos).
  * **Countdown Wait**: Pausa la ejecución con reloj digital regresivo en tiempo real, barra de descarga y botón para **Saltar Espera**.
  * **Barra de Progreso**: Widget visual dedicado para visualizar el avance de 0% a 100%.
  * **Reloj ETR**: Pantalla digital estilo sala de control con tiempo restante estimado (`HH:MM:SS` o `MM:SS`).
  * **Medidor de Tiempo (Measure Time)**: Mide con precisión el tiempo transcurrido entre eventos de ejecución.

---

### 4.4 Funciones Avanzadas

* **Dashboard del Operador y Tarjetas Fijadas (📊 / `D`)**: El Dashboard ofrece una vista despejada tipo sala de control para operar experimentos, presentar resultados u operar bancos de ensayo sin la distracción visual de cables y bloques.
  * **Fijar Bloques en el Dashboard**: Cualquier bloque o pin puede fijarse al Dashboard. Haz clic derecho en el bloque y selecciona **Pin to Dashboard**, presiona el icono de alfiler en el Inspector de Bloques o usa el botón correspondiente en widgets compatibles.
  * **Organización Inteligente**: Las entradas y controles se agrupan en **Tarjetas de Control**, mientras que los gráficos, indicadores y cronómetros forman **Tarjetas de Monitoreo**.
  * **Personalización**: Reordena tarjetas arriba/abajo, arrastra las esquinas de los gráficos para redimensionarlos o haz clic en el icono de salto para regresar instantáneamente al bloque en el lienzo.
  * **Vista Maximizada**: Maximiza el panel del dashboard para convertirlo en una estación de control a pantalla completa.
* **Bloques Persistentes (📌)**: Por defecto, los estados de los bloques se reinician en cada corrida. Marcar un bloque como **Persistente** mantiene vivos sus recursos (ej. conexiones VISA, puertos seriales abiertos o promedios acumulados) entre ejecuciones consecutivas.
* **Deshabilitar Bloques (🚫)**: Hacer clic derecho y seleccionar deshabilitar atenúa el bloque en el lienzo. Los bloques deshabilitados se omiten en la ejecución, transfiriendo las señales limpiamente sin ejecutar código.
* **Clústeres (Sub-lienzos 📦)**: Agrupa conjuntos complejos de bloques en un único bloque personalizado. Hacer doble clic en un clúster abre un sub-lienzo aislado, con migas de pan para navegar.
* **Modo Pizarra (🎨)**: Presiona el atajo `4` para alternar al modo de dibujo, agregando notas, cuadros de texto y formas geométricas sobre el lienzo.
* **ComfyLAB Store y Suscripciones (🛍️)**: Gestor integrado de paquetes que mantiene la distribución central ligera y portátil, ofreciendo acceso modular a drivers de fabricantes, clústeres especializados y blueprints completos de experimentos. Incluye instalación en 1 clic, resolución automática de dependencias y suscripciones con sincronización automática en el arranque.

<div style="page-break-before: always; break-before: page;"></div>

---

## 5. Resumen de Categorías de Bloques Nativos

| Categoría | Función Principal y Bloques Clave |
| :--- | :--- |
| 🔄 **Control de Flujo y Tiempo** | Orquestación de bucles y temporización: `Bucle For` (`For Loop`), `Bucle Para Cada`, `Bucle While`, `Si/Sino` (`If/Else`), `Esperar` (`Sleep`), `Espera con Cuenta Regresiva` (`Countdown Wait`), `Medir Tiempo`, `Temporizador`. |
| 🔢 **Matemáticas y Lógica** | Aritmética, lógica booleana y ecuaciones: `Sumar`, `Restar`, `Multiplicar`, `Dividir`, `Potencia`, `Calculadora` (`Calculator`), `Trigonometría`, comparaciones (`>`, `<`, `==`), compuertas lógicas (`AND`, `OR`, `NOT`). |
| 📝 **Datos y Cadenas** | Manipulación de texto y diccionarios: `Concatenar`, `Formatear Cadena`, `Dividir Cadena`, `Reemplazar Cadena`, `Crear Diccionario`, `Obtener Valor`, `Definir Clave/Valor`. |
| 📊 **Arreglos y Señales** | Procesamiento de matrices numéricas y señales: `Crear NDArray`, `Linspace`, `Cortar NDArray`, `Espectro FFT` (`FFT Spectrum`), `Filtro de Señal`, `Ajuste de Curva` (`Curve Fit`). |
| 💾 **Entrada/Salida de Archivos** | Persistencia y exportación de datos: `Guardar CSV` (`Save CSV`), `Cargar CSV`, `Guardar JSON`, `Cargar JSON`, `Guardar Parquet`, `Cargar Parquet`, `Imagen a Matriz`. |
| 📡 **VISA y Hardware Físico** | Comunicación con instrumentos: `Dispositivo VISA` (`VISA Device`), `Consulta VISA` (`VISA Query`), `Lectura VISA` (`VISA Read`), `Escritura VISA` (`VISA Write`), `Administrador de Recursos VISA`. |
| 🖥️ **Instrumentos Virtuales** | Simulación sin hardware: `Conexión VirtOsc`, `Adquirir VirtOsc`, `Conexión VirtSigGen`, `Configurar Onda VirtSigGen`, `Circuito RC Simulado`. |
| 🔬 **Drivers Modulares de Fabricantes** | Drivers modulares instalados a pedido vía ComfyLAB Store: Osciloscopios (Tektronix, Keysight), Multímetros (HP/Agilent 34401A), Fuentes DC, Espectrómetros Horiba, Digitalizadores CAEN, Motores Thorlabs, Minipa, etc. |
| 📈 **Visualización y Dashboard** | Visualización de datos y monitoreo: `Gráfico XY` (`XY Plot`), `Gráfico de Tiempo`, `Gráfico de Doble Eje Y`, `Gráfico Box / Violin`, `Gráfico de Barras`, `Histograma`, `Gráfico 3D`, `Gráfico Polar`, `Espectrograma Cascada`, `Mapa de Calor`, `Barra de Progreso`, `Reloj ETR`. |
| ⚙️ **Scripts y Nativo** | Extensiones personalizadas: `Script Python` (`Python Script`), `Python Externo`, `Script JavaScript`, `Script TypeScript`, `Script Julia`, `Script Rust`, `Script Lua`, `Script Octave`, `Script R`, `Script Wolfram`, `Cargar DLL/SO`. |

<div style="page-break-before: always; break-before: page;"></div>

---

## 6. Tutoriales Prácticos de Iniciación

Sigue estos ejemplos prácticos paso a paso para dominar rápidamente los flujos y capacidades de ComfyLAB.

<div style="page-break-before: always; break-before: page;"></div>

---

### Tutorial 1: Pipeline Matemático e Inspección en Vivo
**Objetivo**: Crear dos números, multiplicarlos, evaluar una expresión matemática usando el bloque **Calculadora** (`Calculator`) e inspeccionar el resultado en el Inspector de Bloques.

```
┌──────────────┐
│ Número (5.0) ├──┐   ┌─────────────┐   ┌─────────────┐
│ Salida       │  ├──▶│ Multiplicar ├──▶│ Calculadora ├──► Resultado
└──────────────┘  │   └─────────────┘   │ "x^2 + 10"  │
┌──────────────┐  │                     └─────────────┘
│ Número (3.0) ├──┘
│ Salida       │
└──────────────┘
```

#### Instrucciones Paso a Paso:
1. Abre ComfyLAB y crea un nuevo workspace/blueprint.
2. En la **Barra Lateral** izquierda, busca **Número** (`Number`, en *Constantes*) y arrastra **dos** bloques Número al lienzo.
3. Establece el valor del primer bloque en `5.0` y el del segundo en `3.0`.
4. Arrastra un bloque **Multiplicar** (`Multiply`, en *Matemáticas / Básica*) al lienzo.
5. Conecta el pin de datos del Número 1 a la Entrada A del bloque Multiplicar, y el Número 2 a la Entrada B.
6. Arrastra un bloque **Calculadora** (`Calculator`, en *Matemáticas / Básica*) al lienzo. En el Inspector de Bloques, define la expresión como `x^2 + 10` y añade la variable `x`.
7. Conecta el pin de salida de Multiplicar (`15.0`) a la entrada `x` del bloque Calculadora.
8. Haz clic en **Ejecutar Blueprint** (▶️ o `Ctrl+R`) en la barra superior.
9. Haz clic en el bloque **Calculadora** para abrir el **Inspector de Bloques** a la derecha.
10. **Verificación**: En el Inspector, revisa el valor en vivo en el pin **Resultado** (`Result`). Debe evaluarse como `(15)^2 + 10 = 235.0`.

<div style="page-break-before: always; break-before: page;"></div>

---

### Tutorial 2: Generación de Señal Sintética y Graficado en Vivo
**Objetivo**: Generar un arreglo de onda senoidal ruidosa, calcular su espectro FFT y mostrarlo en un bloque **Gráfico XY** (`XY Plot`).

```
┌────────────────────┐     ┌────────────────────┐
│ Linspace (0 a 10s) ├────▶│Onda Senoidal (5 Hz)├─┐
└────────────────────┘     └────────────────────┘ │
                                                  ▼
┌────────────────────┐     ┌────────────────────┐ │
│ Bloque Gráfico XY  │◀────┤ Sumar(Señal+Ruido) │◀┘
└────────────────────┘     └─────────┬──────────┘
                                     │
                                     ▼
                           ┌────────────────────┐
                           │ Espectro FFT       │
                           └────────────────────┘
```

#### Instrucciones Paso a Paso:
1. Busca **Linspace** (en *Arreglos Numéricos*) en la Barra Lateral. Establece `Start = 0`, `Stop = 10`, `Points = 1000` para generar un vector de tiempo.
2. Busca **Onda Senoidal** (`Sine Wave`, en *Matemáticas / Funciones*). Conecta la salida de Linspace a la entrada `X` del bloque Onda Senoidal. Establece `Frecuencia = 5.0` Hz.
3. Agrega un bloque **Matriz Aleatoria** (`Random Array`, en *Matemáticas / Aleatorio*, establece `Forma = 1000`, `Mín = -0.2`, `Máx = 0.2`) y un bloque **Sumar** (`Add`) para sumar el ruido a la señal.
4. Arrastra un bloque **Gráfico XY** (`XY Plot`, en *Gráficos*) al lienzo.
5. Conecta el arreglo de tiempo de Linspace al pin **X** del Gráfico XY y la señal con ruido al pin **Y**. Conecta un cable de ejecución al pin **Graficar** (`Plot`).
6. (Opcional) Conecta la señal a un bloque **Espectro FFT** (`FFT Spectrum`, en *Matemáticas / Procesamiento de Señales*) para visualizar los picos de frecuencia.
7. Haz clic en **Ejecutar Blueprint** (▶️ o `Ctrl+R`).
8. **Verificación**: El widget del Gráfico XY mostrará inmediatamente la onda senoidal con ruido en tiempo real. ¡Usa la rueda del ratón para hacer zoom y arrastra para desplazarte por los ejes!

<div style="page-break-before: always; break-before: page;"></div>

---

### Tutorial 3: Barrido Automatizado de Parámetros y Registro en CSV
**Objetivo**: Usar un **Bucle For** (`For Loop`) para barrer voltajes, calcular la corriente y guardar los datos en un archivo CSV con el bloque **Guardar CSV** (`Save CSV`).

```
┌─────────────────────┐    ┌────────────────────┐
│ Bucle For (0 a 50)  │▶──▶│ Guardar CSV        │
└──────────┬──────────┘    │ "sweep_results.csv"│
           │ (Índice)      └────────────────────┘
           ▼
┌─────────────────────┐
│ Voltaje = Ind*0.1   │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ Corriente = V / R   ├─► Gráfico XY
└─────────────────────┘
```

#### Instrucciones Paso a Paso:
1. Arrastra un bloque **Bucle For** (`For Loop`, en *Control de Flujo*) al lienzo.
2. Establece `Iteraciones = 50`. Observa que el bloque proporciona pines de porcentaje (`%`) y tiempo restante estimado (`ETR`).
3. Dentro de la ruta de ejecución del bucle, multiplica el pin `Índice` (`Index`) por `0.1` usando un bloque **Multiplicar** (`Multiply`) para crear un barrido de `0.0 V` a `5.0 V`.
4. Divide el voltaje entre una resistencia fija (`R = 100 Ohms`) usando un bloque **Dividir** (`Divide`) para obtener la corriente `I`.
5. Arrastra un bloque **Guardar CSV** (`Save CSV`, en *Entrada / Salida*) al lienzo. Nombra `Ruta de Archivo` (`FilePath`) como `sweep_results.csv`.
6. Conecta los valores al pin `Datos` (`Data`) de Guardar CSV. Conecta el cable de ejecución `Cuerpo` (`Body`) del bucle al pin `Escribir` (`Write`) de Guardar CSV.
7. Conecta el cable de ejecución `Salida` (`Out`) de Guardar CSV de regreso a la entrada `Paso` (`Step`) del bucle para completar la iteración.
8. Haz clic en **Ejecutar Blueprint** (▶️ o `Ctrl+R`).
9. **Verificación**: Observa el avance paso a paso. Al finalizar, abre la carpeta de tu espacio de trabajo: ¡encontrarás `sweep_results.csv` con las 50 filas registradas!

<div style="page-break-before: always; break-before: page;"></div>

---

### Tutorial 4: Creación y Publicación de un Bloque Script Python Personalizado
**Objetivo**: Crear un bloque **Script Python** (`Python Script`) personalizado que filtre valores por debajo de un umbral, probarlo y publicarlo en la paleta de la barra lateral.

```
┌──────────────────────────────────────────────────┐
│ Bloque Script Python                             │
│ Entradas: data_in (Arreglo), threshold (Número)  │
│ Salidas:  filtered_data (Arreglo), count (Número)│
├──────────────────────────────────────────────────┤
│ arr = np.array(inputs['data_in'])                │
│ result = arr[arr > inputs['threshold']]          │
│ outputs['filtered_data'] = result.tolist()       │
│ outputs['count'] = len(result)                   │
└──────────────────────────────────────────────────┘
```

#### Instrucciones Paso a Paso:
1. Arrastra un bloque **Script Python** (`Python Script`, de *Scripts*) al lienzo.
2. En el **Inspector de Bloques**, haz clic en **Editar Pines** (`Edit Pins`):
   * Añadir Pin de Entrada: `data_in` (Tipo: Array)
   * Añadir Pin de Entrada: `threshold` (Tipo: Number)
   * Añadir Pin de Salida: `filtered_data` (Tipo: Array)
   * Añadir Pin de Salida: `count_passed` (Tipo: Number)
3. Haz doble clic en el bloque Script Python para abrir el editor Monaco integrado.
4. Escribe el código Python mostrado arriba. (Observa que `os.environ["COMFYLAB_WORKSPACE"]` está disponible si tu script necesita acceder a archivos del proyecto).
5. Conecta un arreglo de prueba a `data_in` y establece `threshold = 2.5`.
6. Haz clic en **Ejecutar Blueprint** (▶️) y revisa `filtered_data` y `count_passed` en el Inspector de Bloques.
7. Una vez comprobado, haz clic en **Publicar Bloque** (`Publish Block`) en el Inspector. Nómbralo `Filtro Umbral`, elige un icono y asígnalo a la categoría `Arrays`.
8. **Verificación**: Observa tu **Barra Lateral** izquierda: ¡tu nuevo bloque `Filtro Umbral` estará disponible permanentemente para ser usado en cualquier lienzo de tu espacio de trabajo!

<div style="page-break-before: always; break-before: page;"></div>

---

### Tutorial 5: Interfaz de Hardware VISA (Consulta SCPI de Identificación)
**Objetivo**: Conectar a un instrumento mediante VISA usando el bloque **Dispositivo VISA** (`VISA Device`), enviar una consulta con **Consulta VISA** (`VISA Query`) y mostrar la respuesta de identificación del fabricante.

```
┌──────────────────┐     ┌──────────────────┐
│ Dispositivo VISA │▶───▶│ Consulta VISA    ├──► Respuesta: "*IDN?..."
│ Dirección: ...   ├────▶│ Comando: *IDN?   │
└──────────────────┘     └──────────────────┘
```

#### Instrucciones Paso a Paso:
1. Arrastra un bloque **Dispositivo VISA** (`VISA Device`, en *Instrumentos / VISA*) al lienzo. Establece `Dirección` (`Address`) con la dirección de tu instrumento (ej. `TCPIP0::192.168.1.100::INSTR`, `GPIB0::14::INSTR`, `COM3` o `VIRT::OSC`).
2. Arrastra un bloque **Consulta VISA** (`VISA Query`, en *Instrumentos / VISA*) al lienzo.
3. Conecta el cable de ejecución `Salida` (`Out`) de Dispositivo VISA a la entrada `Entrada` (`In`) de Consulta VISA.
4. Conecta el pin `Dispositivo` (`Device`, cian) de Dispositivo VISA a la entrada `Dispositivo` (`Device`) de Consulta VISA.
5. Establece el parámetro `Comando` (`Command`) en Consulta VISA como `*IDN?`.
6. Haz clic en **Ejecutar Blueprint** (▶️ o `Ctrl+R`). (ComfyLAB administra automáticamente bloqueos y apagado seguro).
7. **Verificación**: Haz clic en el bloque **Consulta VISA** y revisa el Inspector de Bloques. El pin de salida `Respuesta` (`Response`) mostrará la identificación (ej. `HEWLETT-PACKARD,34401A,0,11-5-2` o `KEYSIGHT TECHNOLOGIES,DSOX2002A,...`).
8. **Consejo**: ¡También puedes usar el bloque **Administrador de Recursos VISA** (`VISA Resource Manager`) para descubrir instrumentos automáticamente!

<div style="page-break-before: always; break-before: page;"></div>

---

### Tutorial 6: Automatización Offline con Instrumentos Virtuales Integrados
**Objetivo**: Conectar a los instrumentos virtuales de ComfyLAB, configurar un generador de señales simulado, capturar la forma de onda con el osciloscopio virtual y monitorear los resultados en el Dashboard sin necesidad de hardware físico.

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│ Conexión VirtSigGen │▶───▶│Configurar Onda VirtS│▶───▶│ Conexión VirtOsc     │
│ (TCP Virtual)       ├────▶│ Freq: 1 kHz         │     │ (TCP Virtual)       │
└─────────────────────┘     └─────────────────────┘     └──────────┬──────────┘
                                                                   │
                                                                   ▼
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│ Fijar en            │◀────┤ Bloque Gráfico XY   │◀────┤ Adquirir VirtOsc    │
│ Dashboard (D)       │     │ Tiempo vs Tensión   │     │ Datos Canal 1       │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

#### Instrucciones Paso a Paso:
1. En la Barra Lateral, navega hasta la categoría **Dispositivos > Virtual**.
2. Arrastra un bloque **Conexión VirtSigGen** (`VirtSigGen Connect`) y un bloque **Configurar Onda VirtSigGen** (`VirtSigGen Config Wave`). Conéctalos para generar una onda senoidal de 1.0 kHz a 2.0 Vpp.
3. Arrastra un bloque **Conexión VirtOsc** (`VirtOsc Connect`) y un bloque **Adquirir VirtOsc** (`VirtOsc Acquire`). Conecta el flujo de ejecución y los identificadores de dispositivo.
4. Arrastra un bloque **Gráfico XY** (`XY Plot`). Conecta la salida de tiempo del osciloscopio a **X** y el trazo de voltaje a **Y**.
5. Haz clic derecho en el bloque **Gráfico XY** y selecciona **Fijar en Dashboard** (`Pin to Dashboard`).
6. Presiona `D` en tu teclado (o haz clic en **Dashboard** en la barra superior) para abrir el panel del operador.
7. Haz clic en **Ejecutar Blueprint** (▶️ o `Ctrl+R`).
8. **Verificación**: ComfyLAB iniciará automáticamente el servidor de simulación en segundo plano. El Dashboard mostrará de inmediato la forma de onda capturada. ¡También puedes abrir el ejemplo **Bode Diagram Virtual** desde **Menú Archivo > Cargar Ejemplo > Bode_Diagram_Virtual.json** para observar un barrido de frecuencia completo con diagramas de Bode!

<div style="page-break-before: always; break-before: page;"></div>

---

## 7. ComfyLAB Store y Gestión de Paquetes

La **ComfyLAB Store** es un repositorio modular integrado diseñado para mantener la instalación base de ComfyLAB ligera, portátil y de inicio ultra rápido, brindando acceso a pedido a controladores de hardware comercial, clústeres especializados y flujos completos de experimentos automatizados.

### 7.1 Conceptos Clave de la Store

* **Arquitectura Desacoplada**: La instalación base incluye bloques genéricos de comunicación (VISA/Serial) y simuladores virtuales. Los controladores dedicados para modelos de hardware físico (Keysight, Tektronix, Agilent, Minipa, Thorlabs, Keithley, CAEN, etc.) y los workflows de laboratorio residen en el repositorio oficial de la Store ([gateeit-ifgw/comfylab-store](https://github.com/gateeit-ifgw/comfylab-store)).
* **Categorías de Paquetes**:
  * **Instrumentos (Instruments)**: Drivers de hardware comercial con comandos, consultas y configuraciones predefinidas.
  * **Clústeres (Clusters)**: Sub-lienzos modulares y empaquetados con pines de entrada y salida estandarizados.
  * **Blueprints**: Workflows de experimentos automatizados listos para usar (como *Respuesta en Frecuencia - Diagrama de Bode* o *Espectroscopía VUV Horiba*).
  * **Bloques (Blocks)**: Bloques reutilizables para análisis matemático, procesamiento de señales o control.
* **Resolución Topológica de Dependencias**: Los blueprints y clústeres declaran sus dependencias explícitamente. Al instalar un workflow de laboratorio, ComfyLAB identifica, descarga y registra automáticamente todos los clústeres y controladores de instrumentos requeridos en estricto orden de dependencias.
* **Detección Automática de Bloques Faltantes**: Si abres un blueprint compartido que utiliza bloques o clústeres que aún no tienes instalados en tu computadora, ComfyLAB muestra un aviso con un botón de instalación en 1 clic para descargar los paquetes necesarios directamente desde la Store.
* **Suscripciones y Sincronización Automática**: En la pestaña **Subscriptions**, puedes suscribirte a *All Instruments* o a fabricantes específicos presentes en tu laboratorio. ComfyLAB busca nuevos drivers y actualizaciones al iniciar la aplicación, o puedes pulsar **Sync Now** en cualquier momento.
* **Seguridad Criptográfica**: Cada paquete y el catálogo central están firmados digitalmente con criptografía Ed25519 y verificados mediante hashes SHA-256 para garantizar autenticidad y seguridad del código.

---

### 7.2 Tutorial 7: Instalando Instrumentos y Blueprints desde la Store

**Objetivo**: Abrir la ComfyLAB Store, instalar un driver o blueprint con resolución automática de dependencias y configurar suscripciones.

#### Instrucciones Paso a Paso:
1. **Abrir la Store**: Haz clic en el botón **🛍️ Store** situado en el centro de la Barra Superior (o selecciónalo desde el menú hamburguesa). Una insignia verde (badge) te avisará cuando haya actualizaciones o paquetes nuevos disponibles en tus suscripciones.
2. **Explorar y Filtrar**: Usa la barra de búsqueda o las pestañas de categoría (**All**, **Instruments**, **Clusters**, **Blueprints**) para encontrar el equipo o experimento que necesitas.
3. **Instalación en 1 Clic**: Haz clic en **Install** en el paquete deseado. Si tiene dependencias (por ejemplo, un blueprint que necesita el driver del osciloscopio y del generador), ComfyLAB mostrará la lista y las instalará en orden.
4. **Disponibilidad Inmediata**: Los nuevos bloques aparecen de inmediato en la paleta de la barra lateral izquierda, listos para arrastrar al lienzo, y los blueprints quedan disponibles en **Menú Archivo > Cargar Ejemplo**.
5. **Gestión de Actualizaciones y Desinstalación**: En la pestaña **Installed**, puedes comprobar las versiones instaladas, actualizar a versiones más recientes o desinstalar paquetes con seguridad.
6. **Actualizaciones Automáticas**: En la pestaña **Subscriptions**, activa los fabricantes de tu laboratorio (ej. *Keysight* o *Tektronix*) para recibir drivers nuevos automáticamente cada vez que inicies ComfyLAB.

<div style="page-break-before: always; break-before: page;"></div>

---

## 8. Guía Rápida de Atajos y Referencia de Teclado

### Atajos de Teclado

| Acción | Atajo | Descripción |
| :--- | :--- | :--- |
| **Alternar Dashboard** | `D` | Abrir o cerrar el cockpit del Dashboard del Operador |
| **Ejecutar / Pausar / Reanudar** | `Ctrl + R` | Iniciar la ejecución del blueprint, pausar o reanudar |
| **Detener Ejecución** | `Ctrl + Shift + R` | Interrumpir la ejecución de inmediato y ejecutar rutinas de seguridad |
| **Duplicar Bloque(s)** | `Ctrl + D` | Clonar bloques seleccionados manteniendo su configuración |
| **Herramienta Selección** | `1` | Modo estándar: seleccionar, mover bloques y conectar pines |
| **Herramienta Pan** | `2` | Mover la vista del lienzo sin arrastrar bloques |
| **Herramienta Cortar Cable** | `3` | Pasar la cuchilla para borrar cables rápidamente |
| **Herramienta Pizarra** | `4` | Alternar la capa de dibujo para notas, figuras y anotaciones |
| **Desplazar Lienzo** | `Espacio + Arrastrar` | Mantener presionada la barra espaciadora y arrastrar el fondo |
| **Zoom en Lienzo** | `Rueda del Ratón` | Girar la rueda para acercar o alejar la vista |
| **Guardar Blueprint** | `Ctrl + S` | Guardar el plano actual en el JSON del workspace (`Ctrl + Shift + S` para Guardar Como) |
| **Abrir Blueprint** | `Ctrl + O` | Abrir la ventana de diálogo para cargar un blueprint |
| **Deshacer / Rehacer** | `Ctrl + Z` / `Ctrl + Y` | Deshacer o rehacer acciones recientes en el lienzo |
| **Copiar / Pegar** | `Ctrl + C` / `Ctrl + V` | Copiar y pegar bloques seleccionados |
| **Eliminar** | `Delete` / `Backspace` | Eliminar los bloques o cables seleccionados |
| **Navegar en Clúster** | `Doble Clic` | Entrar al sub-lienzo interno del bloque Clúster |
---
*ComfyLAB se distribuye bajo la Licencia Pública General GNU v3.0 (GPLv3). Desarrollado por Paulo Felipe Jarschel, GATE/EIT, IFGW, Unicamp.*

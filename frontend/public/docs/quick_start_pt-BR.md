# ComfyLAB: Guia de Início Rápido e Visão Geral Completa
*Comfortable Lab Automation Blocks — Manual do Usuário, Visão Geral do Software e Referência de Tutoriais Práticos*

---

## 1. Introdução e Filosofia

### 1.1 O que é o ComfyLAB?
O **ComfyLAB** (**Comf**ortable **L**ab **A**utomation **B**locks) é uma plataforma de programação visual de código aberto, projetada especificamente para automação de experimentos científicos, teste e medição, aquisição de dados (DAQ) e visualização em tempo real.

Em laboratórios de pesquisa modernos, sistemas de medição automatizados frequentemente exigem comunicação com diversos equipamentos (osciloscópios, fontes de alimentação, multímetros, geradores de funções, sensores customizados) por meio de múltiplos protocolos (VISA, SCPI, Serial RS-232/RS-485, Ethernet, bibliotecas nativas C/C++ DLLs). Escrever código de automação tradicional baseado em scripts geralmente resulta em códigos repetitivos (boilerplate) para gerenciamento de loops, segurança entre threads, tratamento de exceções, parsing de dados e renderização de interfaces gráficas.

O ComfyLAB resolve esse desafio fornecendo uma interface gráfica limpa e modular, onde os usuários arrastam **Blocos** funcionais para uma tela digital, os conectam através de **Fios** visuais e organizam resultados em um **Dashboard** interativo imediato.

---

### 1.2 Arquitetura Dupla: Interface Web UI + Motor de Execução Python
O ComfyLAB opera em um modelo cliente-servidor desacoplado:
<div style="page-break-before: always; break-before: page;"></div>

```
┌──────────────────────────────────────────────────────────┐
│                   INTERFACE WEB (FRONT-END)              │
│ - Canvas Web (React + XY Flow)                           │
│ - Posicionamento de Blocos e Conexão Drag-and-Drop       │
│ - Cockpit Dedicado de Dashboard do Operador (Atalho: D)  │
│ - Gráficos Interativos 2D e 3D e Displays em Tempo Real  │
│ - Camada de Lousa Interativa (Whiteboard) e Anotações    │
└────────────────────────────┬─────────────────────────────┘
                             │ WebSocket / API HTTP
┌────────────────────────────▼─────────────────────────────┐
│            SERVIDOR DE EXECUÇÃO (BACK-END)               │
│ - Motor Core Python + API (FastAPI)                      │
│ - Executor de Máquina de Estados Híbrida Push/Pull       │
│ - Drivers Hardware VISA e Gerenciador Serial Lock        │
│ - Servidor de Instrumentos Virtuais Embutidos (SCPI)     │
│ - Processamento de Sinais NumPy/SciPy e FFT              │
│ - Scripting Multilinguagem e Invocação DLL / SO          │
└──────────────────────────────────────────────────────────┘
```

* **Canvas Front-End & Dashboard**: Executa em navegadores web modernos (ou em builds de aplicativo desktop de arquivo único). Proporciona manipulação gráfica fluida, ferramentas de auto-layout, zoom/pan interativo em gráficos, anotações virtuais em lousa e um **Painel de Dashboard do Operador** que exibe cards fixados, controles e monitores em uma interface limpa de sala de controle.
* **Servidor Back-End**: Alimentado por Python e FastAPI. Gerencia bloqueios de hardware em tempo real, consultas VISA/SCPI, cálculos matriciais pesados, execução multi-thread, persistência de arquivos, ambientes virtuais Python e um processo de servidor em segundo plano para **Instrumentos Virtuais**.

---

### 1.3 Segurança e Proteção Integradas

* **Proteção de Instrumentos e Rotinas de Segurança (Teardown)**: Equipamentos físicos de laboratório (lasers, fontes de alta tensão, fontes de sinal RF) exigem gerenciamento de segurança rigoroso. Se uma execução de medição encontrar um erro, for interrompida manualmente ou sofrer perda de conexão, o ComfyLAB executa automaticamente rotinas de desligamento seguro (shutdown hooks) para desativar saídas ativas e retornar os instrumentos a estados seguros.
* **Verificação de Segurança de Blueprints**: Ao abrir blueprints de fontes externas, o ComfyLAB realiza verificações de segurança para evitar a execução não autorizada de scripts, garantindo controle total e confirmação rápida ao usuário antes de rodar códigos customizados.
* **Acesso Remoto Seguro**: O ComfyLAB suporta operação remota segura via rede com autenticação por token, permitindo que pesquisadores monitorem e controlem com segurança experimentos rodando em computadores do laboratório a partir de estações de trabalho remotas.
* **Verificador Integrado de Versões e Atualizações**: Gerenciador de atualizações embutido na janela *Sobre* (About), que verifica automaticamente novas versões no PyPI / GitHub, exibe notas de versão e permite atualização simplificada.

<div style="page-break-before: always; break-before: page;"></div>

---

## 2. Capacidades e Flexibilidade: O que Pode (ou Não) Ser Feito

O ComfyLAB foi desenvolvido do zero para oferecer extrema flexibilidade, sem restringir usuários avançados a modelos de interface rígidos.

### 2.1 O que Pode Ser Feito com o ComfyLAB

| Área de Recurso | Capacidades e Extensibilidade |
| :--- | :--- |
| **Controle de Hardware Físico** | Suporte completo para **VISA** (GPIB, USB TMC, Ethernet/LXI, Serial RS-232/RS-485) e comandos padrão **SCPI**. Blocos de driver integrados para osciloscópios comerciais populares, multímetros, fontes de alimentação, geradores de funções e espectrômetros Horiba. |
| **Instrumentos Virtuais Embutidos** | Instrumentos de teste e medição simulados por software diretamente na plataforma! Inclui **Osciloscópio Virtual** (`virt_osc`) e **Gerador de Funções Virtual** (`virt_siggen`) acoplados a uma simulação de **Circuito RC**, permitindo testes completos e ensino sem depender de hardware físico. |
| **Painel de Dashboard do Operador** | Visualização dedicada de **Dashboard** (atalho `D`). Fixe qualquer bloco, parâmetro de controle ou widget de visualização em um cockpit de operação limpo. Reordene e redimensione cards para criar painéis prontos para apresentações e controle de bancada. |
| **Temporização e Monitoramento de Progresso** | Acompanhamento visual da execução com **Countdown Wait** (relógio regressivo digital, barra de progresso em esgotamento e botão de avanço imediato), widgets de **Barra de Progresso** (0–100%), mostrador de **Tempo Restante Estimado (ETR)** e blocos de loop inteligentes. |
| **Suíte Completa de Gráficos Científicos** | Plotagem interativa 2D e 3D em tempo real: **Gráfico XY / Linhas** (traço único/múltiplo, log/linear), **Gráfico Dual-Y** (dois eixos Y independentes), **Gráfico de Barras**, **Box Plot** (distribuição estatística e outliers), **Histograma**, **Superfície 3D & Dispersão 3D**, **Gráfico Polar**, **Cascata Espectral (Waterfall)** e Matrizes 2D Heatmap. |
| **Invocação de Bibliotecas Nativas** | Chamada direta de bibliotecas em C/C++ (`.dll` no Windows, `.so` no Linux/macOS) através de um **Editor de Assinaturas** interativo, sem escrever Ctypes em Python. |
| **Scripts Customizados Multilinguagem** | Criação de **Blocos de Script** em 9 linguagens: Python, Rust, JavaScript, TypeScript, Julia, R, Lua, Octave e Wolfram. Acesso automático à variável de ambiente `COMFYLAB_WORKSPACE` para leitura e gravação transparente de arquivos no diretório do projeto. |
| **Acesso ao Ecossistema Python** | Conexão de blocos de script a ambientes virtuais Python (`.venv`), para acesso a bibliotecas como `scipy`, `numpy`, `pandas`, `opencv`, `scikit-learn`, `matplotlib` e pacotes PyPI. |
| **Publicação de Blocos e Pacotes (.cfy)** | Publicação de blocos de script diretamente na paleta da barra lateral ou empacotamento de fluxos completos (blueprints, scripts e arquivos) em pacotes redistribuíveis `.cfy`. |
| **Processamento Avançado de Sinais e Matemática** | Operações matriciais NumPy, análise espectral FFT, ajuste de curvas (Gaussiana, Exponencial, Polinomial, Não-linear customizada), filtragem (passa-baixas, passa-altas, passa-faixa), remoção de tendência (detrend) e detecção de picos. |
| **Sub-Canvases Modulares (Clusters)** | Agrupamento de sub-grafos complexos em **Blocos de Cluster** com pinos de entrada e saída dinâmicos para manter diagramas de blueprint limpos e hierárquicos. |
| **Camada de Lousa Interativa (Whiteboard)** | Adição de notas, texto formatado, formas geométricas, setas e desenhos livres diretamente sobre o canvas para apresentação e documentação. Uso de formas para agrupar blocos visualmente dentro de retângulos. |

---

### 2.2 Limitações Realistas: O que Não Pode (ou Não Deve) Ser Feito

Embora o ComfyLAB suporte quase qualquer tarefa de medição científica, automação e processamento de dados, é importante compreender seus limites de aplicação:

* **Determinismo de Tempo Real Estrito em Microsegundos**: O ComfyLAB executa sobre sistemas operacionais convencionais (Windows/Linux/macOS) através de back-ends em Python/FastAPI. Ele é projetado para loops de automação na escala de milissegundos a sub-segundos, amostragem de sensores e controle de instrumentos. Ele **não** se destina a lógicas de hardware bare-metal em FPGA ou loops de controle determinísticos de microsegundos em tempo real (ex.: comutação PWM de drivers de motor a 100 kHz). Para essas tarefas, placas FPGA ou microcontroladores dedicados com RTOS devem gerenciar a temporização de baixo nível, enquanto o ComfyLAB se comunica com eles via serial/USB para controle de alto nível, armazenamento em buffer e plotagem.

> **Resumo**: Fora o determinismo de hardware em microsegundos via FPGA, **praticamente qualquer fluxo de medição científica, automação de laboratório, registro de dados, análise de sinais ou plotagem pode ser construído no ComfyLAB**.

<div style="page-break-before: always; break-before: page;"></div>

---

## 3. Comparação com Paradigmas Alternativos

Compreender como o ComfyLAB se compara às ferramentas tradicionais de laboratório destaca por que ele é uma escolha vantajosa tanto para o ensino quanto para a pesquisa.

| Recurso / Aspecto | Scripts Python Puros (PyVISA, Matplotlib) | National Instruments LabVIEW | MATLAB / Simulink | **ComfyLAB** |
| :--- | :--- | :--- | :--- | :--- |
| **Licenciamento e Custo** | Gratuito e Código Aberto | Licenciamento Comercial Elevado | Licenciamento Comercial Elevado | **Gratuito e Código Aberto (GPLv3)** |
| **Paradigma de Programação** | Código Baseado em Texto | Código Gráfico Proprietário G | Diagrama de Blocos Gráfico / Texto | **Diagramas de Blocos Web + Código Poliglota** |
| **Curva de Aprendizado** | Alta (Exige fluência em programação) | Média (Convenções complexas da linguagem G) | Média (Exige sintaxe e toolboxes) | **Baixa (Canvas intuitivo drag-and-drop)** |
| **Configuração de GUI e Gráficos** | Manual (PyQt, Tkinter, Matplotlib) | Painel Frontal Integrado | Janelas de Figura Integradas | **Plotagem 2D/3D, Polar, Cascata e Dashboard Instantâneos** |
| **Simulação Offline** | Requer bibliotecas mock manuais | Simulação de software básica | Modelagem física Simulink | **Osciloscópio, Gerador e Circuito SCPI Virtuais Embutidos** |
| **Formato de Arquivo e Versionamento** | Texto puro `.py` (Amigável ao Git) | Binário Proprietário `.vi` (Difícil diff no Git) | `.m` / Binário Proprietário `.slx` | **Blueprints JSON Limpos (Amigáveis ao Git)** |
| **Extensão com Código Customizado** | Nativa | Nós de Chamada Complexos C/Python | Funções S / Código MATLAB | **Blocos de Script Poliglotas (Python, C/C++, Rust, etc.)** |
| **Arquitetura** | Script single-thread / threads manuais | Aplicação Desktop Monolítica | Ambiente Desktop Pesado | **Interface Web Desacoplada + Servidor FastAPI** |
| **Bloqueio de Hardware (Locking)** | Exige implementação manual de lock | Drivers Integrados VISA / DAQmx | VISA / Instrument Control Toolbox | **Gerenciador de Lock VISA Assíncrono Automático** |

### Principais Conclusões:
1. **Vs. Python Puro**: O Python é extremamente poderoso, mas criar interfaces de usuário, gráficos interativos em tempo real, loops de estado de hardware e fluxos visuais exige centenas de linhas de código repetitivo. O ComfyLAB mantém todo o poder analítico do Python, fornecendo uma interface visual imediata e cockpit de operação.
2. **Vs. LabVIEW**: O LabVIEW é amplamente utilizado, mas sofre com custos elevados de licença comercial, arquivos binários proprietários que dificultam o controle de versão e bloqueio do fornecedor (lock-in). O ComfyLAB oferece uma alternativa moderna e open-source com blueprints em JSON, instrumentos virtuais embutidos e integração nativa com navegadores web.
3. **Vs. MATLAB**: O MATLAB se destaca em cálculos matriciais, mas possui custos de licença elevados. O ComfyLAB utiliza back-ends gratuitos e de código aberto baseados em NumPy/SciPy.

<div style="page-break-before: always; break-before: page;"></div>

---

## 4. Layout da Interface e Conceitos Fundamentais

### 4.1 Visão Geral do Layout da Interface

A interface do usuário do ComfyLAB é composta por três zonas funcionais principais cercadas por controles superiores:

```
┌──────────────────────────────────────────────────────────────┐
│ BARRA SUPERIOR: [🟰][⚙️] | [▶ Rodar/⏸ Pausa] [🛑 Parar] | [📊 Dash] │
├────────────────┬──────────────────────────────┬──────────────┤
│ BARRA LATERAL  │ ÁREA PRINCIPAL / DASHBOARD   │ INSPETOR     │
│ (Paleta Blocos)│                              │ (Valores)    │
│                │  ┌───────┐   Fio Execução    │              │
│ Buscar...      │  │ Entry │▶───┐              │ Entradas     │
│ Controle Fluxo │  └───────┘    │              │ Dados ao Vivo│
│ Matemática     │            ┌──▼────────────┐ │ Logs Console │
│ VISA / Virtual │ Fio Dados  │ Bloco Math    │ │              │
│ Instrumentos   │ ──────────▶└───────────────┘ │              │
│ Visualização   │                              │              │
│                │ [Minimap]        [Tools 1-4] │              │
└────────────────┴──────────────────────────────┴──────────────┘
```

#### Descrição Detalhada da Interface:
* **Barra de Ferramentas Superior**: Controles para executar (▶️ / `Ctrl+R`), pausar (⏸️) e parar (🛑 / `Ctrl+Shift+R`) blueprints, abrir o **Dashboard do Operador** (📊 / `D`), acessar a **ComfyLAB Store** (🛍️), criar/salvar arquivos de workspace (`Ctrl+S`), alternar temas de cores e configurar opções globais do VISA e diagnósticos.
* **Barra Lateral (Esquerda)**: Paleta pesquisável contendo todos os blocos nativos disponíveis, blocos customizados publicados, blocos de instrumentos virtuais e nós de script categorizados por domínio.
* **Canvas Principal (Centro)**: Área de trabalho visual infinita com zoom e pan onde você arrasta, posiciona e conecta os blocos funcionais.
* **Inspetor de Blocos (Direita)**: Painel de detalhes contextual que se abre ao selecionar um bloco. Exibe valores de pinos ao vivo, parâmetros do bloco, documentação resumida, notas e logs de console de execução.
* **Barra de Abas e Breadcrumbs**: Navegação entre múltiplos arquivos de blueprint abertos e detalhamento (drill down) em clusters de sub-canvas.

<div style="page-break-before: always; break-before: page;"></div>
---

### 4.2 Pinos e Conexões: Fluxo de Execução vs. Valores de Dados

As conexões entre blocos no ComfyLAB são estritamente divididas em duas categorias distintas:

```
  Saída Exec  ▶══════════════════════════════▶ Entrada Exec
              (Linha Violeta: Controla QUANDO os blocos rodam)

  Saída Dados ●──────────────────────────────● Entrada Dados
              (Linha Sólida: Transfere VALORES sob demanda)
```

1. **Pinos de Execução (Fluxo)**:
   * Representados por **conectores em forma de seta** e interligados por **linhas violetas (🟪)**.
   * Ditam o **sequenciamento temporal e fluxo de controle** (quando as etapas executam, loops repetem ou ramificações são acionadas).

2. **Pinos de Dados (Valores)**:
   * Representados por **pinos circulares coloridos** e interligados por **linhas coloridas sólidas**.
   * Transportam **valores** (números, strings de texto, vetores NumPy, dicionários, handles de hardware).
   * São avaliados de forma preguiçosa (lazy evaluation) sob demanda quando um bloco de execução solicita dados de entrada.

#### Referência de Cores dos Pinos de Dados:
* 🟧 **Número (Laranja)**: Valores numéricos escalares inteiros ou de ponto flutuante.
* 🟩 **Booleano (Verde)**: Flags lógicas `True` (Verdadeiro) ou `False` (Falso).
* 🟪 **String (Rosa)**: Textos, caracteres formatados ou comandos SCPI.
* 🟨 **Array (Amarelo)**: Vetores ou matrizes numéricas NumPy 1D/2D de alto desempenho.
* 🟦 **Lista (Ciano)**: Coleções ordenadas de elementos.
* 🟫 **Dicionário (Marrom)**: Mapeamentos de parâmetros chave-valor.

---

### 4.3 Lógica de Execução e Cadeias Independentes
* **Gatilho de Execução**: Clicar em **Run Blueprint** (▶️ ou `Ctrl+R`) inicia a execução nos blocos de entrada (blocos sem conexões de execução de entrada) e segue os fios de execução fluxo abaixo.
* **Cadeias de Execução Independentes**: Se o canvas contiver grupos de blocos separados e não conectados entre si, o ComfyLAB os trata automaticamente como cadeias de execução paralelas, permitindo que loops de aquisição independentes rodem concorrentemente.
* **Blocos de Controle de Fluxo e Temporização**:
  * **For Loop**: Executa um sub-loop por uma quantidade fixa de iterações, emitindo o índice atual, porcentagem de conclusão (`%`) e estimativa de tempo restante (`ETR`).
  * **For Each Loop**: Itera sobre cada item em uma lista ou array, fornecendo saídas de item, índice, porcentagem e tempo restante (ETR).
  * **While Loop**: Executa continuamente um sub-loop enquanto a condição Booleana do pino permanecer `True`.
  * **If / Else Branch**: Direciona o fluxo de execução para uma saída `True` ou `False` com base em uma condição.
  * **Delay / Sleep**: Pausa o fluxo de execução por uma duração especificada (ms ou segundos).
  * **Countdown Wait**: Pausa a execução com relógio digital regressivo ao vivo, barra de progresso em esgotamento e botão de clique para **Pular Espera**.
  * **Barra de Progresso**: Widget visual dedicado para acompanhamento de progresso de 0% a 100%.
  * **Relógio ETR**: Mostrador digital estilo sala de controle que formata o tempo restante estimado (`HH:MM:SS` ou `MM:SS`).
  * **Medidor de Tempo (Measure Time)**: Mede com precisão o tempo decorrido de relógio (wall-clock) entre pulsos de execução.

---

### 4.4 Recursos Avançados

* **Painel de Dashboard e Cards Fixados (📊 / `D`)**: O Dashboard proporciona um cockpit de operação limpo e sem distrações para conduzir experimentos, apresentar resultados ou realizar aulas práticas sem a complexidade visual do diagrama de fios.
  * **Fixando Blocos no Dashboard**: Qualquer bloco ou pino pode ser fixado no Dashboard. Basta clicar com o botão direito no bloco e escolher **Pin to Dashboard**, clicar no ícone de alfinete no cabeçalho do Inspetor de Blocos ou usar o botão correspondente nos widgets suportados.
  * **Organização Automática**: Controles e entradas numéricas são reunidos em **Cards de Controle** interativos, enquanto gráficos, medidores e temporizadores formam **Cards de Monitoramento**.
  * **Personalização de Layout**: Reordene cards verticalmente, arraste os cantos dos gráficos para redimensioná-los ou clique no ícone de salto para navegar instantaneamente até o bloco no canvas.
  * **Visão Maximizada**: Maximize o painel do dashboard para ocupar todo o workspace em um painel de bancada em tela cheia.
* **Blocos Persistentes (📌)**: Por padrão, os estados dos blocos são reiniciados a cada execução. Marcar um bloco como **Persistente** preserva seu estado interno e handles de hardware (ex.: conexões VISA ativas, portas seriais abertas ou médias móveis) entre múltiplas execuções do blueprint.
* **Desativação de Blocos (🚫)**: Clicar com o botão direito em um bloco para desativá-lo o deixa opaco no canvas. Blocos desativados são ignorados durante a execução, repassando dados de forma limpa sem executar código—ideal para testar fluxos sem hardware físico.
* **Clusters (Sub-canvases 📦)**: Agrupamento de arranjos complexos de blocos em um único bloco customizado. Dar um duplo clique em um bloco de cluster abre um sub-canvas isolado, com breadcrumbs na barra superior para navegação.
* **Modo Lousa / Whiteboard (🎨)**: Clique no ícone de ferramenta ou pressione o atalho `4` para alternar o modo de desenho, permitindo adicionar notas adesivas, caixas de texto e formas geométricas diretamente sobre o canvas.
* **ComfyLAB Store e Assinaturas (🛍️)**: Gerenciador integrado de pacotes que mantém a distribuição central leve e portátil, oferecendo acesso modular a drivers de equipamentos comerciais, clusters especializados e blueprints completos de experimentos. Inclui instalação em 1 clique, resolução automática de dependências e assinaturas de fabricantes com sincronização na inicialização.

<div style="page-break-before: always; break-before: page;"></div>

---

## 5. Resumo das Categorias de Blocos Nativos

| Categoria | Descrição e Blocos Comuns |
| :--- | :--- |
| 🔄 **Controle de Fluxo e Tempo** | For Loop, For Each Loop, While Loop, Ramificação If/Else, Delay/Sleep, Countdown Wait, Medidor de Tempo (Measure Time), Parar Execução. |
| 🔢 **Matemática e Lógica** | Adição, Subtração, Multiplicação, Divisão, Evaluator de Fórmulas, Seno/Cosseno, Trigonometria, Exponencial, Logaritmo, Comparações (`>`, `<`, `==`), Lógica AND, OR, NOT. |
| 📝 **Dados e Strings** | Concatenação de Strings, Formatador de Texto, Busca Regex, Divisor de Texto, Construtor de Listas, Indexador de Listas, Construtor de Dicionários, Obter Chave-Valor. |
| 📊 **Arrays e Sinais** | Criar Array, Linspace/Range, Fatiamento de Array (Slicing), Espectro de Potência FFT, Filtros Passa-Baixas/Passa-Faixa, Detrend, Estatísticas (Média, Desvio Padrão, Mín, Máx), Detector de Picos, Ajuste de Curvas (Gaussiana, Exponencial, Polinomial, Customizada). |
| 💾 **Entrada/Saída de Arquivos** | Leitura/Escrita de arquivos CSV, JSON, armazenamento Parquet, Leitura/Escrita de Texto Puro, Carregador e Salvador de Imagens. |
| 📡 **VISA e Hardware Físico** | Abrir Recurso VISA, Escrita SCPI, Leitura SCPI, Consulta SCPI (Query), Fechar VISA, Abrir/Ler/Escrever Porta Serial, Descoberta Automática de Instrumentos. |
| 🖥️ **Instrumentos Virtuais** | **VirtOsc** (Conexão, Base de Tempo, Canais 1 e 2, Trigger, Estado, Aquisição de Traço), **VirtSigGen** (Conexão, Onda Senoidal/Quadrada/Triangular, Varredura Chirp, Nível de Saída), Circuito RC Simulado. |
| 🔬 **Drivers Modulares de Instrumentos** | Drivers modulares instalados sob demanda via ComfyLAB Store: Osciloscópios (Tektronix, Keysight), Multímetros (HP/Agilent 34401A), Fontes DC, Espectrômetros Horiba Jobin Yvon, Digitalizadores CAEN, Motores Thorlabs, Minipa, etc. |
| 📈 **Exibição, Gráficos e UI** | **Gráfico XY / Linhas** (traço único/múltiplo, log/linear), **Gráfico Dual-Y**, **Gráfico de Barras**, **Box Plot**, **Histograma**, **Superfície 3D & Dispersão 3D**, **Gráfico Polar**, **Cascata Espectral (Waterfall)**, Matriz 2D Heatmap, Tabela, Gauge, LED, **Barra de Progresso**, **Relógio ETR**, **Relógio Regressivo**. |
| ⚙️ **Nativo e Scripting** | Invocação de Biblioteca Nativa (DLL/SO) com Editor de Assinaturas, Nós de Script Poliglotas (Python, JS/TS, Julia, Rust, Lua, Octave, R, Wolfram) com suporte à variável `COMFYLAB_WORKSPACE`. |

<div style="page-break-before: always; break-before: page;"></div>

---

## 6. Tutoriais Práticos de Iniciação

Utilize estes exercícios passo a passo rápidos para se familiarizar com o ComfyLAB.

<div style="page-break-before: always; break-before: page;"></div>

---

### Tutorial 1: Pipeline Matemático e Inspeção ao Vivo
**Objetivo**: Criar dois números, multiplicá-los, aplicar uma fórmula matemática e inspecionar o resultado no Inspetor de Blocos.

```
┌──────────────┐
│ Número (5.0) ├──┐   ┌───────────┐   ┌─────────────┐
│ Saída Dados  │  ├──▶│ Multiplicar├──▶│ Fórmula     ├──► Saída
└──────────────┘  │   └───────────┘   │ "x^2 + 10"  │
┌──────────────┐  │                   └─────────────┘
│ Número (3.0) ├──┘
│ Saída Dados  │
└──────────────┘
```

#### Instruções Passo a Passo:
1. Abra o ComfyLAB e crie um novo workspace/blueprint.
2. Na **Barra Lateral** à esquerda, busque por `Number` e arraste **dois** blocos de Número para o canvas.
3. Defina o valor do primeiro bloco de Número para `5.0` e o do segundo para `3.0`.
4. Arraste um bloco **Multiply** (da categoria *Matemática e Lógica*) para o canvas.
5. Conecte o pino de saída de dados do Número 1 à Entrada A do bloco Multiply, e o Número 2 à Entrada B.
6. Arraste um bloco **Formula** para o canvas. Defina o parâmetro da equação para `x^2 + 10`.
7. Conecte o pino de saída do bloco Multiply (`15.0`) à entrada `x` do bloco Formula.
8. Clique em **Run Blueprint** (▶️ ou `Ctrl+R`) na barra de ferramentas superior.
9. Clique no bloco **Formula** para abrir o **Inspetor de Blocos** no painel da direita.
10. **Verificação**: No Inspetor de Blocos, verifique o valor de saída ao vivo do pino. Ele deve avaliar para `(15)^2 + 10 = 235.0`.

<div style="page-break-before: always; break-before: page;"></div>

---

### Tutorial 2: Geração de Sinal Sintético e Plotagem ao Vivo
**Objetivo**: Gerar um array de onda senoidal ruidosa, calcular seu espectro de potência FFT e exibi-lo em um plotter interativo.

```
┌────────────────────┐     ┌────────────────────┐
│ Linspace (0 a 10s) ├────▶│ Gerador Onda Seno  ├─┐
└────────────────────┘     └────────────────────┘ │
                                                  ▼
┌────────────────────┐     ┌────────────────────┐ │
│ Gráfico Interativo │◀────┤ Sinal + Ruído      │◀┘
└────────────────────┘     └─────────┬──────────┘
                                     │
                                     ▼
                           ┌────────────────────┐
                           │ Espectro FFT       │
                           └────────────────────┘
```

#### Instruções Passo a Passo:
1. Busque por `Linspace` na Barra Lateral. Defina `Start = 0`, `Stop = 10`, `Points = 1000` para criar um vetor de tempo.
2. Busque por `Sine` (em *Matemática e Lógica* ou *Arrays*). Conecte a saída do Linspace à entrada de tempo do bloco Sine. Defina o parâmetro de frequência para `5.0 Hz`.
3. Adicione um bloco **Random Noise** e um bloco **Add** para corromper a onda senoidal com ruído branco (`Sinal + Ruído`).
4. Arraste um bloco **Interactive Plotter** para o canvas.
5. Conecte o array de tempo ao **Pino X** do Plotter e o array de sinal ruidoso ao **Pino Y**.
6. (Opcional) Conecte o sinal ruidoso a um bloco **FFT Spectrum** e conecte a saída da FFT a um segundo traço no Plotter.
7. Clique em **Run Blueprint** (▶️).
8. **Verificação**: O widget do Plotter no canvas exibirá imediatamente a onda senoidal ruidosa ao vivo. Use a roda do mouse sobre o gráfico para aproximar/afastar (zoom) e arraste para navegar pelos eixos!

<div style="page-break-before: always; break-before: page;"></div>

---

### Tutorial 3: Varredura Automatizada de Parâmetros e Registro em CSV
**Objetivo**: Usar um `For Loop` para simular a varredura da tensão de uma fonte de alimentação, calcular o consumo de corrente, exibir a curva ao vivo e salvar os dados em um arquivo CSV.

```
┌─────────────────────┐    ┌────────────────────┐
│ For Loop (0 a 50)   │▶──▶│ Escritor CSV       │
└──────────┬──────────┘    └────────────────────┘
           │ (Índice)
           ▼
┌─────────────────────┐
│ Tensão = Índice*0.1 │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ Corrente = V / R    ├─► Plotter ao Vivo
└─────────────────────┘
```

#### Instruções Passo a Passo:
1. Arraste um bloco **For Loop** para o canvas. 
2. Defina a contagem de iterações do `For Loop` para `50`. Observe que o bloco também disponibiliza pinos de porcentagem (`%`) e tempo estimado restante (`ETR`)!
3. Dentro do caminho de execução do loop, multiplique o pino `Iteration Index` por `0.1` usando um bloco **Multiply** para gerar uma varredura de tensão de `0.0 V` a `5.0 V`.
4. Divida a tensão por uma resistência constante (`R = 100 Ohms`) usando um bloco **Divide** para calcular a corrente `I`.
5. Conecte os valores de Tensão e Corrente a um bloco **CSV Writer**. Defina a opção de nome do arquivo para `sweep_results.csv`.
6. Conecte o pino de execução de saída do bloco CSV de volta à entrada de passo do loop para concluir a iteração.
7. Clique em **Run Blueprint** (▶️).
8. **Verificação**: Observe o loop executando passo a passo com as linhas de execução violetas animadas. Após a conclusão, abra a pasta do seu workspace ativo—você encontrará o arquivo `sweep_results.csv` preenchido com as 50 linhas de dados!

<div style="page-break-before: always; break-before: page;"></div>

---

### Tutorial 4: Criação e Publicação de um Bloco de Script Python Customizado
**Objetivo**: Criar um bloco de script Python customizado que filtra valores abaixo de um limiar, testá-lo e publicá-lo na paleta da barra lateral esquerda.

```
┌──────────────────────────────────────────────────┐
│ Bloco de Script Customizado (Python)             │
│ Entradas: data_in (Array), threshold (Número)    │
│ Saídas:   filtered_data (Array), count (Número)  │
├──────────────────────────────────────────────────┤
│ arr = np.array(inputs['data_in'])                │
│ result = arr[arr > inputs['threshold']]          │
│ outputs['filtered_data'] = result.tolist()       │
│ outputs['count'] = len(result)                   │
└──────────────────────────────────────────────────┘
```

#### Instruções Passo a Passo:
1. Arraste um bloco **Script Block** (da categoria *Scripting & Native*) para o canvas. Selecione **Python** como a linguagem.
2. No **Inspetor de Blocos**, clique em **Edit Pins**:
   * Adicionar Pino de Entrada: `data_in` (Tipo: Array)
   * Adicionar Pino de Entrada: `threshold` (Tipo: Number)
   * Adicionar Pino de Saída: `filtered_data` (Tipo: Array)
   * Adicionar Pino de Saída: `count_passed` (Tipo: Number)
3. Dê um duplo clique no Bloco de Script para abrir o editor de código integrado.
4. Digite o código Python mostrado acima. (Observe que `os.environ["COMFYLAB_WORKSPACE"]` está disponível caso seu script precise acessar arquivos do projeto!).
5. Conecte um array de amostra em `data_in` e defina `threshold = 2.5`.
6. Clique em **Run Blueprint** (▶️) e inspecione os pinos `filtered_data` e `count_passed` no Inspetor de Blocos.
7. Após verificar, clique em **Publish Block** no Inspetor de Blocos. Dê o nome de `Filtro Limiar`, escolha um ícone e atribua à categoria `Arrays`.
8. **Verificação**: Observe a sua **Barra Lateral** à esquerda. Seu novo bloco `Filtro Limiar` agora está permanentemente disponível para ser arrastado para qualquer canvas no seu workspace!

<div style="page-break-before: always; break-before: page;"></div>

---

### Tutorial 5: Interface de Hardware VISA (Consulta SCPI de Identificação)
**Objetivo**: Conectar a um instrumento físico ou simulado via VISA, enviar uma consulta SCPI `*IDN?` e exibir a resposta do modelo do instrumento.

```
┌───────────┐     ┌───────────┐     ┌───────────┐
│ Abrir VISA│▶───▶│Query SCPI │▶───▶│Fechar VISA│
│ Recurso   ├────▶│ "*IDN?"   ├────▶│ Handle    │
└───────────┘     └─────┬─────┘     └───────────┘
                        │ String de Resposta
                        ▼
                  [Inspetor de Blocos]
```

#### Instruções Passo a Passo:
1. Arraste um bloco **VISA Open** para o canvas. Defina o parâmetro String de Recurso para o endereço do seu instrumento (ex.: `TCPIP0::192.168.1.100::INSTR`, `GPIB0::14::INSTR` ou `COM3`).
2. Arraste um bloco **SCPI Query**. Conecte o `ExecOut` do VISA Open ao `ExecIn` do SCPI Query.
3. Conecte o pino de saída `VISA Handle` (pino ciano) do VISA Open à entrada `VISA Handle` do SCPI Query.
4. Defina o parâmetro de string de comando no SCPI Query para `*IDN?
`.
5. Arraste um bloco **VISA Close** e conecte a linha de execução e o handle VISA a ele para garantir a liberação limpa do recurso.
6. Clique em **Run Blueprint** (▶️).
7. **Verificação**: Clique no bloco **SCPI Query** e observe o Inspetor de Blocos. O pino de saída de string exibirá a identificação do fabricante (ex.: `HEWLETT-PACKARD,34401A,0,11-5-2` ou `KEYSIGHT TECHNOLOGIES,DSOX2002A,...`).
8. **Dica**: Você também pode aproveitar o bloco Gerenciador de Recursos VISA (VISA Resource Manager) para descobrir instrumentos conectados automaticamente!

<div style="page-break-before: always; break-before: page;"></div>

---

### Tutorial 6: Automação Offline com Instrumentos Virtuais Embutidos
**Objetivo**: Conectar aos instrumentos virtuais do ComfyLAB, configurar um gerador de sinais simulado, capturar a forma de onda com o osciloscópio virtual e monitorar os resultados no Dashboard sem precisar de hardware físico.

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ VirtSigGen Conn │▶───▶│ Config Wave     │▶───▶│ VirtOsc Connect │
│ (TCP Virtual)   ├────▶│ Freq: 1 kHz     │     │ (TCP Virtual)   │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Fixar no        │◀────┤ Widget Gráfico  │◀────┤ Adquirir Traço  │
│ Dashboard (D)   │     │ Tempo vs Volts  │     │ Dados Canal 1   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

#### Instruções Passo a Passo:
1. Na Barra Lateral, navegue até a categoria **Dispositivos > Virtual**.
2. Arraste um bloco **VirtSigGen Connect** e um bloco **VirtSigGen Config Wave**. Conecte-os para gerar uma onda senoidal de 1,0 kHz com 2,0 Vpp.
3. Arraste um bloco **VirtOsc Connect** e um bloco **VirtOsc Acquire**. Conecte as linhas de execução e os handles dos dispositivos.
4. Arraste um bloco **XY Plot**. Conecte a saída de tempo do osciloscópio em **X** e o traço de tensão em **Y**.
5. Clique com o botão direito no bloco **XY Plot** e selecione **Pin to Dashboard**.
6. Pressione `D` no teclado (ou clique no botão **Dashboard** na barra superior) para abrir o cockpit de operação.
7. Clique em **Run Blueprint** (▶️ ou `Ctrl+R`).
8. **Verificação**: O ComfyLAB inicializará automaticamente o servidor de simulação de instrumentos virtuais em segundo plano. O Dashboard exibirá imediatamente a forma de onda capturada em tempo real. Você também pode carregar o exemplo pronto **Bode Diagram Virtual** em **Menu Arquivo > Carregar Exemplo > Bode_Diagram_Virtual.json** para ver uma varredura completa de resposta em frequência com traçado de diagramas de Bode!

<div style="page-break-before: always; break-before: page;"></div>

---

## 7. ComfyLAB Store e Gerenciamento de Pacotes

A **ComfyLAB Store** é um ecossistema modular integrado projetado para manter a instalação base do ComfyLAB leve, portátil e de inicialização instantânea, disponibilizando sob demanda drivers de equipamentos comerciais, clusters de sub-canvas especializados e workflows de experimentos completos.

### 7.1 Conceitos Principais da Store

* **Arquitetura Desacoplada**: A instalação padrão inclui blocos genéricos de comunicação (VISA/Serial) e simuladores de instrumentos virtuais. Drivers dedicados a modelos físicos de fabricantes (Keysight, Tektronix, Agilent, Minipa, Thorlabs, Keithley, CAEN, etc.) e blueprints de bancada são distribuídos pelo repositório oficial da Store ([gateeit-ifgw/comfylab-store](https://github.com/gateeit-ifgw/comfylab-store)).
* **Categorias de Pacotes**:
  * **Instrumentos (Instruments)**: Drivers dedicados com comandos, consultas e tratamentos específicos de hardware comercial.
  * **Clusters**: Blocos compostos com sub-canvases pré-configurados e pinos de entrada/saída padronizados.
  * **Blueprints**: Workflows de experimentos automatizados prontos para uso (como o *Levantamento de Curva de Bode* ou *Espectroscopia VUV Horiba*).
  * **Blocos (Blocks)**: Blocos analíticos, matemáticos ou de controle reutilizáveis.
* **Resolução Topológica de Dependências**: Blueprints e clusters declaram dependências explicitamente. Ao instalar um blueprint de bancada, o ComfyLAB identifica, baixa e registra automaticamente todos os clusters e drivers de instrumentos necessários em ordem estrita de dependência.
* **Detecção Automática de Blocos Ausentes**: Se você abrir um blueprint compartilhado que contenha blocos ou clusters ainda não instalados no seu computador, o ComfyLAB exibe um aviso com botão de instalação em 1 clique para baixar os pacotes necessários diretamente da Store.
* **Assinaturas e Sincronização Automática**: Na aba **Subscriptions**, você pode assinar a categoria *All Instruments* ou fabricantes específicos presentes no seu laboratório. O ComfyLAB verifica novos drivers e atualizações na inicialização ou através do botão **Sync Now**.
* **Segurança Criptográfica**: Cada pacote e o catálogo central são assinados com chaves digitais Ed25519 e verificados por hashes SHA-256 para garantir integridade e procedência do código.

---

### 7.2 Tutorial 7: Instalando Instrumentos e Blueprints pela Store

**Objetivo**: Abrir a ComfyLAB Store, instalar um driver ou blueprint com resolução automática de dependências e gerenciar assinaturas.

#### Instruções Passo a Passo:
1. **Abrir a Store**: Clique no botão **🛍️ Store** no centro da Barra de Ferramentas Superior (ou no menu hambúrguer no canto superior esquerdo). Uma insígnia verde (badge) avisa quando há novas atualizações ou pacotes disponíveis nas suas assinaturas.
2. **Navegar e Filtrar**: Use a barra de busca ou as abas de categoria (**All**, **Instruments**, **Clusters**, **Blueprints**) para localizar o equipamento ou experimento desejado.
3. **Instalação em 1 Clique**: Clique em **Install** no pacote desejado. Se houver dependências (por exemplo, um blueprint que precisa do driver do osciloscópio e do gerador), o ComfyLAB exibirá a lista de pacotes e os instalará em ordem.
4. **Disponibilidade Imediata**: Os novos blocos aparecem instantaneamente na paleta da barra lateral esquerda, prontos para uso, e os blueprints ficam disponíveis em **Menu Arquivo > Carregar Exemplo**.
5. **Atualizações e Desinstalação**: Na aba **Installed**, consulte as versões instaladas, atualize para versões recentes ou desinstale pacotes com segurança.
6. **Atualizações Automáticas**: Na aba **Subscriptions**, ative os fabricantes do seu laboratório (ex.: *Keysight* ou *Tektronix*) para receber drivers novos automaticamente sempre que iniciar o ComfyLAB.

<div style="page-break-before: always; break-before: page;"></div>

---

## 8. Guia Rápido de Atalhos e Referência de Teclado

### Atalhos de Teclado

| Ação | Atalho | Descrição |
| :--- | :--- | :--- |
| **Alternar Dashboard** | `D` | Abrir ou fechar o Painel de Dashboard do Operador. |
| **Executar / Pausar / Retomar** | `Ctrl + R` | Iniciar a execução do blueprint, pausar ou retomar. |
| **Parar Execução** | `Ctrl + Shift + R` | Interromper a execução imediatamente e acionar rotinas de segurança. |
| **Duplicar Bloco(s)** | `Ctrl + D` | Duplicar os blocos selecionados preservando configurações. |
| **Ferramenta Seleção** | `1` | Modo padrão para selecionar, mover blocos e conectar pinos. |
| **Ferramenta Pan** | `2` | Mover a visualização do canvas sem arrastar blocos. |
| **Ferramenta Cortar Fio** | `3` | Passar a lâmina sobre os fios para excluí-los rapidamente. |
| **Ferramenta Lousa** | `4` | Alternar camada de desenho para notas, formas e anotações. |
| **Mover Canvas (Pan)** | `Espaço` + Arrastar | Segurar barra de espaço e arrastar fundo para navegar. |
| **Zoom no Canvas** | `Roda do Mouse` | Rolar para aproximar ou afastar a visualização. |
| **Salvar Blueprint** | `Ctrl + S` | Salvar o layout atual no arquivo JSON do workspace (`Ctrl + Shift + S` para Salvar Como). |
| **Abrir Blueprint** | `Ctrl + O` | Abrir caixa de diálogo para carregar blueprint. |
| **Desfazer / Refazer** | `Ctrl + Z` / `Ctrl + Y` | Desfazer ou refazer ações recentes no canvas. |
| **Copiar / Colar** | `Ctrl + C` / `Ctrl + V` | Copiar e colar blocos selecionados. |
| **Excluir Bloco / Fio** | `Delete` ou `Backspace` | Remover blocos ou fios selecionados do canvas. |
| **Navegação Sub-canvas** | `Duplo Clique no Cluster` | Entrar no sub-canvas de um Bloco de Cluster. |
---
*O ComfyLAB é disponibilizado sob a licença GNU General Public License v3.0 (GPLv3). Desenvolvido por Paulo Felipe Jarschel, GATE/EIT, IFGW, Unicamp.*

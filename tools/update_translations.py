#!/usr/bin/env python3
# Copyright (C) 2026 Paulo Felipe Jarschel
# Updates i18n translations for all store packages, clusters, manifests, and catalog.json,
# signs them with the master Ed25519 key, and verifies hashes.

import os
import sys
import json
import base64
import hashlib
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

KEY_PATH = Path("/home/pfjarschel/.comfylab/store_master_key.pem")
STORE_DIST_DIR = Path(__file__).resolve().parent.parent / "dist" / "comfylab-store"
CORE_CLUSTERS_DIR = Path(__file__).resolve().parent.parent / "comfylab" / "clusters"
USER_STORE_DIR = Path.home() / ".comfylab" / "store"

# Load Master Key
with open(KEY_PATH, "rb") as f:
    priv_key = serialization.load_pem_private_key(f.read(), password=None)
pub_hex = priv_key.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw
).hex()

print(f"[I18N Updater] Master Key Identity: {pub_hex}")

def sign_json_with_key(data: dict) -> dict:
    content = {k: v for k, v in data.items() if k not in ("signature", "creator_identity")}
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig_bytes = priv_key.sign(canonical)
    signed = dict(data)
    signed["creator_identity"] = pub_hex
    signed["signature"] = base64.b64encode(sig_bytes).decode("utf-8")
    return signed

# ---------------------------------------------------------------------------
# 1. Cluster Translations
# ---------------------------------------------------------------------------

CLUSTER_I18N = {
    "bode_export_dataset.cluster.json": {
        "pt-BR": {
            "display_name": "Exportar Conjunto de Dados Bode",
            "description": "Gera um caminho com carimbo de data/hora, empacota arrays de frequência/ganho/tensão e exporta os dados em CSV.",
            "category": "Clusters/Bode",
            "pins": {
                "Write": "Gravar",
                "Out": "Saída",
                "Frequencies": "Frequências",
                "Gains_dB": "Ganhos_dB",
                "Vin_Vpp": "Vin_Vpp",
                "Vout_Vpp": "Vout_Vpp",
                "SavedPath": "CaminhoSalvo"
            }
        },
        "es": {
            "display_name": "Exportar Conjunto de Datos Bode",
            "description": "Genera una ruta con marca de tiempo, empaqueta arrays de frecuencia/ganancia/voltaje y exporta los datos en CSV.",
            "category": "Clusters/Bode",
            "pins": {
                "Write": "Escribir",
                "Out": "Salida",
                "Frequencies": "Frecuencias",
                "Gains_dB": "Ganancias_dB",
                "Vin_Vpp": "Vin_Vpp",
                "Vout_Vpp": "Vout_Vpp",
                "SavedPath": "RutaGuardada"
            }
        }
    },
    "bode_setup_virtual_instruments.cluster.json": {
        "pt-BR": {
            "display_name": "Configurar Instrumentos Virtuais Bode",
            "description": "Inicializa os canais do Gerador de Funções Virtual e do Osciloscópio Virtual para medições de diagrama de Bode.",
            "category": "Clusters/Bode",
            "pins": {
                "In": "Entrada",
                "Out": "Saída",
                "SigGenAddress": "EndereçoGerador",
                "ScopeAddress": "EndereçoOsciloscópio",
                "SigGenDevice": "DispositivoGerador",
                "ScopeDevice": "DispositivoOsciloscópio"
            }
        },
        "es": {
            "display_name": "Configurar Instrumentos Virtuales Bode",
            "description": "Inicializa los canales del Generador de Funciones Virtual y del Osciloscopio Virtual para mediciones de diagrama de Bode.",
            "category": "Clusters/Bode",
            "pins": {
                "In": "Entrada",
                "Out": "Salida",
                "SigGenAddress": "DirecciónGenerador",
                "ScopeAddress": "DirecciónOsciloscopio",
                "SigGenDevice": "DispositivoGenerador",
                "ScopeDevice": "DispositivoOsciloscopio"
            }
        }
    },
    "bode_measure_virtual_point.cluster.json": {
        "pt-BR": {
            "display_name": "Medir Ponto Virtual Bode",
            "description": "Define a frequência de excitação no Gerador Virtual, ajusta automaticamente a base de tempo do Osciloscópio Virtual, adquire CH1/CH2 e calcula Ganho (dB) e Vpp.",
            "category": "Clusters/Bode",
            "pins": {
                "In": "Entrada",
                "Out": "Saída",
                "SigGenDevice": "DispositivoGerador",
                "ScopeDevice": "DispositivoOsciloscópio",
                "Frequency": "Frequência",
                "Gain_dB": "Ganho_dB",
                "Vin_Vpp": "Vin_Vpp",
                "Vout_Vpp": "Vout_Vpp"
            }
        },
        "es": {
            "display_name": "Medir Punto Virtual Bode",
            "description": "Configura la frecuencia de excitación en el Generador Virtual, auto-ajusta la base de tiempo del Osciloscopio Virtual, adquiere CH1/CH2 y calcula Ganancia (dB) y Vpp.",
            "category": "Clusters/Bode",
            "pins": {
                "In": "Entrada",
                "Out": "Salida",
                "SigGenDevice": "DispositivoGenerador",
                "ScopeDevice": "DispositivoOsciloscopio",
                "Frequency": "Frecuencia",
                "Gain_dB": "Ganancia_dB",
                "Vin_Vpp": "Vin_Vpp",
                "Vout_Vpp": "Vout_Vpp"
            }
        }
    },
    "bode_setup_instruments.cluster.json": {
        "pt-BR": {
            "display_name": "Configurar Instrumentos Físicos Bode",
            "description": "Inicializa o gerador de funções Minipa e os canais do osciloscópio Tektronix TBS1062 para medições de diagrama de Bode.",
            "category": "Clusters/Bode",
            "pins": {
                "In": "Entrada",
                "Out": "Saída",
                "MinipaAddress": "EndereçoMinipa",
                "ScopeAddress": "EndereçoOsciloscópio",
                "MinipaDevice": "DispositivoMinipa",
                "ScopeDevice": "DispositivoOsciloscópio"
            }
        },
        "es": {
            "display_name": "Configurar Instrumentos Físicos Bode",
            "description": "Inicializa el generador de funciones Minipa y los canales del osciloscopio Tektronix TBS1062 para mediciones de diagrama de Bode.",
            "category": "Clusters/Bode",
            "pins": {
                "In": "Entrada",
                "Out": "Salida",
                "MinipaAddress": "DirecciónMinipa",
                "ScopeAddress": "DirecciónOsciloscopio",
                "MinipaDevice": "DispositivoMinipa",
                "ScopeDevice": "DispositivoOsciloscopio"
            }
        }
    },
    "bode_measure_point.cluster.json": {
        "pt-BR": {
            "display_name": "Medir Ponto Físico Bode",
            "description": "Define a frequência no gerador Minipa, ajusta a base de tempo do osciloscópio, adquire CH1/CH2 e calcula Ganho (dB) e Vpp.",
            "category": "Clusters/Bode",
            "pins": {
                "In": "Entrada",
                "Out": "Saída",
                "MinipaDevice": "DispositivoMinipa",
                "ScopeDevice": "DispositivoOsciloscópio",
                "Frequency": "Frequência",
                "Gain_dB": "Ganho_dB",
                "Vin_Vpp": "Vin_Vpp",
                "Vout_Vpp": "Vout_Vpp"
            }
        },
        "es": {
            "display_name": "Medir Punto Físico Bode",
            "description": "Configura la frecuencia en el generador Minipa, ajusta la base de tiempo del osciloscopio, adquiere CH1/CH2 y calcula Ganancia (dB) y Vpp.",
            "category": "Clusters/Bode",
            "pins": {
                "In": "Entrada",
                "Out": "Salida",
                "MinipaDevice": "DispositivoMinipa",
                "ScopeDevice": "DispositivoOsciloscopio",
                "Frequency": "Frecuencia",
                "Gain_dB": "Ganancia_dB",
                "Vin_Vpp": "Vin_Vpp",
                "Vout_Vpp": "Vout_Vpp"
            }
        }
    },
    "vuv_setup_instruments.cluster.json": {
        "pt-BR": {
            "display_name": "Configurar Instrumentos VUV Horiba",
            "description": "Inicializa o Monocromador VUV Horiba (MonoID, Torrete de Redes, Fendas) e o Osciloscópio Tektronix MDO com modo de Simulação selecionável.",
            "category": "Clusters/Horiba",
            "pins": {
                "In": "Entrada",
                "Out": "Saída",
                "MonoID": "IDMonocromador",
                "Turret": "Torrete",
                "EntranceSlit_mm": "FendaEntrada_mm",
                "ExitSlit_mm": "FendaSaída_mm",
                "ScopeAddress": "EndereçoOsciloscópio",
                "ScopeChannel": "CanalOsciloscópio",
                "TimeScale": "EscalaTempo",
                "Simulation": "Simulação",
                "MonoDevice": "DispositivoMonocromador",
                "ScopeDevice": "DispositivoOsciloscópio"
            }
        },
        "es": {
            "display_name": "Configurar Instrumentos VUV Horiba",
            "description": "Inicializa el Monocromador VUV Horiba (MonoID, Torreta de Redes, Ranuras) y el Osciloscopio Tektronix MDO con modo de Simulación seleccionable.",
            "category": "Clusters/Horiba",
            "pins": {
                "In": "Entrada",
                "Out": "Salida",
                "MonoID": "IDMonocromador",
                "Turret": "Torreta",
                "EntranceSlit_mm": "RanuraEntrada_mm",
                "ExitSlit_mm": "RanuraSalida_mm",
                "ScopeAddress": "DirecciónOsciloscopio",
                "ScopeChannel": "CanalOsciloscopio",
                "TimeScale": "EscalaTiempo",
                "Simulation": "Simulación",
                "MonoDevice": "DispositivoMonocromador",
                "ScopeDevice": "DispositivoOsciloscopio"
            }
        }
    },
    "vuv_measure_point.cluster.json": {
        "pt-BR": {
            "display_name": "Medir Ponto VUV Horiba",
            "description": "Posiciona o Monocromador no comprimento de onda (nm), adquire a forma de onda do osciloscópio e calcula Tensão Média, Desvio Padrão, Potência (mW) e Potência (dBm).",
            "category": "Clusters/Horiba",
            "pins": {
                "In": "Entrada",
                "Out": "Saída",
                "MonoDevice": "DispositivoMonocromador",
                "ScopeDevice": "DispositivoOsciloscópio",
                "Wavelength": "ComprimentoDeOnda",
                "ScopeChannel": "CanalOsciloscópio",
                "CalFactor": "FatorCalibração",
                "SettleDelay": "AtrasoEstabilização",
                "Simulation": "Simulação",
                "Power_mW": "Potência_mW",
                "Power_dBm": "Potência_dBm",
                "StdDev_V": "DesvPad_V",
                "MeanVoltage_V": "TensãoMédia_V"
            }
        },
        "es": {
            "display_name": "Medir Punto VUV Horiba",
            "description": "Posiciona el Monocromador en la longitud de onda (nm), adquiere la forma de onda del osciloscopio y calcula Voltaje Medio, Desviación Estándar, Potencia (mW) y Potencia (dBm).",
            "category": "Clusters/Horiba",
            "pins": {
                "In": "Entrada",
                "Out": "Salida",
                "MonoDevice": "DispositivoMonocromador",
                "ScopeDevice": "DispositivoOsciloscopio",
                "Wavelength": "LongitudDeOnda",
                "ScopeChannel": "CanalOsciloscopio",
                "CalFactor": "FactorCalibración",
                "SettleDelay": "RetardoEstabilización",
                "Simulation": "Simulación",
                "Power_mW": "Potencia_mW",
                "Power_dBm": "Potencia_dBm",
                "StdDev_V": "DesvEst_V",
                "MeanVoltage_V": "VoltajeMedio_V"
            }
        }
    },
    "vuv_accumulate_data.cluster.json": {
        "pt-BR": {
            "display_name": "Acumulador de Dados VUV Horiba",
            "description": "Acumula os valores de comprimento de onda (nm), potência (mW), potência (dBm) e desvio padrão (V) em arrays numéricos.",
            "category": "Clusters/Horiba",
            "pins": {
                "In": "Entrada",
                "Out": "Saída",
                "Wavelength": "ComprimentoDeOnda",
                "Power_mW": "Potência_mW",
                "Power_dBm": "Potência_dBm",
                "StdDev_V": "DesvPad_V",
                "Wavelength_Array": "Array_ComprimentoDeOnda",
                "Power_mW_Array": "Array_Potência_mW",
                "Power_dBm_Array": "Array_Potência_dBm",
                "StdDev_Array": "Array_DesvPad"
            }
        },
        "es": {
            "display_name": "Acumulador de Datos VUV Horiba",
            "description": "Acumula los valores de longitud de onda (nm), potencia (mW), potencia (dBm) y desviación estándar (V) en arrays numéricos.",
            "category": "Clusters/Horiba",
            "pins": {
                "In": "Entrada",
                "Out": "Salida",
                "Wavelength": "LongitudDeOnda",
                "Power_mW": "Potencia_mW",
                "Power_dBm": "Potencia_dBm",
                "StdDev_V": "DesvEst_V",
                "Wavelength_Array": "Array_LongitudDeOnda",
                "Power_mW_Array": "Array_Potencia_mW",
                "Power_dBm_Array": "Array_Potencia_dBm",
                "StdDev_Array": "Array_DesvEst"
            }
        }
    },
    "vuv_export_dataset.cluster.json": {
        "pt-BR": {
            "display_name": "Exportar Conjunto de Dados VUV Horiba",
            "description": "Empacota os arrays de comprimento de onda (nm), potência (mW), potência (dBm) e desvio padrão, salvando em arquivo CSV com carimbo de data/hora.",
            "category": "Clusters/Horiba",
            "pins": {
                "Write": "Gravar",
                "Out": "Saída",
                "Wavelength_Array": "Array_ComprimentoDeOnda",
                "Power_mW_Array": "Array_Potência_mW",
                "Power_dBm_Array": "Array_Potência_dBm",
                "StdDev_Array": "Array_DesvPad",
                "SavedPath": "CaminhoSalvo"
            }
        },
        "es": {
            "display_name": "Exportar Conjunto de Datos VUV Horiba",
            "description": "Empaqueta los arrays de longitud de onda (nm), potencia (mW), potencia (dBm) y desviación estándar, guardando en archivo CSV con marca de tiempo.",
            "category": "Clusters/Horiba",
            "pins": {
                "Write": "Escribir",
                "Out": "Salida",
                "Wavelength_Array": "Array_LongitudDeOnda",
                "Power_mW_Array": "Array_Potencia_mW",
                "Power_dBm_Array": "Array_Potencia_dBm",
                "StdDev_Array": "Array_DesvEst",
                "SavedPath": "RutaGuardada"
            }
        }
    },
    "fh_setup_instruments.cluster.json": {
        "pt-BR": {
            "display_name": "Configurar Instrumentos Franck-Hertz",
            "description": "Inicializa a conexão Serial para o aparato de Franck-Hertz (/dev/ttyUSB0 ou porta COM) com chave selecionável Simulação / Hardware Real.",
            "category": "Clusters/Franck-Hertz",
            "pins": {
                "In": "Entrada",
                "Out": "Saída",
                "Port": "Porta",
                "Simulation": "Simulação",
                "Device": "Dispositivo"
            }
        },
        "es": {
            "display_name": "Configurar Instrumentos Franck-Hertz",
            "description": "Inicializa la conexión Serial para el aparato de Franck-Hertz (/dev/ttyUSB0 o puerto COM) con interruptor seleccionable Simulación / Hardware Real.",
            "category": "Clusters/Franck-Hertz",
            "pins": {
                "In": "Entrada",
                "Out": "Salida",
                "Port": "Puerto",
                "Simulation": "Simulación",
                "Device": "Dispositivo"
            }
        }
    },
    "fh_measure_point.cluster.json": {
        "pt-BR": {
            "display_name": "Medir Ponto Franck-Hertz",
            "description": "Adquire tensão de aceleração (Ua), corrente de coletor (Is), tensão de retardo (Us) e temperatura (T) via comandos seriais ou modo de simulação física.",
            "category": "Clusters/Franck-Hertz",
            "pins": {
                "In": "Entrada",
                "Out": "Saída",
                "Device": "Dispositivo",
                "Step": "Passo",
                "Simulation": "Simulação",
                "Ua_V": "Ua_V",
                "Is_nA": "Is_nA",
                "Us_V": "Us_V",
                "Temp_C": "Temp_C"
            }
        },
        "es": {
            "display_name": "Medir Punto Franck-Hertz",
            "description": "Adquiere voltaje de aceleración (Ua), corriente de colector (Is), voltaje de retardo (Us) y temperatura (T) mediante consultas seriales o modo de simulación física.",
            "category": "Clusters/Franck-Hertz",
            "pins": {
                "In": "Entrada",
                "Out": "Salida",
                "Device": "Dispositivo",
                "Step": "Paso",
                "Simulation": "Simulación",
                "Ua_V": "Ua_V",
                "Is_nA": "Is_nA",
                "Us_V": "Us_V",
                "Temp_C": "Temp_C"
            }
        }
    },
    "fh_check_limits.cluster.json": {
        "pt-BR": {
            "display_name": "Verificação de Limites Franck-Hertz",
            "description": "Avalia a condição de continuação da varredura (Index == 0 OU (Ua < Max_Ua E Is < Max_Is)).",
            "category": "Clusters/Franck-Hertz",
            "pins": {
                "Index": "Índice",
                "Ua_V": "Ua_V",
                "Is_nA": "Is_nA",
                "Max_Ua": "Max_Ua",
                "Max_Is": "Max_Is",
                "Continue": "Continuar"
            }
        },
        "es": {
            "display_name": "Verificación de Límites Franck-Hertz",
            "description": "Evalúa la condición de continuación del barrido (Index == 0 O (Ua < Max_Ua Y Is < Max_Is)).",
            "category": "Clusters/Franck-Hertz",
            "pins": {
                "Index": "Índice",
                "Ua_V": "Ua_V",
                "Is_nA": "Is_nA",
                "Max_Ua": "Max_Ua",
                "Max_Is": "Max_Is",
                "Continue": "Continuar"
            }
        }
    },
    "fh_accumulate_data.cluster.json": {
        "pt-BR": {
            "display_name": "Acumulador de Dados Franck-Hertz",
            "description": "Acumula os valores de tensão de aceleração (Ua), corrente de coletor (Is), tensão de retardo (Us) e temperatura (T) em arrays numéricos.",
            "category": "Clusters/Franck-Hertz",
            "pins": {
                "In": "Entrada",
                "Out": "Saída",
                "Ua_V": "Ua_V",
                "Is_nA": "Is_nA",
                "Us_V": "Us_V",
                "Temp_C": "Temp_C",
                "Ua_Array": "Array_Ua",
                "Is_Array": "Array_Is",
                "Us_Array": "Array_Us",
                "Temp_Array": "Array_Temp"
            }
        },
        "es": {
            "display_name": "Acumulador de Datos Franck-Hertz",
            "description": "Acumula los valores de voltaje de aceleración (Ua), corriente de colector (Is), voltaje de retardo (Us) y temperatura (T) en arrays numéricos.",
            "category": "Clusters/Franck-Hertz",
            "pins": {
                "In": "Entrada",
                "Out": "Salida",
                "Ua_V": "Ua_V",
                "Is_nA": "Is_nA",
                "Us_V": "Us_V",
                "Temp_C": "Temp_C",
                "Ua_Array": "Array_LongitudDeOnda",
                "Is_Array": "Array_Is",
                "Us_Array": "Array_Us",
                "Temp_Array": "Array_Temp"
            }
        }
    },
    "fh_export_dataset.cluster.json": {
        "pt-BR": {
            "display_name": "Exportar Conjunto de Dados Franck-Hertz",
            "description": "Empacota os arrays de tensão de aceleração (Ua), corrente de coletor (Is), tensão de retardo (Us) e temperatura (T), salvando em arquivo CSV.",
            "category": "Clusters/Franck-Hertz",
            "pins": {
                "Write": "Gravar",
                "Out": "Saída",
                "Ua_V": "Ua_V",
                "Is_nA": "Is_nA",
                "Us_V": "Us_V",
                "Temp_C": "Temp_C",
                "SavedPath": "CaminhoSalvo"
            }
        },
        "es": {
            "display_name": "Exportar Conjunto de Datos Franck-Hertz",
            "description": "Empaqueta los arrays de voltaje de aceleración (Ua), corriente de colector (Is), voltaje de retardo (Us) y temperatura (T), guardando en archivo CSV.",
            "category": "Clusters/Franck-Hertz",
            "pins": {
                "Write": "Escribir",
                "Out": "Salida",
                "Ua_V": "Ua_V",
                "Is_nA": "Is_nA",
                "Us_V": "Us_V",
                "Temp_C": "Temp_C",
                "SavedPath": "RutaGuardada"
            }
        }
    }
}

# ---------------------------------------------------------------------------
# 2. Package Translations (for catalog.json and manifest.json)
# ---------------------------------------------------------------------------

PACKAGE_I18N = {
    "blueprints/bode/physical_bode_plot": {
        "pt-BR": {
            "name": "Medição de Diagrama de Bode (Física)",
            "description": "Fluxo completo de medição automatizada de resposta em frequência (Diagrama de Bode) usando Minipa MFG-4230 e Tektronix TBS-1062."
        },
        "es": {
            "name": "Medición de Diagrama de Bode (Física)",
            "description": "Flujo completo de medición automatizada de respuesta en frecuencia (Diagrama de Bode) usando Minipa MFG-4230 y Tektronix TBS-1062."
        }
    },
    "blueprints/horiba/vuv_spectroscopy": {
        "pt-BR": {
            "name": "Espectroscopia VUV Horiba H20 UVL",
            "description": "Fluxo automatizado de espectroscopia de excitação e fluorescência VUV usando monocromador Horiba H20 UVL e osciloscópio Tektronix MDO-3040."
        },
        "es": {
            "name": "Espectroscopía VUV Horiba H20 UVL",
            "description": "Flujo automatizado de espectroscopía de excitación y fluorescencia VUV usando monocromador Horiba H20 UVL y osciloscopio Tektronix MDO-3040."
        }
    },
    "blueprints/ifgw/franck_hertz": {
        "pt-BR": {
            "name": "Experimento Franck-Hertz IFGW F-740",
            "description": "Fluxo automatizado de medição da curva de ressonância do mercúrio (Franck-Hertz) com gráficos em tempo real, monitoramento de limites de segurança e exportação de dados."
        },
        "es": {
            "name": "Experimento Franck-Hertz IFGW F-740",
            "description": "Flujo automatizado de medición de la curva de resonancia de mercurio (Franck-Hertz) con gráficos en tiempo real, monitoreo de límites de seguridad y exportación de datos."
        }
    },
    "clusters/bode/physical_setup": {
        "pt-BR": {
            "name": "Clusters do Setup Físico de Bode",
            "description": "Clusters de inicialização de instrumentos e medição ponto a ponto de diagrama de Bode usando Minipa MFG-4230 e Tektronix TBS-1062."
        },
        "es": {
            "name": "Clusters de Setup Físico de Bode",
            "description": "Clusters de inicialización de instrumentos y medición punto a punto de diagrama de Bode usando Minipa MFG-4230 y Tektronix TBS-1062."
        }
    },
    "clusters/horiba/vuv_spectroscopy": {
        "pt-BR": {
            "name": "Clusters de Espectroscopia Horiba VUV",
            "description": "Clusters de controle de monocromador, aquisição de formas de onda, acúmulo de dados e exportação em CSV para espectroscopia Horiba VUV."
        },
        "es": {
            "name": "Clusters de Espectroscopía Horiba VUV",
            "description": "Clusters de control de monocromador, adquisición de formas de onda, acumulación de datos y exportación en CSV para espectroscopía Horiba VUV."
        }
    },
    "clusters/ifgw/franck_hertz": {
        "pt-BR": {
            "name": "Clusters do Experimento Franck-Hertz IFGW",
            "description": "Clusters de configuração, medição, limites de segurança, acúmulo e exportação para o experimento IFGW F-740 Franck-Hertz."
        },
        "es": {
            "name": "Clusters del Experimento Franck-Hertz IFGW",
            "description": "Clusters de configuración, medición, límites de seguridad, acumulación y exportación para el experimento IFGW F-740 Franck-Hertz."
        }
    },
    "instruments/advantest/q8384": {
        "pt-BR": {
            "name": "Analisador de Espectro Óptico Advantest Q8384",
            "description": "Blocos de driver para analisador de espectro óptico (OSA) de alta resolução Advantest Q8384."
        },
        "es": {
            "name": "Analizador de Espectro Óptico Advantest Q8384",
            "description": "Bloques de controlador para analizador de espectro óptico (OSA) de alta resolución Advantest Q8384."
        }
    },
    "instruments/agilent/a33220a": {
        "pt-BR": {
            "name": "Gerador de Funções Agilent 33220A",
            "description": "Blocos de driver para gerador de funções arbitrário Agilent 33220A (20 MHz)."
        },
        "es": {
            "name": "Generador de Funciones Agilent 33220A",
            "description": "Bloques de controlador para generador de funciones arbitrario Agilent 33220A (20 MHz)."
        }
    },
    "instruments/agilent/e4407b": {
        "pt-BR": {
            "name": "Analisador de Espectro Agilent E4407B",
            "description": "Blocos de driver para analisador de espectro Agilent ESA-E E4407B (9 kHz a 26.5 GHz)."
        },
        "es": {
            "name": "Analizador de Espectro Agilent E4407B",
            "description": "Bloques de controlador para analizador de espectro Agilent ESA-E E4407B (9 kHz a 26.5 GHz)."
        }
    },
    "instruments/agilent/hp34401a": {
        "pt-BR": {
            "name": "Multímetro Digital Agilent / HP 34401A",
            "description": "Blocos de driver para multímetro digital de bancada de 6½ dígitos Agilent / HP 34401A."
        },
        "es": {
            "name": "Multímetro Digital Agilent / HP 34401A",
            "description": "Bloques de controlador para multímetro digital de banco de 6½ dígitos Agilent / HP 34401A."
        }
    },
    "instruments/bk_precision/bk4052": {
        "pt-BR": {
            "name": "Gerador de Formas de Onda BK Precision 4052",
            "description": "Blocos de driver para gerador de formas de onda de canal duplo BK Precision 4052."
        },
        "es": {
            "name": "Generador de Formas de Onda BK Precision 4052",
            "description": "Bloques de controlador para generador de formas de onda de doble canal BK Precision 4052."
        }
    },
    "instruments/caen/dt5720b": {
        "pt-BR": {
            "name": "Digitalizador CAEN DT5720B",
            "description": "Blocos de driver para digitalizador de pulsos e física nuclear CAEN DT5720B."
        },
        "es": {
            "name": "Digitalizador CAEN DT5720B",
            "description": "Bloques de controlador para digitalizador de pulsos y física nuclear CAEN DT5720B."
        }
    },
    "instruments/coherent/ws1000a": {
        "pt-BR": {
            "name": "Medidor de Comprimento de Onda Coherent WaveMaster",
            "description": "Blocos de driver para medidor de comprimento de onda a laser Coherent WaveMaster (WS-1000A)."
        },
        "es": {
            "name": "Medidor de Longitud de Onda Coherent WaveMaster",
            "description": "Bloques de controlador para medidor de longitud de onda láser Coherent WaveMaster (WS-1000A)."
        }
    },
    "instruments/horiba/vuv_excitation": {
        "pt-BR": {
            "name": "Monocromador VUV Horiba H20 UVL",
            "description": "Blocos de driver para monocromador de vácuo ultravioleta Horiba H20 UVL."
        },
        "es": {
            "name": "Monocromador VUV Horiba H20 UVL",
            "description": "Bloques de controlador para monocromador de vacío ultravioleta Horiba H20 UVL."
        }
    },
    "instruments/keithley/k2231a": {
        "pt-BR": {
            "name": "Fonte DC Keithley 2231A",
            "description": "Blocos de driver para fonte de alimentação DC programável de 3 canais Keithley 2231A."
        },
        "es": {
            "name": "Fuente DC Keithley 2231A",
            "description": "Bloques de controlador para fuente de alimentación DC programable de 3 canales Keithley 2231A."
        }
    },
    "instruments/keithley/k2400": {
        "pt-BR": {
            "name": "Fonte e Medidor (SMU) Keithley 2400",
            "description": "Blocos de driver para unidade de fonte e medida (SMU) Keithley 2400."
        },
        "es": {
            "name": "Fuente y Medidor (SMU) Keithley 2400",
            "description": "Bloques de controlador para unidad de fuente y medida (SMU) Keithley 2400."
        }
    },
    "instruments/keopsys/edfa": {
        "pt-BR": {
            "name": "Amplificador Óptico EDFA Keopsys",
            "description": "Blocos de driver para amplificador óptico de fibra dopada com érbio (EDFA) Keopsys."
        },
        "es": {
            "name": "Amplificador Óptico EDFA Keopsys",
            "description": "Bloques de controlador para amplificador óptico de fibra dopada con erbio (EDFA) Keopsys."
        }
    },
    "instruments/keysight/agilent_816x": {
        "pt-BR": {
            "name": "Chassi Óptico Agilent / Keysight 816x",
            "description": "Blocos de driver para mainframe de testes ópticos e fontes de laser Agilent / Keysight 816x."
        },
        "es": {
            "name": "Chasis Óptico Agilent / Keysight 816x",
            "description": "Bloques de controlador para mainframe de pruebas ópticas y fuentes de láser Agilent / Keysight 816x."
        }
    },
    "instruments/keysight/dsox1204a": {
        "pt-BR": {
            "name": "Osciloscópio Keysight DSOX1204A",
            "description": "Blocos de driver para osciloscópio digital de 4 canais Keysight InfiniiVision DSOX1204A."
        },
        "es": {
            "name": "Osciloscopio Keysight DSOX1204A",
            "description": "Bloques de controlador para osciloscopio digital de 4 canales Keysight InfiniiVision DSOX1204A."
        }
    },
    "instruments/keysight/dsox3024a": {
        "pt-BR": {
            "name": "Osciloscópio Keysight DSOX3024A",
            "description": "Blocos de driver para osciloscópio digital Keysight InfiniiVision DSOX3024A."
        },
        "es": {
            "name": "Osciloscopio Keysight DSOX3024A",
            "description": "Bloques de controlador para osciloscopio digital Keysight InfiniiVision DSOX3024A."
        }
    },
    "instruments/keysight/dsox_series": {
        "pt-BR": {
            "name": "Osciloscópios Keysight Série DSOX",
            "description": "Blocos de driver universais para osciloscópios da série Keysight InfiniiVision DSOX."
        },
        "es": {
            "name": "Osciloscopios Keysight Serie DSOX",
            "description": "Bloques de controlador universales para osciloscopios de la serie Keysight InfiniiVision DSOX."
        }
    },
    "instruments/keysight/e36234a": {
        "pt-BR": {
            "name": "Fonte DC Keysight E36234A",
            "description": "Blocos de driver para fonte DC de canal duplo de alta precisão Keysight E36234A."
        },
        "es": {
            "name": "Fuente DC Keysight E36234A",
            "description": "Bloques de controlador para fuente DC de doble canal de alta precisión Keysight E36234A."
        }
    },
    "instruments/mcc/mcdaq1208ls": {
        "pt-BR": {
            "name": "Placa DAQ USB MCC USB-1208LS",
            "description": "Blocos de driver para módulo multifunção de aquisição de dados USB Measurement Computing USB-1208LS."
        },
        "es": {
            "name": "Placa DAQ USB MCC USB-1208LS",
            "description": "Bloques de controlador para módulo multifunción de adquisición de datos USB Measurement Computing USB-1208LS."
        }
    },
    "instruments/minipa/mfg4230": {
        "pt-BR": {
            "name": "Gerador de Funções Minipa MFG-4230",
            "description": "Blocos de driver para gerador de funções e formas de onda arbitrárias Minipa MFG-4230."
        },
        "es": {
            "name": "Generador de Funciones Minipa MFG-4230",
            "description": "Bloques de controlador para generador de funciones y formas de onda arbitrarias Minipa MFG-4230."
        }
    },
    "instruments/ni/nidaqmx_device": {
        "pt-BR": {
            "name": "Dispositivo NI-DAQmx National Instruments",
            "description": "Blocos de driver para canais analógicos e digitais NI-DAQmx da National Instruments."
        },
        "es": {
            "name": "Dispositivo NI-DAQmx National Instruments",
            "description": "Bloques de controlador para canales analógicos y digitales NI-DAQmx de National Instruments."
        }
    },
    "instruments/owon/dge2000": {
        "pt-BR": {
            "name": "Gerador de Funções OWON Série DGE2000",
            "description": "Blocos de driver para geradores de formas de onda arbitrárias da série OWON DGE2000."
        },
        "es": {
            "name": "Generador de Funciones OWON Serie DGE2000",
            "description": "Bloques de controlador para generadores de formas de onda arbitrarias de la serie OWON DGE2000."
        }
    },
    "instruments/srs/sr830": {
        "pt-BR": {
            "name": "Amplificador Lock-in SRS SR830",
            "description": "Blocos de driver para amplificador lock-in de DSP duplo Stanford Research Systems SR830."
        },
        "es": {
            "name": "Amplificador Lock-in SRS SR830",
            "description": "Bloques de controlador para amplificador lock-in de doble DSP Stanford Research Systems SR830."
        }
    },
    "instruments/tektronix/mdo3040": {
        "pt-BR": {
            "name": "Osciloscópio Tektronix MDO3040",
            "description": "Blocos de driver para osciloscópio de domínio misto Tektronix MDO3040."
        },
        "es": {
            "name": "Osciloscopio Tektronix MDO3040",
            "description": "Bloques de controlador para osciloscopio de dominio mixto Tektronix MDO3040."
        }
    },
    "instruments/tektronix/mso24": {
        "pt-BR": {
            "name": "Osciloscópio Tektronix MSO24",
            "description": "Blocos de driver para osciloscópio de sinais mistos Tektronix Série 2 (MSO24)."
        },
        "es": {
            "name": "Osciloscopio Tektronix MSO24",
            "description": "Bloques de controlador para osciloscopio de señales mixtas Tektronix Serie 2 (MSO24)."
        }
    },
    "instruments/tektronix/tbs1062": {
        "pt-BR": {
            "name": "Osciloscópio Tektronix TBS1062",
            "description": "Blocos de driver para osciloscópio digital de armazenamento Tektronix TBS1062."
        },
        "es": {
            "name": "Osciloscopio Tektronix TBS1062",
            "description": "Bloques de controlador para osciloscopio digital de almacenamiento Tektronix TBS1062."
        }
    },
    "instruments/thorlabs/lts200": {
        "pt-BR": {
            "name": "Estágio de Translação Thorlabs LTS200",
            "description": "Blocos de driver para platina de translação motorizada de longo curso Thorlabs LTS200."
        },
        "es": {
            "name": "Etapa de Traslación Thorlabs LTS200",
            "description": "Bloques de controlador para platina de traslación motorizada de largo recorrido Thorlabs LTS200."
        }
    },
    "instruments/thorlabs/mdt69x": {
        "pt-BR": {
            "name": "Controlador Piezoelétrico Thorlabs MDT693B/MDT694",
            "description": "Blocos de driver para controlador de atuadores piezoelétricos de 3 eixos Thorlabs MDT69X."
        },
        "es": {
            "name": "Controlador Piezoeléctrico Thorlabs MDT693B/MDT694",
            "description": "Bloques de controlador para controlador de actuadores piezoeléctricos de 3 ejes Thorlabs MDT69X."
        }
    },
    "instruments/thorlabs/pm100d": {
        "pt-BR": {
            "name": "Medidor de Potência Óptica Thorlabs PM100D",
            "description": "Blocos de driver para console digital de medição de potência óptica Thorlabs PM100D."
        },
        "es": {
            "name": "Medidor de Potencia Óptica Thorlabs PM100D",
            "description": "Bloques de controlador para consola digital de medición de potencia óptica Thorlabs PM100D."
        }
    },
    "instruments/yokogawa/aq6370": {
        "pt-BR": {
            "name": "Analisador de Espectro Óptico Yokogawa AQ6370",
            "description": "Blocos de driver para analisador de espectro óptico (OSA) de alta resolução Yokogawa AQ6370."
        },
        "es": {
            "name": "Analizador de Espectro Óptico Yokogawa AQ6370",
            "description": "Bloques de controlador para analizador de espectro óptico (OSA) de alta resolución Yokogawa AQ6370."
        }
    }
}

# ---------------------------------------------------------------------------
# Apply Cluster Translations
# ---------------------------------------------------------------------------

cluster_dirs = [CORE_CLUSTERS_DIR, STORE_DIST_DIR / "clusters"]
if USER_STORE_DIR.exists():
    cluster_dirs.append(USER_STORE_DIR / "clusters")

for cdir in cluster_dirs:
    if not cdir.exists():
        continue
    for root, _, files in os.walk(cdir):
        for f in files:
            if f.endswith(".cluster.json") and f in CLUSTER_I18N:
                path = Path(root) / f
                with open(path, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                data["i18n"] = CLUSTER_I18N[f]
                # Sign cluster with master key
                signed_data = sign_json_with_key(data)
                with open(path, "w", encoding="utf-8") as fp:
                    json.dump(signed_data, fp, indent=2)
                print(f"[I18N Updater] Updated & signed cluster: {path}")

# ---------------------------------------------------------------------------
# Apply Package Translations to manifests and catalog.json
# ---------------------------------------------------------------------------

catalog_path = STORE_DIST_DIR / "catalog.json"
with open(catalog_path, "r", encoding="utf-8") as fp:
    catalog = json.load(fp)

for pkg in catalog.get("packages", []):
    pid = pkg.get("id")
    if pid in PACKAGE_I18N:
        pkg["i18n"] = PACKAGE_I18N[pid]
    
    # Also update the manifest.json inside the package folder
    rel_path = pkg.get("path") or pid
    pkg_dir = STORE_DIST_DIR / rel_path
    manifest_path = pkg_dir / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as mfp:
            manifest = json.load(mfp)
        if pid in PACKAGE_I18N:
            manifest["i18n"] = PACKAGE_I18N[pid]
        
        # Recompute package file hashes
        hashes = {}
        for fn in pkg.get("files", []):
            if fn == "manifest.json":
                continue
            target_f = pkg_dir / fn
            if target_f.exists():
                h = hashlib.sha256(target_f.read_bytes()).hexdigest()
                hashes[fn] = h
        
        manifest["hashes"] = hashes
        pkg["hashes"] = hashes
        
        with open(manifest_path, "w", encoding="utf-8") as mfp:
            json.dump(manifest, mfp, indent=2)
        
        # Compute manifest.json hash itself
        m_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        hashes["manifest.json"] = m_hash
        pkg["hashes"]["manifest.json"] = m_hash

# Re-sign catalog.json
clean_catalog = {k: v for k, v in catalog.items() if k not in ("signature", "creator_identity")}
canonical_cat = json.dumps(clean_catalog, sort_keys=True, separators=(",", ":")).encode("utf-8")
cat_sig = priv_key.sign(canonical_cat)
catalog["creator_identity"] = pub_hex
catalog["signature"] = base64.b64encode(cat_sig).decode("utf-8")

with open(catalog_path, "w", encoding="utf-8") as fp:
    json.dump(catalog, fp, indent=2)

print(f"[I18N Updater] Updated catalog.json with i18n for all {len(catalog.get('packages', []))} packages and signed.")

# ---------------------------------------------------------------------------
# Synchronize to user local store ~/.comfylab/store if installed
# ---------------------------------------------------------------------------

if USER_STORE_DIR.exists():
    installed_file = Path.home() / ".comfylab" / "store_installed.json"
    if installed_file.exists():
        try:
            with open(installed_file, "r", encoding="utf-8") as ifp:
                installed_data = json.load(ifp)
            for pid, inst in installed_data.items():
                if pid in PACKAGE_I18N:
                    inst["i18n"] = PACKAGE_I18N[pid]
            with open(installed_file, "w", encoding="utf-8") as ifp:
                json.dump(installed_data, ifp, indent=2)
            print("[I18N Updater] Synchronized user installed.json with i18n.")
        except Exception as e:
            print(f"[I18N Updater] Notice: installed.json sync skipped: {e}")

print("[I18N Updater] Successfully completed all translations updates!")

# Lista de modelos LLM locales candidatos

## Fine-tuned para ciberseguridad
### DeepHat V1 (7B) (WhiteRabbitNeo 3)

- **Modelo base**: Qwen2.5-Coder-7B.
- **Tipo**: Modelo de lenguaje causal.
- **Parámetros**: 7.61B (6.53B sin embeddings).
- **Capas**: 28.
- **Contexto**: Hasta 131,072 tokens.
- **Descarga**: [15 GB en Hugging Face](https://huggingface.co/DeepHat/DeepHat-V1-7B).

### WhiteRabbitNeo 2 (70B)
- **Modelo base**: Llama 3.1 70B.
- **Tipo**: Modelo de lenguaje causal fine-tuned para ciberseguridad.
- **Parámetros**: 70B.
- **Descarga original**: [Hugging Face - WhiteRabbitNeo](https://huggingface.co/WhiteRabbitNeo/Llama-3.1-WhiteRabbitNeo-2-70B)

#### Quantizaciones GGUF (por bartowski)
Quantizaciones con imatrix para ejecutar en local con llama.cpp, Ollama, LM Studio, etc.

**Repositorio**: [bartowski/Llama-3.1-WhiteRabbitNeo-2-70B-GGUF](https://huggingface.co/bartowski/Llama-3.1-WhiteRabbitNeo-2-70B-GGUF)

##### Para GPU de 64GB VRAM (2 opciones recomendadas)
| Quantización | Tamaño | Calidad | Notas |
|--------------|--------|---------|-------|
| **Q6_K** | 57.89 GB | Muy alta | Near perfect, recomendado para máxima calidad |
| **Q5_K_M** | 49.95 GB | Alta | Buen balance calidad/tamaño, recomendado |

##### Para GPU de 32GB VRAM (2 opciones recomendadas)
| Quantización | Tamaño | Calidad | Notas |
|--------------|--------|---------|-------|
| **IQ3_M** | 31.94 GB | Media-baja | Nuevo método con rendimiento comparable a Q3_K_M |
| **Q3_K_S** | 30.91 GB | Baja | Ajustado, deja ~1GB de margen |
| **IQ3_XXS** | 27.47 GB | Muy baja | Deja más margen, calidad reducida |


## Modelos generales (Reasoning / Distilled)

### DeepSeek-R1-Distill-Qwen-32B
- **Modelo base**: Qwen 2.5 32B (Destilado de DeepSeek-R1).
- **Tipo**: Modelo de razonamiento (Reasoning) destilado.
- **Parámetros**: 32B.
- **Descarga original**: [Hugging Face - DeepSeek-R1-Distill-Qwen-32B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B)

#### Quantizaciones GGUF (por bartowski)
**Repositorio**: [bartowski/DeepSeek-R1-Distill-Qwen-32B-GGUF](https://huggingface.co/bartowski/DeepSeek-R1-Distill-Qwen-32B-GGUF)

##### Para GPU de 64GB VRAM (2 opciones recomendadas)
| Quantización | Tamaño | Calidad | Notas |
|--------------|--------|---------|-------|
| **Q8_0** | 34.4 GB | Máxima | Prácticamente idéntico a FP16, cabe en 64GB |
| **Q6_K** | 26.9 GB | Muy alta | Permite contexto masivo (hasta 128k) sin problemas |

##### Para GPU de 32GB VRAM (2 opciones recomendadas)
| Quantización | Tamaño | Calidad | Notas |
|--------------|--------|---------|-------|
| **Q6_K** | 26.89 GB | Muy alta | Near perfect, cabe holgadamente en 32GB |
| **Q5_K_M** | 23.26 GB | Alta | Recomendado, deja mucho margen para contexto largo |

**Prompt format**:
```
<｜begin of sentence｜>{system_prompt}<｜User｜>{prompt}<｜Assistant｜>
```

### DeepSeek-R1-Distill-Llama-70B
- **Modelo base**: Llama 3.1 70B (Destilado de DeepSeek-R1).
- **Tipo**: Modelo de razonamiento (Reasoning) destilado.
- **Parámetros**: 70B.
- **Descarga original**: [Hugging Face - DeepSeek-R1-Distill-Llama-70B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Llama-70B)

#### Quantizaciones GGUF (por unsloth)
**Repositorio**: [unsloth/DeepSeek-R1-Distill-Llama-70B-GGUF](https://huggingface.co/unsloth/DeepSeek-R1-Distill-Llama-70B-GGUF)

##### Para GPU de 64GB VRAM (2 opciones recomendadas)
| Quantización | Tamaño | Calidad | Notas |
|--------------|--------|---------|-------|
| **Q5_K_M** | 49.9 GB | Alta | Recomendado, buen balance |
| **Q4_K_M** | 42.5 GB | Buena | Estándar, deja mucho margen para contexto |

##### Para GPU de 64GB VRAM (2 opciones recomendadas)
| Quantización | Tamaño | Calidad | Notas |
|--------------|--------|---------|-------|
| **Q5_K_M** | 49.9 GB | Alta | Recomendado, buen balance |
| **Q4_K_M** | 42.5 GB | Buena | Estándar, deja mucho margen para contexto |

##### Para GPU de 32GB VRAM (2 opciones recomendadas)
```
<｜begin of sentence｜>{system_prompt}<｜User｜>{prompt}<｜Assistant｜>
```

## Modelos generales (no fine-tuned)
### GPT Oss (20B)
- **Modelo base**: OpenAI GPT-OSS 20B.
- **Arquitectura**: Mixture of Experts (MoE). 21B parámetros totales, 3.6B activos por token.
- **Licencia**: Apache 2.0.
- **Características**: Niveles de razonamiento configurables (Low, Medium, High) vía system prompt.
- **Descarga original**: [Hugging Face - openai/gpt-oss-20b](https://huggingface.co/openai/gpt-oss-20b)

#### Variantes "Uncensored" / "Derestricted"
1.  **ArliAI/gpt-oss-20b-Derestricted**
    *   **Método**: Norm-Preserving Biprojected Abliteration (mantiene mejor la lógica que la abliteración simple).
    *   **Link**: [Hugging Face](https://huggingface.co/ArliAI/gpt-oss-20b-Derestricted)
2.  **aoxo/gpt-oss-20b-uncensored**
    *   **Método**: Abliteración estándar.
    *   **Link**: [Hugging Face](https://huggingface.co/aoxo/gpt-oss-20b-uncensored)

#### Rendimiento en Hardware (32GB / 64GB VRAM)
Este modelo es muy ligero gracias a su arquitectura MoE (solo 3.6B activos).
- **Requisito base**: El modelo original (MXFP4) cabe en **16GB**.
- **En 32GB / 64GB**:
    - Puedes ejecutarlo en **Q8_0** (máxima fidelidad) o incluso **FP16** sin problemas de memoria.
    - Deja la gran mayoría de la VRAM libre para contextos masivos (128k+) o para cargar otros modelos simultáneamente.

### 
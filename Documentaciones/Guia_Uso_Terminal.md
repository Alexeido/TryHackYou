# Guía de Uso: Herramientas del Terminal

## Estado Actual ✅

- **Backend**: Envía el tool schema `execute_command` al LLM
- **Frontend**: Terminal integrado muestra comandos en ejecución
- **Sandbox**: Kali Linux container en puerto 5000, CORS habilitado
- **Git Snapshots**: Cada conversación tiene su workspace aislado

## ⚠️ Modelos Compatibles con Function Calling

No todos los modelos soportan herramientas (function calling). **Modelos recomendados**:

### OpenAI
- ✅ `gpt-4o` - Mejor para tool calling
- ✅ `gpt-4-turbo`
- ✅ `gpt-3.5-turbo`

### Google (Gemini)
- ✅ `gemini-2.0-flash-exp` - Excelente con tools
- ✅ `gemini-1.5-pro`
- ✅ `gemini-1.5-flash`

### Anthropic (Claude)
- ✅ `claude-3-5-sonnet-latest` - Muy bueno con tools
- ✅ `claude-3-5-haiku-latest`

### OpenRouter
- ✅ `anthropic/claude-3.5-sonnet`
- ✅ `google/gemini-2.0-flash-exp`
- ✅ `openai/gpt-4o`
- ❌ Modelos pequeños (<7B) generalmente NO soportan tools bien

## Cómo Usar

### 1. Selecciona un Modelo Compatible
En la interfaz, elige un modelo de la lista anterior que soporte function calling.

### 2. Pide Ejecución de Comandos
Ejemplos de prompts que funcionan:

```
- "ejecuta whoami"
- "escanea los puertos del servidor 192.168.1.1"
- "busca archivos .txt en el directorio actual"
- "haz ping a google.com"
- "verifica la versión de nmap instalada"
```

### 3. Observa el Terminal
El panel de terminal (derecha) mostrará:
- **Pestaña Actividad**: Tool calls y respuestas
- **Pestaña Jobs**: Comandos en ejecución
- **Pestaña Sesión**: Estado del workspace git

## 🔧 Solución de Problemas

### El modelo no usa la herramienta
**Causa**: El modelo no soporta function calling bien
**Solución**: Cambia a `gpt-4o`, `gemini-2.0-flash-exp` o `claude-3.5-sonnet`

### Sale "Sandbox desconectado"
**Causa**: Container de Kali no está corriendo
**Solución**: 
```bash
cd KaliSandbox
docker compose up -d
```

### El comando se ejecuta pero no veo el resultado
**Causa**: El flujo de tool calling requiere que el backend maneje el resultado
**Solución**: Actualmente en desarrollo (ver Fase 4)

## 📋 Próximos Pasos (Fase 4)

Actualmente, el LLM puede **invocar** la herramienta, pero el flujo completo es:

1. ✅ LLM invoca `execute_command`
2. ⚠️ Backend ejecuta el comando en el sandbox
3. ❌ Backend envía el resultado de vuelta al LLM
4. ❌ LLM responde con el análisis del resultado

**Estado**: Pasos 3-4 en desarrollo. Por ahora, el modelo puede ver que existe la herramienta pero no ejecuta el loop completo.

## 🎯 Demo Rápida

Para probar que todo funciona:

1. Selecciona `gpt-4o` o `gemini-2.0-flash-exp`
2. Escribe: "por favor ejecuta el comando whoami en el sandbox"
3. Observa que el modelo invoca la tool en el panel de terminal
4. (Flujo completo pendiente en Fase 4)

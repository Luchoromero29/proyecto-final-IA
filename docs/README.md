# EvalTIC — Asistente Inteligente Neuro-Simbólico Integrado (PG3)

**Proyecto Grupal 3 — Inteligencia Artificial (5K09)**  
**Universidad Tecnológica Nacional — Facultad Regional Mendoza (Ciclo 2026)**  
**Equipo: Grupo 20**  
- **Álvaro Tapia** (SM1: Diagnóstico Técnico y Plan de Reacondicionamiento)
- **Leonel Navarta** (SM2: Valuación Comercial, Obsolescencia y Demanda)
- **Luciano Romero** (SM3: Evaluación de la Operación y Decisión Financiera)

---

## 1. Descripción del Sistema

EvalTIC es un Asistente Inteligente Neuro-Simbólico diseñado para asistir a comerciantes y técnicos en la evaluación integral de notebooks usadas. Mediante el **Patrón Sándwich**, el sistema combina:
1. **Modelos de Lenguaje (LLM)**: Interfaz de procesamiento semántico para extracción estructurada (JSON) de avisos en lenguaje natural y redacción ejecutiva de dictámenes comerciales.
2. **Grafo de Conocimiento y Reglas Crisp**: Inferencia determinística de inviabilidad técnica, filtros de riesgo financiero y base de reglas expertas (R1.1 a R3.8).
3. **Lógica Difusa (Mamdani)**:
   - **SM1**: Degradación de batería y degradación térmica.
   - **SM2**: Riesgo de obsolescencia tecnológica y días de rotación en inventario.
   - **SM3**: Conveniencia de compra/negociación y cálculo de contraofertas sugeridas.

---

## 2. Requisitos de Instalación

```bash
# Crear y activar entorno virtual (opcional pero recomendado)
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

---

## 3. Configuración de Modelos de Lenguaje (.env)

El archivo `.env` permite alternar de forma transparente entre ejecución local (Ollama) o APIs remotas sin modificar el código fuente:

```env
# Proveedor: "ollama" o "openai"
LLM_PROVIDER=ollama

# Configuración Ollama (Local)
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=qwen2.5:1.5b

# Configuración API Remota (opcional)
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

---

## 4. Modos de Ejecución

### A. Interfaz Gráfica Web (Streamlit)
Permite interactuar visualmente con el asistente, cargar los escenarios de prueba con un clic y visualizar las métricas y explicaciones en tiempo real:
```bash
streamlit run app_web.py
```

### B. Modo Consola / CLI
```bash
# Modo interactivo
python3 orquestador_evaltic.py

# Evaluación directa por línea de comandos
python3 orquestador_evaltic.py "Vendo Acer Aspire 5 2020 piden $115.000..."

# Batería completa de pruebas de integración E2E (5 casos oficiales)
python3 orquestador_evaltic.py --test
```

---

## 5. Casos de Prueba Oficiales Incluidos

1. **Caso 1 (Acer Aspire 5 2020)**: Caso difuso con contraoferta fundamentada ($115k pedido ➔ Contraoferta $75k).
2. **Caso 2 (Lenovo ThinkPad T490 2019)**: Compra directa aprobada por margen neto holgado (34.3% vs 12% requerido).
3. **Caso 3 (Dell Inspiron 15)**: Descarte inmediato por falla física catastrófica (CPU en corto, cortocircuito temprano en SM1).
4. **Caso 4 (Lenovo ThinkPad T440p 2014)**: Descarte por riesgo comercial cruzado de obsolescencia e iliquidez (R3.8).
5. **Caso 5 (HP 15 Ryzen 3 2021)**: Compra aprobada con plan de upgrades planificado (margen neto 21% vs 20% requerido).

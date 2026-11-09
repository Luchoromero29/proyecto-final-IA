#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EvalTIC — Aplicación Web Interactiva del Asistente Maestro (PG3)
Desarrollado con Streamlit.
Ejecución: streamlit run app_web.py
"""

import streamlit as st
import json
import time
from orquestador_evaltic import (
    evaluar_publicacion_integral,
    CASOS_INTEGRADOS_PG3,
    LLM_PROVIDER,
    OLLAMA_MODEL,
    OPENAI_MODEL,
    obtener_driver_neo4j,
    NEO4J_URI,
    TIPO_INSTANCIA
)

st.set_page_config(
    page_title="EvalTIC — Asistente Maestro Integrado (PG3)",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1A365D;
        margin-bottom: 0px;
    }
    .sub-title {
        font-size: 1.1rem;
        color: #2B6CB0;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #F7FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
    }
    .metric-val {
        font-size: 1.6rem;
        font-weight: bold;
        color: #2D3748;
    }
    .metric-lbl {
        font-size: 0.85rem;
        color: #718096;
        text-transform: uppercase;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=80)
st.sidebar.title("EvalTIC — PG3")
st.sidebar.markdown("**Sistema Neuro-Simbólico de Valuación de Hardware**")
st.sidebar.markdown("---")
st.sidebar.markdown("**Equipo de Proyecto (Grupo 20):**")
st.sidebar.markdown("- 🛠️ **Álvaro Tapia**: SM1 Técnico")
st.sidebar.markdown("- 📊 **Leonel Navarta**: SM2 Comercial")
st.sidebar.markdown("- ⚖️ **Luciano Romero**: SM3 Financiero")
st.sidebar.markdown("---")

modelo_activo = OLLAMA_MODEL if LLM_PROVIDER == "ollama" else OPENAI_MODEL
st.sidebar.info(f"**Motor LLM Activo:**\n- Proveedor: `{LLM_PROVIDER.upper()}`\n- Modelo: `{modelo_activo}`")

try:
    driver_n4j = obtener_driver_neo4j()
    st.sidebar.success(f"**Grafo Neo4j:** `{TIPO_INSTANCIA}`\n- URI: `{NEO4J_URI}`\n- Inferencia: Consultas Cypher en base de datos")
except Exception as e:
    st.sidebar.error(f"**Grafo Neo4j:** `Error de Conexión`\n- Detalle: {e}")

# Header
st.markdown('<div class="main-title">💻 EvalTIC — Asistente Maestro Integrado</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Reacondicionamiento Técnico, Valuación Comercial y Decisión Financiera para Notebooks Usadas</div>', unsafe_allow_html=True)

# Case selector
opciones_casos = ["-- Seleccionar un Escenario de Prueba --"] + list(CASOS_INTEGRADOS_PG3.keys()) + ["Personalizado"]
seleccion = st.selectbox("Cargar escenario preconfigurado:", opciones_casos)

texto_default = ""
if seleccion in CASOS_INTEGRADOS_PG3:
    texto_default = CASOS_INTEGRADOS_PG3[seleccion]

input_texto = st.text_area(
    "Publicación u Oferta de Venta (Lenguaje Natural):",
    value=texto_default,
    height=140,
    placeholder="Pega aquí la descripción de la notebook, estado técnico, componentes dañados y precio pedido..."
)

col_btn, _ = st.columns([2, 5])
with col_btn:
    btn_evaluar = st.button("🚀 Evaluar con EvalTIC", use_container_width=True, type="primary")

if btn_evaluar and input_texto.strip():
    with st.spinner("Ejecutando pipeline neuro-simbólico sándwich (SM1 ➔ SM2 ➔ SM3)..."):
        t0 = time.time()
        try:
            resultado = evaluar_publicacion_integral(input_texto, verbose=False)
            t_total = round(time.time() - t0, 2)

            if "error" in resultado:
                st.error(f"❌ {resultado['error']}")
                st.warning("⚠️ Formato esperado: 'Vendo [Marca] [Modelo] [Año/Specs] precio $[Monto] Detalles...'")
                st.stop()

            st.success(f"Evaluación completada en {t_total} segundos.")

            sm1 = resultado["sm1_tecnico"]
            sm2 = resultado["sm2_comercial"]
            sm3 = resultado["sm3_financiero"]
            ind = sm3.get("indicadores", {})
            dec = sm3.get("decision", "Desconocido")

            # Decision Badge
            col_b1, col_b2 = st.columns([1, 3])
            with col_b1:
                if dec == "Comprar":
                    st.success("### ✅ COMPRAR DIRECTO")
                elif dec == "ComprarConOfertaMenor":
                    st.warning("### 🤝 NEGOCIAR CONTRAOFERTA")
                elif dec == "VerificacionPendiente":
                    st.info("### 🔎 VERIFICAR ANTES DE DECIDIR")
                else:
                    st.error(f"### 🛑 DESCARTAR ({dec})")

            with col_b2:
                estado_dec = sm3.get("estado_decision", "")
                if sm3.get("motivo"):
                    st.write(f"**Motivo:** {sm3['motivo']}")
                if estado_dec == "Provisional":
                    st.caption("Decisión **provisional**: usa criterios y costos todavía no validados con el experto "
                               "y/o datos inferidos. Ver la pestaña de trazabilidad.")
                elif estado_dec == "Firme":
                    st.caption("Decisión **firme**.")
                pendientes = resultado.get("traza", {}).get("datos_pendientes", [])
                if pendientes:
                    st.write("**Verificar en la revisión:** " + "; ".join(pendientes))

            # Metric Cards
            m1, m2, m3, m4, m5 = st.columns(5)
            with m1:
                st.metric("Precio Solicitado", f"${ind.get('precio_publicado', 0):,} ARS")
            with m2:
                st.metric("Costo Reparaciones (SM1)", f"${sm1.get('costo_total', 0):,} ARS")
            with m3:
                st.metric("Valor Reventa VMA (SM2)", f"${sm2.get('vma_estimado_ars', 0):,} ARS")
            with m4:
                m_neto = ind.get('margen_neto_pct')
                m_req = ind.get('margen_requerido_pct')
                if m_neto is None or m_req is None:
                    st.metric("Margen Proyectado", "N/A")
                else:
                    st.metric("Margen Proyectado", f"{m_neto}%", delta=f"{round(m_neto - m_req, 1)} pp vs req")
            with m5:
                contra = ind.get('contraoferta_sugerida_ars')
                contra_str = f"${contra:,} ARS" if contra else "N/A"
                desc = ind.get('descuento_requerido_pct', 0.0)
                st.metric("Contraoferta Sugerida", contra_str, delta=f"-{desc}%" if (contra and desc) else None)

            st.markdown("---")

            # Tabs de Detalle
            tab_dictamen, tab_sm1, tab_sm2, tab_sm3, tab_trace = st.tabs([
                "📋 Dictamen Gerencial",
                "🛠️ SM1: Diagnóstico Técnico",
                "📊 SM2: Valuación Comercial",
                "⚖️ SM3: Decisión Financiera",
                "🔍 Trazabilidad Simbólica"
            ])

            with tab_dictamen:
                st.subheader("Dictamen Ejecutivo Consolidado")
                st.info(resultado["dictamen_gerencial"])

            with tab_sm1:
                st.subheader("Submódulo 1 — Diagnóstico Técnico y Plan de Reacondicionamiento")
                if sm1.get('es_viable') is None:
                    st.info("No se evaluó: la operación quedó pendiente de verificación antes del diagnóstico.")
                elif not sm1['es_viable']:
                    st.error(f"**Motivo de Inviabilidad:** {sm1.get('motivo')}")
                else:
                    st.write(f"**Intervenciones Requeridas:** {sm1.get('cantidad_intervenciones')}")
                    st.table(sm1["plan_reparacion"])
                    st.write(f"**Costo Total de Reparación:** ${sm1['costo_total']:,} ARS")

            with tab_sm2:
                st.subheader("Submódulo 2 — Valuación Comercial y Demanda")
                if sm2.get("estado") == "Omitido_Por_Inviabilidad":
                    st.warning("Tasación comercial omitida debido a inviabilidad técnica estructural.")
                elif sm2.get("estado") == "Verificacion_pendiente":
                    st.info(f"No se pudo tasar: falta {sm2.get('dato_faltante')}.")
                elif sm2.get("estado") == "Sin_evaluar":
                    st.info("No se evaluó.")
                else:
                    st.write(f"**Segmento (Neo4j):** {sm2.get('segmento')} · **Modelo de referencia:** {sm2.get('modelo_referencia') or 'no catalogado'}")
                    st.caption(f"Fuente del precio: {sm2.get('fuente_precio')}")
                    col2_1, col2_2 = st.columns(2)
                    with col2_1:
                        st.write(f"• **Precio de un equipo nuevo equivalente:** ${sm2.get('precio_base_referencia', 0):,} ARS")
                        st.write(f"• **Factor de depreciación:** {sm2.get('factor_depreciacion')} · **Factor de riesgo:** {sm2.get('factor_riesgo')}")
                        st.write(f"• **Revalorización por upgrades:** ${sm2.get('revalorizaciones_ars', 0):,} ARS")
                        st.write(f"• **Antigüedad Estimada:** {sm2.get('antiguedad_anios')} años")
                        st.write(f"• **VMA Final Tasado:** ${sm2.get('vma_estimado_ars', 0):,} ARS")
                    with col2_2:
                        st.write(f"• **Riesgo de Obsolescencia:** {sm2.get('riesgo_obsolescencia')} (Score: {sm2.get('score_riesgo')})")
                        st.write(f"• **Demanda Comercial:** {sm2.get('demanda_comercial')}")
                        st.write(f"• **Rotación Estimada:** {sm2.get('dias_rotacion_estimados')} días en inventario")

            with tab_sm3:
                st.subheader("Submódulo 3 — Evaluación Financiera y Decisión Difusa")
                st.write(f"**Decisión Final:** `{dec}`")
                if "motivo" in sm3 and sm3["motivo"]:
                    st.write(f"**Motivo:** {sm3['motivo']}")
                st.json(ind)

            with tab_trace:
                st.subheader("Trazabilidad y Auditoría Simbólica")
                traza = resultado.get("traza", {})
                st.markdown("**Reglas activadas (en orden):**")
                for r in traza.get("reglas", []):
                    st.write(f"• {r}")
                if traza.get("datos_inferidos"):
                    st.markdown("**Datos inferidos:** " + "; ".join(traza["datos_inferidos"]))
                if sm3.get("criterios_pendientes"):
                    st.markdown("**Criterios y costos provisionales que afectaron el resultado:**")
                    st.write(", ".join(sm3["criterios_pendientes"]))
                with st.expander("Criterios expertos usados (Neo4j)"):
                    st.json(traza.get("criterios_usados", {}))
                with st.expander("Costos de reparación usados (Neo4j)"):
                    st.json(traza.get("costos_usados", {}))
                with st.expander("Referencia de mercado (Neo4j)"):
                    st.json(traza.get("referencia_mercado"))
                with st.expander("Datos extraídos por el LLM"):
                    st.json(resultado["datos_extraidos"])

        except Exception as err:
            st.error(f"Error durante la evaluación: {err}")
            st.exception(err)

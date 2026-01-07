import streamlit as st
import pandas as pd
import numpy as np

# -----------------------------------------------------------------------------
# 1. BASE DE DATOS Y CONSTANTES (Extraído de los PDFs)
# -----------------------------------------------------------------------------

# Tabla simplificada de límites de Transmitancia Térmica (U) [W/m2K] - Fuente: Actualizacion_DITEC Pag 15
LIMITES_U = {
    'A': {'Techo': 0.84, 'Muro': 2.10, 'PisoVent': 3.60, 'Puerta': None},
    'B': {'Techo': 0.47, 'Muro': 0.80, 'PisoVent': 0.70, 'Puerta': 1.7},
    'C': {'Techo': 0.38, 'Muro': 0.60, 'PisoVent': 0.60, 'Puerta': 1.7}, # Asumido similar a D para simplificación si no explícito, ajustado por tabla pag 15
    'D': {'Techo': 0.38, 'Muro': 0.80, 'PisoVent': 0.60, 'Puerta': 1.7}, # Pag 15 pdf 2
    'E': {'Techo': 0.33, 'Muro': 0.60, 'PisoVent': 0.50, 'Puerta': 1.7},
    'F': {'Techo': 0.28, 'Muro': 0.45, 'PisoVent': 0.39, 'Puerta': 2.0},
    'G': {'Techo': 0.25, 'Muro': 0.40, 'PisoVent': 0.32, 'Puerta': 2.0},
    'H': {'Techo': 0.25, 'Muro': 0.30, 'PisoVent': 0.30, 'Puerta': 2.0}, # Valores conservadores basados en tendencia
    'I': {'Techo': 0.25, 'Muro': 0.30, 'PisoVent': 0.30, 'Puerta': 2.0}  # Valores conservadores
}

# Datos de Zonificación (Muestra representativa basada en ZONIFICACION-TERMICA.pdf)
# En una implementación real, esto sería un CSV completo importado.
ZONIFICACION_DB = [
    {"Region": "Metropolitana", "Comuna": "Santiago", "Zona_Base": "D", "Altitud_Limite": 2000, "Zona_Alta": "H"},
    {"Region": "Metropolitana", "Comuna": "Puente Alto", "Zona_Base": "D", "Altitud_Limite": 2000, "Zona_Alta": "H"},
    {"Region": "Metropolitana", "Comuna": "Colina", "Zona_Base": "D", "Altitud_Limite": 2000, "Zona_Alta": "H"},
    {"Region": "Valparaíso", "Comuna": "Valparaíso", "Zona_Base": "C", "Altitud_Limite": None, "Zona_Alta": None},
    {"Region": "Valparaíso", "Comuna": "Viña del Mar", "Zona_Base": "C", "Altitud_Limite": None, "Zona_Alta": None},
    {"Region": "Valparaíso", "Comuna": "Los Andes", "Zona_Base": "D", "Altitud_Limite": 2000, "Zona_Alta": "H"},
    {"Region": "Biobío", "Comuna": "Concepción", "Zona_Base": "E", "Altitud_Limite": None, "Zona_Alta": None},
    {"Region": "Biobío", "Comuna": "Los Ángeles", "Zona_Base": "F", "Altitud_Limite": None, "Zona_Alta": None},
    {"Region": "La Araucanía", "Comuna": "Temuco", "Zona_Base": "F", "Altitud_Limite": None, "Zona_Alta": None},
    {"Region": "La Araucanía", "Comuna": "Pucón", "Zona_Base": "H", "Altitud_Limite": None, "Zona_Alta": None},
    {"Region": "Los Lagos", "Comuna": "Puerto Montt", "Zona_Base": "G", "Altitud_Limite": None, "Zona_Alta": None},
    {"Region": "Magallanes", "Comuna": "Punta Arenas", "Zona_Base": "I", "Altitud_Limite": None, "Zona_Alta": None},
    {"Region": "Antofagasta", "Comuna": "Antofagasta", "Zona_Base": "A", "Altitud_Limite": 3000, "Zona_Alta": "H"}, # Simplificado
    {"Region": "Antofagasta", "Comuna": "Calama", "Zona_Base": "B", "Altitud_Limite": 3000, "Zona_Alta": "H"},
]

df_zonas = pd.DataFrame(ZONIFICACION_DB)

# Tabla de Porcentajes Máximos de Ventanas (Simplificada de Pag 69 y 70)
# Estructura: Zona -> Orientación -> U_ventana -> % Max
def get_max_window_percentage(zona, orientacion, u_ventana):
    # Lógica simplificada basada en las tablas del PDF Actualizacion_DITEC
    # Esta función simula la interpolación de las tablas complejas
    
    # Valores base para Zona D (Ejemplo Pag 70) con U <= 3.6
    if zona == 'D':
        if orientacion == 'Norte': return 77 if u_ventana <= 3.6 else 25
        if orientacion in ['Oriente', 'Poniente']: return 53 if u_ventana <= 3.6 else 15
        if orientacion == 'Sur': return 40 if u_ventana <= 3.6 else 10
    
    # Valores genéricos de seguridad para otras zonas (se debe expandir con la tabla completa)
    if zona in ['A', 'B', 'C']: return 80 # Zonas cálidas permiten más
    if zona in ['E', 'F', 'G']: return 40 # Zonas frías restringen más
    if zona in ['H', 'I']: return 30      # Zonas extremas
    
    return 40 # Default

# -----------------------------------------------------------------------------
# 2. FUNCIONES DE CÁLCULO
# -----------------------------------------------------------------------------

def calcular_resistencia_total(capas):
    """
    Calcula la resistencia térmica total Rt = Rsi + Sum(e/lambda) + Rse
    Rsi y Rse estandarizados según NCh853
    """
    rsi = 0.13 # Muros horizontal
    rse = 0.04
    r_capas = sum([c['espesor']/c['conductividad'] for c in capas])
    return rsi + r_capas + rse

def calcular_u(rt):
    return 1 / rt if rt > 0 else 0

def verificar_condensacion_simple(temp_int, hr_int, temp_ext, u_muro):
    """
    Cálculo simplificado de temperatura superficial interior para riesgo de condensación superficial.
    Basado en física de edificios estándar.
    """
    rsi = 0.13
    # Temperatura superficial interior = Ti - U * Rsi * (Ti - Te)
    t_sup_int = temp_int - (u_muro * rsi * (temp_int - temp_ext))
    
    # Cálculo Punto de Rocío (Fórmula de Magnus simplificada)
    import math
    b = 17.62
    c = 243.12
    gamma = (b * temp_int / (c + temp_int)) + math.log(hr_int / 100.0)
    punto_rocio = (c * gamma) / (b - gamma)
    
    return t_sup_int, punto_rocio

# -----------------------------------------------------------------------------
# 3. INTERFAZ DE USUARIO (STREAMLIT)
# -----------------------------------------------------------------------------

st.set_page_config(page_title="Calculadora Térmica OGUC 4.1.10", layout="wide")

# Encabezado
st.title("🇨🇱 Calculadora de Cumplimiento Térmico (Art. 4.1.10 OGUC)")
st.markdown("""
Esta aplicación permite verificar el cumplimiento de la **Actualización de la Reglamentación Térmica** (D.S. N°15 MINVU), 
vigente desde Noviembre 2025. Utiliza los criterios de Zonificación y Transmitancia Térmica de los documentos DITEC.
""")

with st.sidebar:
    st.header("1. Emplazamiento del Proyecto")
    
    regiones = df_zonas['Region'].unique()
    region_sel = st.selectbox("Región", regiones)
    
    comunas = df_zonas[df_zonas['Region'] == region_sel]['Comuna'].unique()
    comuna_sel = st.selectbox("Comuna", comunas)
    
    datos_comuna = df_zonas[df_zonas['Comuna'] == comuna_sel].iloc[0]
    
    zona_termica = datos_comuna['Zona_Base']
    
    if pd.notna(datos_comuna['Altitud_Limite']):
        altitud = st.number_input("Altitud del proyecto (msnm)", min_value=0, value=500)
        if altitud >= datos_comuna['Altitud_Limite']:
            zona_termica = datos_comuna['Zona_Alta']
            st.info(f"Debido a la altitud (>{datos_comuna['Altitud_Limite']} msnm), aplica zona de altura.")
            
    st.metric("Zona Térmica Determinada", zona_termica)
    
    st.divider()
    st.info("Nota: Esta herramienta utiliza una base de datos de muestra. Para un proyecto real, verifique la comuna en la NCh1079:2019.")

# Tabs principales
tab1, tab2, tab3 = st.tabs(["🏗️ Envolvente Opaca", "🪟 Ventanas y Ponderado", "💧 Riesgo Condensación"])

# --- TAB 1: ENVOLVENTE OPACA ---
with tab1:
    st.subheader(f"Verificación de Elementos Opacos - Zona {zona_termica}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Configuración de Elemento (Muro/Techo)")
        tipo_elemento = st.selectbox("Tipo de Elemento", ["Muro", "Techo", "Piso Ventilado"])
        
        # Constructor de capas
        st.write("Capas del elemento (de interior a exterior):")
        num_capas = st.number_input("Número de capas", min_value=1, max_value=10, value=3)
        
        capas = []
        for i in range(int(num_capas)):
            c1, c2, c3 = st.columns([3, 2, 2])
            with c1:
                mat = st.text_input(f"Material {i+1}", key=f"mat_{i}")
            with c2:
                esp = st.number_input(f"Espesor (m) {i+1}", min_value=0.001, format="%.3f", key=f"esp_{i}")
            with c3:
                cond = st.number_input(f"Conductividad (W/mK) {i+1}", min_value=0.01, format="%.3f", key=f"cond_{i}")
            
            if mat and esp and cond:
                capas.append({'material': mat, 'espesor': esp, 'conductividad': cond})
    
    with col2:
        st.markdown("### Resultados")
        if capas:
            rt_calc = calcular_resistencia_total(capas)
            u_calc = calcular_u(rt_calc)
            
            limite_u = LIMITES_U[zona_termica].get(tipo_elemento.replace(" ", ""), 0)
            
            st.metric("Resistencia Térmica Total (Rt)", f"{rt_calc:.2f} m²K/W")
            st.metric("Transmitancia Térmica (U)", f"{u_calc:.2f} W/m²K")
            st.metric("Límite Normativo (U Máx)", f"{limite_u} W/m²K")
            
            if u_calc <= limite_u:
                st.success("✅ CUMPLE con la normativa térmica.")
            else:
                st.error("❌ NO CUMPLE. Debe aumentar la aislación.")
                
            # Sobrecimientos
            if tipo_elemento == "Piso Ventilado" or tipo_elemento == "Muro":
                st.info("ℹ️ Recuerde verificar aislamiento en sobrecimientos (R100 mínimo según zona).")

# --- TAB 2: VENTANAS ---
with tab2:
    st.subheader("Cálculo de Ventanas y Promedio Ponderado ($U_{pvm}$)")
    st.markdown("Si el porcentaje de ventana supera el máximo, se debe verificar mediante el promedio ponderado ventana-muro.")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        orientacion = st.selectbox("Orientación de la Fachada", ["Norte", "Sur", "Oriente", "Poniente"])
        area_muro_total = st.number_input("Superficie Total Fachada (Muro + Ventana) [m²]", min_value=1.0)
        area_ventanas = st.number_input("Superficie de Ventanas [m²]", min_value=0.0, max_value=area_muro_total)
        
        u_ventana = st.number_input("U de la Ventana [W/m²K]", min_value=0.1, value=3.6, help="Valor típico vidrio monolítico: 5.8, DVH simple: 2.8 - 3.6")
        
        # Recuperar U del muro calculado en Tab 1 o manual
        u_muro_input = st.number_input("U del Muro Opaco [W/m²K]", value=0.8, help="Puede usar el valor calculado en la pestaña anterior")

    with col_b:
        porcentaje_real = (area_ventanas / area_muro_total) * 100
        porcentaje_max = get_max_window_percentage(zona_termica, orientacion, u_ventana)
        
        st.markdown(f"#### Análisis Fachada {orientacion}")
        st.metric("% Ventanas Real", f"{porcentaje_real:.1f}%")
        st.metric("% Máximo Permitido (Tabular)", f"{porcentaje_max}%", help=f"Basado en Zona {zona_termica} y U-ventana {u_ventana}")
        
        cumple_porcentaje = porcentaje_real <= porcentaje_max
        
        if cumple_porcentaje:
            st.success("✅ CUMPLE por porcentaje máximo.")
        else:
            st.warning("⚠️ Excede el porcentaje máximo. Verificando por Ponderado ($U_{pvm}$)...")
            
            # Cálculo del límite ponderado (Lógica simplificada aproximada a la tabla del PDF pag 70)
            # El límite del Upvm depende de la tabla de la norma. 
            # Aquí usaremos un cálculo inverso referencial: 
            # Upvm_limite ≈ (U_muro_norma * (1-%max) + U_ventana * %max)
            # Nota: El PDF da valores tabulados específicos para Upvm, aquí estimamos para la demo.
            
            u_muro_limite = LIMITES_U[zona_termica]['Muro']
            upvm_limite_estimado = (u_muro_limite * (1 - (porcentaje_max/100))) + (u_ventana * (porcentaje_max/100))
            
            # Cálculo real del proyecto
            area_opaca = area_muro_total - area_ventanas
            upvm_real = ((u_muro_input * area_opaca) + (u_ventana * area_ventanas)) / area_muro_total
            
            st.metric("U Ponderado Real ($U_{pvm}$)", f"{upvm_real:.2f} W/m²K")
            st.metric("U Ponderado Límite (Estimado)", f"{upvm_limite_estimado:.2f} W/m²K")
            
            if upvm_real <= upvm_limite_estimado:
                st.success("✅ CUMPLE mediante compensación (Promedio Ponderado).")
            else:
                st.error("❌ NO CUMPLE. Debe mejorar el vidrio o aumentar aislación del muro.")

# --- TAB 3: CONDENSACIÓN ---
with tab3:
    st.subheader("Verificación Simplificada de Riesgo de Condensación Superficial")
    st.markdown("""
    Esta herramienta realiza un chequeo básico de condensación superficial.
    *Para el cumplimiento normativo estricto, se debe utilizar la planilla oficial MINVU basada en NCh1973 que considera difusión de vapor intersticial.*
    """)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        t_int = st.number_input("Temperatura Interior (°C)", value=19.0, disabled=True, help="Fijado por norma")
    with c2:
        hr_int = st.number_input("Humedad Relativa Interior (%)", value=75.0, help="Valor crítico normativo")
    with c3:
        # Temperatura exterior crítica (media mínima) - debería venir de la BDD climática
        t_ext = st.number_input("Temperatura Exterior Diseño (°C)", value=5.0, help="Ingrese la T° media mínima de la comuna")
    
    u_elemento_cond = st.number_input("U del Elemento a evaluar [W/m²K]", value=1.8, help="Ingrese el U del muro, techo o la parte más débil (puente térmico)")
    
    if st.button("Verificar Condensación"):
        t_sup, t_rocio = verificar_condensacion_simple(t_int, hr_int, t_ext, u_elemento_cond)
        
        col_res1, col_res2 = st.columns(2)
        col_res1.metric("Temperatura de Rocío", f"{t_rocio:.2f} °C")
        col_res2.metric("Temperatura Superficial Interior", f"{t_sup:.2f} °C")
        
        if t_sup > t_rocio:
            st.success(f"✅ Sin riesgo aparente de condensación superficial (Margen: {t_sup - t_rocio:.2f}°C)")
        else:
            st.error("⚠️ RIESGO DE CONDENSACIÓN. La superficie está más fría que el punto de rocío.")
            st.markdown("**Recomendación:** Aumente la aislación térmica o disminuya los puentes térmicos.")

# Footer
st.divider()
st.caption("Desarrollado para asistencia técnica basada en la Actualización de la Reglamentación Térmica (OGUC 4.1.10). Verifique siempre con los documentos oficiales.")
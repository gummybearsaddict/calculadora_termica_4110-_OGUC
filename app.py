import streamlit as st
import pandas as pd
import numpy as np
import io
import math

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN Y CARGA DE DATOS ROBUSTA
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Calculadora Térmica OGUC & DITEC", layout="wide", page_icon="🏗️")

# URL RAW del archivo en tu repositorio GitHub
URL_GITHUB_RAW = "https://raw.githubusercontent.com/gummybearsaddict/calculadora_termica_4110-_OGUC/main/base_datos_materiales_chile.csv"
NOMBRE_ARCHIVO_LOCAL = "base_datos_materiales_chile.csv"

@st.cache_data
def cargar_base_datos():
    """
    Intenta cargar la base de datos desde 3 fuentes en orden de prioridad:
    1. Archivo local (para desarrollo o si se sube junto al script).
    2. GitHub Raw (para despliegue en nube sin el archivo).
    3. Retorna None si falla para pedir carga manual.
    """
    df = None
    
    # 1. Intentar carga LOCAL
    try:
        df = pd.read_csv(NOMBRE_ARCHIVO_LOCAL)
    except FileNotFoundError:
        pass # No está local, intentamos remoto

    # 2. Intentar carga REMOTA (GitHub)
    if df is None:
        try:
            # Usamos storage_options para evitar errores de certificado en algunos entornos, 
            # aunque pd.read_csv suele manejarlo bien directamente.
            df = pd.read_csv(URL_GITHUB_RAW)
        except Exception as e:
            # Si falla la conexión o la URL está mal
            pass 

    # 3. Procesar DataFrame si se cargó exitosamente
    if df is not None and not df.empty:
        try:
            # Normalizar columnas por si acaso
            df.columns = [c.strip() for c in df.columns]
            
            # Función para categorizar el uso si no viene explícito o para filtrar mejor
            def clasificar_uso(texto_uso):
                texto = str(texto_uso).lower()
                if any(x in texto for x in ['muro', 'tabique', 'fachada', 'siding', 'ladrillo', 'bloque', 'hormigón', 'metalcon']):
                    return 'Muro'
                elif any(x in texto for x in ['techo', 'cubierta', 'cielo', 'cercha', 'teja', 'zinc']):
                    return 'Techo'
                elif any(x in texto for x in ['piso', 'radier', 'sobrecimiento', 'losa']):
                    return 'Piso'
                else:
                    return 'General'

            if 'Uso_Recomendado' in df.columns:
                df['Filtro_Uso'] = df['Uso_Recomendado'].apply(clasificar_uso)
            else:
                df['Filtro_Uso'] = 'General'
                
            return df
        except Exception as e:
            st.error(f"Error procesando la estructura del CSV: {e}")
            return None
            
    return None

# Ejecutar carga
df_materiales = cargar_base_datos()

# -----------------------------------------------------------------------------
# 2. CONSTANTES NORMATIVAS (OGUC / DITEC)
# -----------------------------------------------------------------------------
LIMITES_U = {
    'A': {'Techo': 0.84, 'Muro': 2.10, 'PisoVent': 3.60},
    'B': {'Techo': 0.47, 'Muro': 0.80, 'PisoVent': 0.70},
    'C': {'Techo': 0.38, 'Muro': 0.60, 'PisoVent': 0.60},
    'D': {'Techo': 0.38, 'Muro': 0.80, 'PisoVent': 0.60},
    'E': {'Techo': 0.33, 'Muro': 0.60, 'PisoVent': 0.50},
    'F': {'Techo': 0.28, 'Muro': 0.45, 'PisoVent': 0.39},
    'G': {'Techo': 0.25, 'Muro': 0.40, 'PisoVent': 0.32},
    'H': {'Techo': 0.25, 'Muro': 0.30, 'PisoVent': 0.30},
    'I': {'Techo': 0.25, 'Muro': 0.30, 'PisoVent': 0.30}
}

# Base de datos simplificada de zonificación (Se debería expandir)
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
    {"Region": "Antofagasta", "Comuna": "Antofagasta", "Zona_Base": "A", "Altitud_Limite": 3000, "Zona_Alta": "H"},
    {"Region": "Antofagasta", "Comuna": "Calama", "Zona_Base": "B", "Altitud_Limite": 3000, "Zona_Alta": "H"},
]
df_zonas = pd.DataFrame(ZONIFICACION_DB)

# -----------------------------------------------------------------------------
# 3. FUNCIONES UTILITARIAS
# -----------------------------------------------------------------------------

def get_max_window_percentage(zona, orientacion, u_ventana):
    """
    Retorna el % máximo de ventana permitido (Simplificación de tablas DITEC).
    """
    limites_base = {'Norte': 75, 'Oriente': 50, 'Poniente': 50, 'Sur': 40}
    base = limites_base.get(orientacion, 40)
    
    # Ajuste simple según severidad de la zona
    if zona in ['A', 'B', 'C']: 
        return min(100, base + 20)
    if zona in ['H', 'I']: 
        return max(15, base - 20)
    
    # Si la ventana es muy mala (U alto), castigar porcentaje
    if u_ventana > 3.6:
        return max(10, base - 15)
        
    return base

def generar_excel_ventanas(lista_ventanas, zona, proyecto_info):
    """Genera un archivo Excel en memoria para descargar."""
    output = io.BytesIO()
    # Usamos xlsxwriter como motor
    with pd.ExcelWriter(output, engine='xlsxwriter') as workbook:
        df = pd.DataFrame(lista_ventanas)
        
        # --- Hoja 1: Resumen ---
        ws_resumen = workbook.book.add_worksheet('Resumen Proyecto')
        format_bold = workbook.book.add_format({'bold': True})
        
        ws_resumen.write(0, 0, "Nombre Proyecto:", format_bold)
        ws_resumen.write(0, 1, proyecto_info.get('nombre', 'Sin Nombre'))
        ws_resumen.write(1, 0, "Zona Térmica:", format_bold)
        ws_resumen.write(1, 1, zona)
        ws_resumen.write(2, 0, "Comuna:", format_bold)
        ws_resumen.write(2, 1, proyecto_info.get('comuna', '-'))
        
        # --- Hoja 2: Detalle ---
        if not df.empty:
            df.to_excel(workbook, sheet_name='Calculo_Ventanas', index=False)
            ws_datos = workbook.sheets['Calculo_Ventanas']
            ws_datos.set_column('A:Z', 18) # Ajustar ancho columnas
            
    return output.getvalue()

# -----------------------------------------------------------------------------
# 4. INTERFAZ DE USUARIO (SIDEBAR)
# -----------------------------------------------------------------------------
st.title("🇨🇱 Calculadora Térmica Avanzada (OGUC 4.1.10)")
st.markdown("""
Herramienta de verificación normativa para **Envolvente Térmica** y **Complejo Ventana**.
Integra base de datos de materiales y generación de reportes DITEC.
""")

with st.sidebar:
    st.header("1. Emplazamiento")
    regiones = df_zonas['Region'].unique()
    region_sel = st.selectbox("Región", regiones)
    
    comunas = df_zonas[df_zonas['Region'] == region_sel]['Comuna'].unique()
    comuna_sel = st.selectbox("Comuna", comunas)
    
    datos_comuna = df_zonas[df_zonas['Comuna'] == comuna_sel].iloc[0]
    zona_termica = datos_comuna['Zona_Base']
    
    altitud = st.number_input("Altitud (msnm)", 0, 5000, 500)
    if pd.notna(datos_comuna['Altitud_Limite']) and altitud >= datos_comuna['Altitud_Limite']:
        zona_termica = datos_comuna['Zona_Alta']
        st.info(f"Zona ajustada por altitud a: **{zona_termica}**")
    
    st.metric("Zona Térmica Vigente", zona_termica)
    
    st.divider()
    st.header("2. Datos Proyecto")
    nom_proyecto = st.text_input("Nombre del Proyecto", "Mi Proyecto")
    
    # --- FALLBACK CARGA MANUAL ---
    if df_materiales is None or df_materiales.empty:
        st.error("⚠️ No se pudo cargar la base de datos automáticamente.")
        st.markdown("Por favor, sube el archivo `base_datos_materiales_chile.csv`:")
        uploaded_file = st.file_uploader("Cargar CSV Materiales", type="csv")
        if uploaded_file:
            df_materiales = pd.read_csv(uploaded_file)
            # Replicar lógica de clasificación
            def clasificar_uso_manual(t):
                t = str(t).lower()
                if any(x in t for x in ['muro','ladrillo']): return 'Muro'
                if any(x in t for x in ['techo','cubierta']): return 'Techo'
                if any(x in t for x in ['piso','radier']): return 'Piso'
                return 'General'
            df_materiales['Filtro_Uso'] = df_materiales['Uso_Recomendado'].apply(clasificar_uso_manual)
            st.success("Base de datos cargada.")
            st.rerun()

# -----------------------------------------------------------------------------
# 5. PESTAÑAS PRINCIPALES
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["🧱 Envolvente Opaca", "🪟 Ventanas (Formulario)", "💧 Riesgo Condensación"])

# =============================================================================
# TAB 1: CALCULO OPACO
# =============================================================================
with tab1:
    st.subheader(f"Verificación Elementos Opacos - Zona {zona_termica}")
    
    if df_materiales is not None:
        col_input, col_result = st.columns([2, 1])
        
        with col_input:
            tipo_elem = st.selectbox("Elemento a calcular", ["Muro", "Techo", "Piso Ventilado"])
            # Filtro para la DB
            mapa_uso = {'Muro': 'Muro', 'Techo': 'Techo', 'Piso Ventilado': 'Piso'}
            filtro_uso_actual = mapa_uso.get(tipo_elem, 'General')
            
            st.markdown("##### Capas del Elemento")
            if 'capas_opaco' not in st.session_state:
                st.session_state['capas_opaco'] = [{'mat': '', 'esp': 0.1, 'cond': 1.0}]
            
            n_capas = st.number_input("N° Capas", 1, 10, len(st.session_state['capas_opaco']))
            
            # Ajustar tamaño lista
            if len(st.session_state['capas_opaco']) < n_capas:
                for _ in range(n_capas - len(st.session_state['capas_opaco'])):
                    st.session_state['capas_opaco'].append({})
            elif len(st.session_state['capas_opaco']) > n_capas:
                st.session_state['capas_opaco'] = st.session_state['capas_opaco'][:n_capas]
            
            capas_para_calculo = []
            
            for i in range(n_capas):
                st.markdown(f"**Capa {i+1}**")
                c1, c2, c3, c4 = st.columns([3, 3, 2, 2])
                
                # Filtrar DF
                df_filt = df_materiales[df_materiales['Filtro_Uso'] == filtro_uso_actual]
                # Si queda vacío (ej. no hay pisos), usar todo
                if df_filt.empty: df_filt = df_materiales
                
                categorias = ['Personalizado'] + sorted(list(df_filt['Categoria_General'].unique()))
                
                with c1:
                    cat_sel = st.selectbox(f"Cat {i+1}", categorias, key=f"c_cat_{i}")
                
                with c2:
                    if cat_sel == 'Personalizado':
                        nom_mat = st.text_input(f"Nombre {i+1}", key=f"c_nom_{i}")
                        val_cond_def = 1.0
                    else:
                        mats = df_filt[df_filt['Categoria_General'] == cat_sel]
                        dict_mats = dict(zip(mats['Producto_Comercial'], mats['Conductividad_W_mK']))
                        nom_mat = st.selectbox(f"Mat {i+1}", list(dict_mats.keys()), key=f"c_mat_{i}")
                        # Intentar parsear el valor de conductividad (a veces viene como rango string)
                        try:
                            val_str = str(dict_mats[nom_mat]).replace(',', '.')
                            # Si hay rango "0.03 - 0.04", tomamos el mayor (más desfavorable)
                            if '-' in val_str:
                                val_cond_def = float(val_str.split('-')[-1])
                            else:
                                val_cond_def = float(val_str)
                        except:
                            val_cond_def = 1.0

                with c3:
                    cond = st.number_input(f"λ (W/mK)", value=val_cond_def, format="%.3f", key=f"c_cond_{i}")
                
                with c4:
                    esp = st.number_input(f"Esp (m)", value=0.01, format="%.3f", key=f"c_esp_{i}")
                
                if esp > 0 and cond > 0:
                    capas_para_calculo.append({'e': esp, 'cond': cond})

        with col_result:
            st.markdown("### Resultados")
            if capas_para_calculo:
                rsi = 0.10 if tipo_elem == 'Techo' else 0.13 # NCh853
                rse = 0.04
                r_capas = sum([c['e']/c['cond'] for c in capas_para_calculo])
                rt = rsi + r_capas + rse
                u_final = 1 / rt
                
                limite = LIMITES_U[zona_termica].get(tipo_elem.replace(" ", ""), 99)
                
                st.metric("Resistencia Total ($R_t$)", f"{rt:.2f} m²K/W")
                st.metric("Transmitancia ($U$)", f"{u_final:.2f} W/m²K")
                st.metric(f"Límite Zona {zona_termica}", f"{limite} W/m²K")
                
                if u_final <= limite:
                    st.success("✅ CUMPLE NORMATIVA")
                else:
                    st.error("❌ NO CUMPLE - Aumentar aislación")
            else:
                st.warning("Ingrese espesores válidos.")
    else:
        st.warning("Esperando base de datos...")

# =============================================================================
# TAB 2: VENTANAS (FORMULARIO DITEC)
# =============================================================================
with tab2:
    st.subheader("Cálculo y Reporte de Ventanas")
    
    if 'ventanas' not in st.session_state:
        st.session_state['ventanas'] = []
        
    # Formulario de Ingreso
    with st.expander("➕ Agregar Nueva Ventana", expanded=True):
        col_v1, col_v2, col_v3 = st.columns(3)
        with col_v1:
            v_id = st.text_input("ID / Código", f"V-{len(st.session_state['ventanas'])+1}")
            v_ori = st.selectbox("Orientación", ["Norte", "Sur", "Oriente", "Poniente"])
        with col_v2:
            v_w = st.number_input("Ancho (m)", 0.1, 10.0, 1.2)
            v_h = st.number_input("Alto (m)", 0.1, 10.0, 1.2)
            v_area = v_w * v_h
            st.caption(f"Área Ventana: {v_area:.2f} m²")
        with col_v3:
            v_u_win = st.number_input("U Ventana ($U_w$)", 0.1, 7.0, 2.8, help="Valor combinado vidrio+marco")
            v_muro_total = st.number_input("Superficie Total Fachada (m²)", v_area, 200.0, v_area*3)
            v_u_muro = st.number_input("U Muro Opaco", 0.1, 5.0, 0.6)
            
        if st.button("Agregar a la Lista"):
            porc_real = (v_area / v_muro_total) * 100
            porc_max = get_max_window_percentage(zona_termica, v_ori, v_u_win)
            
            # Cálculo Ponderado Referencial para esa fachada
            area_opaca = v_muro_total - v_area
            u_pond = ((v_u_win * v_area) + (v_u_muro * area_opaca)) / v_muro_total
            
            estado = "CUMPLE (% Base)" if porc_real <= porc_max else "VERIFICAR PONDERADO"
            
            st.session_state['ventanas'].append({
                "ID": v_id,
                "Orientacion": v_ori,
                "Dimensiones": f"{v_w}x{v_h}",
                "Area_Ventana": v_area,
                "Area_Fachada": v_muro_total,
                "%_Real": round(porc_real, 1),
                "%_Max_Tabla": porc_max,
                "U_Ventana": v_u_win,
                "U_Muro": v_u_muro,
                "U_Ponderado_Fachada": round(u_pond, 2),
                "Estado": estado
            })
            st.success(f"Ventana {v_id} agregada.")
            
    # Tabla Resultados
    st.divider()
    if st.session_state['ventanas']:
        df_v = pd.DataFrame(st.session_state['ventanas'])
        st.dataframe(df_v, use_container_width=True)
        
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            excel_file = generar_excel_ventanas(st.session_state['ventanas'], zona_termica, {'nombre': nom_proyecto, 'comuna': comuna_sel})
            st.download_button(
                "💾 Descargar Reporte Excel",
                data=excel_file,
                file_name=f"Reporte_Ventanas_{nom_proyecto}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with c_btn2:
            if st.button("🗑️ Borrar Lista"):
                st.session_state['ventanas'] = []
                st.rerun()
    else:
        st.info("No hay ventanas registradas.")

# =============================================================================
# TAB 3: CONDENSACIÓN
# =============================================================================
with tab3:
    st.subheader("Análisis de Riesgo de Condensación Superficial")
    st.markdown("Basado en criterio de Temperatura de Rocío (NCh1973)")
    
    col_cond1, col_cond2 = st.columns(2)
    
    with col_cond1:
        st.markdown("**Condiciones Interiores**")
        t_int = st.number_input("Temp. Interior (°C)", value=20.0, disabled=True, help="Estándar habitacional")
        hr_int = st.slider("Humedad Relativa Interior (%)", 30, 90, 75, help="75% es el valor crítico normativo")
        
        st.markdown("**Condiciones Exteriores**")
        t_ext = st.number_input("Temp. Exterior Diseño (°C)", -20.0, 20.0, 5.0, help="Temperatura media mínima del lugar")
        
        u_elemento = st.number_input("U del Elemento a Evaluar (W/m²K)", 0.1, 5.0, 1.8)
    
    with col_cond2:
        # Cálculo
        # 1. T Superficial Interior
        # Tsi = Ti - U * Rsi * (Ti - Te)
        rsi_cond = 0.13 # Muro
        t_si = t_int - (u_elemento * rsi_cond * (t_int - t_ext))
        
        # 2. Punto de Rocío (Magnus)
        # Tdp = (c * gamma) / (b - gamma)
        b_const = 17.62
        c_const = 243.12
        gamma = (b_const * t_int / (c_const + t_int)) + math.log(hr_int / 100.0)
        t_rocio = (c_const * gamma) / (b_const - gamma)
        
        st.metric("Temp. Superficial Interior (Tsi)", f"{t_si:.2f} °C")
        st.metric("Punto de Rocío (Tdp)", f"{t_rocio:.2f} °C")
        
        diff = t_si - t_rocio
        
        if diff > 0:
            st.success(f"✅ **NO CONDENSA** (Margen: {diff:.2f}°C)")
            st.caption("La superficie está más caliente que el punto de rocío.")
        else:
            st.error(f"⚠️ **RIESGO DE CONDENSACIÓN**")
            st.caption("El vapor de agua condensará en la superficie fría del muro/vidrio.")
            st.markdown("💡 **Solución:** Mejore la aislación (baje el U) o ventile para bajar la humedad.")

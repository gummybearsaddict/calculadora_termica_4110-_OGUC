import streamlit as st
import pandas as pd
import numpy as np
import io
import math
import re

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN Y CARGA DE DATOS ROBUSTA
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Calculadora Térmica OGUC & DITEC", layout="wide", page_icon="🏗️")

# URL RAW del archivo en tu repositorio GitHub
URL_GITHUB_RAW = "https://raw.githubusercontent.com/gummybearsaddict/calculadora_termica_4110-_OGUC/main/base_datos_materiales_chile.csv"
NOMBRE_ARCHIVO_LOCAL = "base_datos_materiales_chile.csv"

def procesar_dato_numerico(valor, es_espesor=False):
    """
    Extrae el primer valor numérico válido de una cadena de texto.
    Maneja formatos como: "140", "50 a 100", "Variable", "0.043 (Aislante)".
    Si es espesor (es_espesor=True), asume que viene en mm y convierte a metros.
    """
    if pd.isna(valor) or valor == "":
        return 0.1 if es_espesor else 1.0 # Valores por defecto seguros
    
    val_str = str(valor).replace(',', '.')
    
    # Buscar todos los números (enteros o decimales)
    numeros = re.findall(r"[-+]?\d*\.\d+|\d+", val_str)
    
    if numeros:
        try:
            # Tomamos el primer número encontrado como base
            numero = float(numeros[0])
            
            # Lógica específica para espesores (mm -> m)
            if es_espesor:
                # Si el CSV dice "Variable", retornamos un default reconocible
                if "variable" in val_str.lower():
                    return 0.1
                return numero / 1000.0
            
            # Lógica para conductividad (Rangos)
            # Si hay un rango "0.03 - 0.04", tomamos el mayor (más conservador para cálculo de U)
            if len(numeros) > 1 and '-' in val_str:
                return max([float(n) for n in numeros])
            
            return numero
        except ValueError:
            pass
            
    return 0.1 if es_espesor else 1.0

@st.cache_data
def cargar_base_datos():
    df = None
    
    # 1. Intentar carga LOCAL
    try:
        df = pd.read_csv(NOMBRE_ARCHIVO_LOCAL)
    except FileNotFoundError:
        pass 

    # 2. Intentar carga REMOTA
    if df is None:
        try:
            df = pd.read_csv(URL_GITHUB_RAW)
        except Exception:
            pass 

    # 3. Procesar DataFrame
    if df is not None and not df.empty:
        try:
            df.columns = [c.strip() for c in df.columns]
            
            # Normalizar columnas clave
            col_cond = next((c for c in df.columns if 'Conductividad' in c), None)
            col_esp = next((c for c in df.columns if 'Espesor' in c), None)
            
            if col_cond and col_esp:
                # Pre-calcular valores limpios para usar en la UI
                df['Valor_K'] = df[col_cond].apply(lambda x: procesar_dato_numerico(x, es_espesor=False))
                df['Valor_E'] = df[col_esp].apply(lambda x: procesar_dato_numerico(x, es_espesor=True))
            
            # Clasificación de uso
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
            st.error(f"Error procesando CSV: {e}")
            return None
            
    return None

df_materiales = cargar_base_datos()

# -----------------------------------------------------------------------------
# 2. CONSTANTES NORMATIVAS
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
    limites_base = {'Norte': 75, 'Oriente': 50, 'Poniente': 50, 'Sur': 40}
    base = limites_base.get(orientacion, 40)
    if zona in ['A', 'B', 'C']: return min(100, base + 20)
    if zona in ['H', 'I']: return max(15, base - 20)
    if u_ventana > 3.6: return max(10, base - 15)
    return base

def generar_excel_ventanas(lista_ventanas, zona, proyecto_info):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as workbook:
        df = pd.DataFrame(lista_ventanas)
        ws_resumen = workbook.book.add_worksheet('Resumen Proyecto')
        format_bold = workbook.book.add_format({'bold': True})
        
        ws_resumen.write(0, 0, "Nombre Proyecto:", format_bold)
        ws_resumen.write(0, 1, proyecto_info.get('nombre', 'Sin Nombre'))
        ws_resumen.write(1, 0, "Zona Térmica:", format_bold)
        ws_resumen.write(1, 1, zona)
        ws_resumen.write(2, 0, "Comuna:", format_bold)
        ws_resumen.write(2, 1, proyecto_info.get('comuna', '-'))
        
        if not df.empty:
            df.to_excel(workbook, sheet_name='Calculo_Ventanas', index=False)
            ws_datos = workbook.sheets['Calculo_Ventanas']
            ws_datos.set_column('A:Z', 18)
            
    return output.getvalue()

# -----------------------------------------------------------------------------
# 4. INTERFAZ DE USUARIO
# -----------------------------------------------------------------------------
st.title("🇨🇱 Calculadora Térmica Avanzada (OGUC 4.1.10)")
st.markdown("""
Herramienta de verificación normativa para **Envolvente Térmica** y **Complejo Ventana**.
Integra base de datos de materiales y generación de reportes DITEC.
""")

with st.sidebar:
    st.header("1. Emplazamiento")
    regiones = sorted(df_zonas['Region'].unique())
    region_sel = st.selectbox("Región", regiones)
    
    comunas = sorted(df_zonas[df_zonas['Region'] == region_sel]['Comuna'].unique())
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
    
    if df_materiales is None or df_materiales.empty:
        st.error("⚠️ Error base de datos.")
        uploaded_file = st.file_uploader("Cargar CSV Manual", type="csv")
        if uploaded_file:
            df_materiales = pd.read_csv(uploaded_file)
            st.rerun()

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
            mapa_uso = {'Muro': 'Muro', 'Techo': 'Techo', 'Piso Ventilado': 'Piso'}
            filtro_uso_actual = mapa_uso.get(tipo_elem, 'General')
            
            st.markdown("##### Capas del Elemento")
            if 'capas_opaco' not in st.session_state:
                st.session_state['capas_opaco'] = [{'mat': '', 'esp': 0.1, 'cond': 1.0}]
            
            n_capas = st.number_input("N° Capas", 1, 10, len(st.session_state['capas_opaco']))
            
            # Sincronizar tamaño lista
            if len(st.session_state['capas_opaco']) < n_capas:
                for _ in range(n_capas - len(st.session_state['capas_opaco'])):
                    st.session_state['capas_opaco'].append({})
            elif len(st.session_state['capas_opaco']) > n_capas:
                st.session_state['capas_opaco'] = st.session_state['capas_opaco'][:n_capas]
            
            capas_para_calculo = []
            
            for i in range(n_capas):
                st.markdown(f"**Capa {i+1}**")
                c1, c2, c3, c4 = st.columns([3, 3, 2, 2])
                
                # Filtrado inteligente
                df_filt = df_materiales[df_materiales['Filtro_Uso'] == filtro_uso_actual]
                if df_filt.empty: df_filt = df_materiales
                
                categorias = ['Personalizado'] + sorted(list(df_filt['Categoria_General'].unique()))
                
                with c1:
                    cat_sel = st.selectbox(f"Categoría", categorias, key=f"c_cat_{i}", label_visibility="collapsed")
                
                with c2:
                    if cat_sel == 'Personalizado':
                        nom_mat = st.text_input(f"Material", key=f"c_nom_{i}", label_visibility="collapsed", placeholder="Nombre")
                        val_cond_def = 1.0
                        val_esp_def = 0.01
                    else:
                        mats = df_filt[df_filt['Categoria_General'] == cat_sel]
                        # Diccionario ahora guarda (Conductividad, Espesor)
                        dict_mats = {row['Producto_Comercial']: (row['Valor_K'], row['Valor_E']) for _, row in mats.iterrows()}
                        
                        nom_mat = st.selectbox(f"Material", list(dict_mats.keys()), key=f"c_mat_{i}", label_visibility="collapsed")
                        
                        # Extraer valores pre-calculados
                        datos_mat = dict_mats.get(nom_mat, (1.0, 0.01))
                        val_cond_def = datos_mat[0]
                        val_esp_def = datos_mat[1]

                with c3:
                    cond = st.number_input(f"λ (W/mK)", value=val_cond_def, format="%.3f", key=f"c_cond_{i}", step=0.01)
                
                with c4:
                    esp = st.number_input(f"Esp (m)", value=val_esp_def, format="%.3f", key=f"c_esp_{i}", step=0.01)
                
                if esp > 0 and cond > 0:
                    capas_para_calculo.append({'e': esp, 'cond': cond})

        with col_result:
            st.markdown("### Resultados")
            if capas_para_calculo:
                rsi = 0.10 if tipo_elem == 'Techo' else 0.13
                rse = 0.04
                r_capas = sum([c['e']/c['cond'] for c in capas_para_calculo])
                rt = rsi + r_capas + rse
                u_final = 1 / rt if rt > 0 else 0
                
                limite = LIMITES_U[zona_termica].get(tipo_elem.replace(" ", ""), 99)
                
                st.metric("Resistencia Total ($R_t$)", f"{rt:.2f} m²K/W")
                st.metric("Transmitancia ($U$)", f"{u_final:.2f} W/m²K")
                st.metric(f"Límite Zona {zona_termica}", f"{limite} W/m²K")
                
                if u_final <= limite:
                    st.success("✅ CUMPLE")
                else:
                    st.error("❌ NO CUMPLE")
                    dif = (1/limite) - rt if limite > 0 else 0
                    if dif > 0:
                        st.caption(f"Falta resistencia: {dif:.2f} m²K/W")
    else:
        st.info("Cargando base de datos...")

# =============================================================================
# TAB 2: VENTANAS
# =============================================================================
with tab2:
    st.subheader("Cálculo y Reporte de Ventanas")
    if 'ventanas' not in st.session_state: st.session_state['ventanas'] = []
        
    with st.expander("➕ Agregar Nueva Ventana", expanded=True):
        col_v1, col_v2, col_v3 = st.columns(3)
        with col_v1:
            v_id = st.text_input("ID", f"V-{len(st.session_state['ventanas'])+1}")
            v_ori = st.selectbox("Orientación", ["Norte", "Sur", "Oriente", "Poniente"])
        with col_v2:
            v_w = st.number_input("Ancho (m)", 0.1, 10.0, 1.2)
            v_h = st.number_input("Alto (m)", 0.1, 10.0, 1.2)
            v_area = v_w * v_h
        with col_v3:
            v_u_win = st.number_input("U Ventana ($U_w$)", 0.1, 7.0, 2.8)
            v_muro_total = st.number_input("Sup. Fachada Total (m²)", v_area, 500.0, max(v_area*3, 10.0))
            v_u_muro = st.number_input("U Muro Opaco", 0.1, 5.0, 0.6)
            
        if st.button("Agregar a la Lista"):
            porc_real = (v_area / v_muro_total) * 100
            porc_max = get_max_window_percentage(zona_termica, v_ori, v_u_win)
            area_opaca = v_muro_total - v_area
            u_pond = ((v_u_win * v_area) + (v_u_muro * area_opaca)) / v_muro_total
            estado = "CUMPLE" if porc_real <= porc_max else "VERIFICAR PONDERADO"
            
            st.session_state['ventanas'].append({
                "ID": v_id, "Orientacion": v_ori, "Dimensiones": f"{v_w}x{v_h}",
                "Area_Ventana": v_area, "Area_Fachada": v_muro_total,
                "%_Real": round(porc_real, 1), "%_Max": porc_max,
                "U_Win": v_u_win, "U_Muro": v_u_muro, "U_Pond": round(u_pond, 2), "Estado": estado
            })
            st.success("Agregada")
            
    if st.session_state['ventanas']:
        df_v = pd.DataFrame(st.session_state['ventanas'])
        st.dataframe(df_v, use_container_width=True)
        excel_file = generar_excel_ventanas(st.session_state['ventanas'], zona_termica, {'nombre': nom_proyecto, 'comuna': comuna_sel})
        st.download_button("💾 Descargar Excel", excel_file, f"Ventanas_{nom_proyecto}.xlsx")
        if st.button("Borrar Lista"):
            st.session_state['ventanas'] = []
            st.rerun()

# =============================================================================
# TAB 3: CONDENSACIÓN
# =============================================================================
with tab3:
    st.subheader("Análisis Condensación Superficial")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        t_int = 20.0
        hr_int = st.slider("HR Interior (%)", 40, 90, 75)
        t_ext = st.number_input("T° Exterior Diseño", -20.0, 20.0, 5.0)
        u_elem = st.number_input("U Elemento (W/m²K)", 0.1, 5.0, 1.8)
    with col_c2:
        rsi = 0.13
        t_si = t_int - (u_elem * rsi * (t_int - t_ext))
        b, c = 17.62, 243.12
        gamma = (b * t_int / (c + t_int)) + math.log(hr_int / 100.0)
        t_rocio = (c * gamma) / (b - gamma)
        
        st.metric("T° Superficial", f"{t_si:.1f}°C")
        st.metric("T° Rocío", f"{t_rocio:.1f}°C")
        if t_si > t_rocio:
            st.success("✅ NO CONDENSA")
        else:
            st.error("⚠️ RIESGO CONDENSACIÓN")

import streamlit as st
import pandas as pd
import numpy as np
import io

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN Y CARGA DE DATOS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Calculadora Térmica OGUC & DITEC", layout="wide", page_icon="🏗️")

# Cargar base de datos de materiales
@st.cache_data
def cargar_base_datos():
    try:
        # Intentar cargar el archivo CSV adjunto
        df = pd.read_csv("base_datos_materiales_chile.csv")
        
        # Función para categorizar el uso si no viene explícito
        def clasificar_uso(texto_uso):
            texto = str(texto_uso).lower()
            if any(x in texto for x in ['muro', 'tabique', 'fachada', 'siding', 'ladrillo', 'bloque']):
                return 'Muro'
            elif any(x in texto for x in ['techo', 'cubierta', 'cielo', 'cercha', 'teja']):
                return 'Techo'
            elif any(x in texto for x in ['piso', 'radier', 'sobrecimiento', 'losa']):
                return 'Piso'
            else:
                return 'General'

        # Crear columna de filtro simplificado
        df['Filtro_Uso'] = df['Uso_Recomendado'].apply(clasificar_uso)
        return df
    except FileNotFoundError:
        st.error("⚠️ No se encontró el archivo 'base_datos_materiales_chile.csv'. Asegúrate de que esté en la misma carpeta.")
        # Retornar un DataFrame vacío o genérico para evitar crash
        return pd.DataFrame(columns=['Categoria_General', 'Producto_Comercial', 'Conductividad_W_mK', 'Filtro_Uso'])

df_materiales = cargar_base_datos()

# Constantes Normativas (Simplificado)
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
    {"Region": "Valparaíso", "Comuna": "Viña del Mar", "Zona_Base": "C", "Altitud_Limite": None, "Zona_Alta": None},
    {"Region": "Biobío", "Comuna": "Concepción", "Zona_Base": "E", "Altitud_Limite": None, "Zona_Alta": None},
    {"Region": "La Araucanía", "Comuna": "Temuco", "Zona_Base": "F", "Altitud_Limite": None, "Zona_Alta": None},
    {"Region": "Magallanes", "Comuna": "Punta Arenas", "Zona_Base": "I", "Altitud_Limite": None, "Zona_Alta": None},
    # Se puede extender...
]
df_zonas = pd.DataFrame(ZONIFICACION_DB)

# -----------------------------------------------------------------------------
# 2. FUNCIONES UTILITARIAS
# -----------------------------------------------------------------------------

def get_max_window_percentage(zona, orientacion, u_ventana):
    # Lógica simplificada de tablas DITEC
    limites = {
        'Norte': 75, 'Oriente': 50, 'Poniente': 50, 'Sur': 40
    }
    base = limites.get(orientacion, 40)
    # Ajuste simple por zona (en realidad es una tabla compleja)
    if zona in ['A','B','C']: return min(100, base + 20)
    if zona in ['H','I']: return max(15, base - 20)
    return base

def generar_excel_ventanas(lista_ventanas, zona, proyecto_info):
    """Genera un archivo Excel descargable con los datos."""
    output = io.BytesIO()
    workbook = pd.ExcelWriter(output, engine='xlsxwriter')
    
    # DataFrame de Ventanas
    df = pd.DataFrame(lista_ventanas)
    
    # Hoja 1: Resumen General
    worksheet_resumen = workbook.book.add_worksheet('Resumen Proyecto')
    worksheet_resumen.write(0, 0, "Proyecto:")
    worksheet_resumen.write(0, 1, proyecto_info.get('nombre', 'Sin Nombre'))
    worksheet_resumen.write(1, 0, "Zona Térmica:")
    worksheet_resumen.write(1, 1, zona)
    
    # Hoja 2: Detalle Ventanas
    df.to_excel(workbook, sheet_name='Calculo_Ventanas', index=False)
    
    # Formato condicional o ajustes de ancho podrían ir aquí
    worksheet = workbook.sheets['Calculo_Ventanas']
    worksheet.set_column('A:Z', 15)
    
    workbook.close()
    return output.getvalue()

# -----------------------------------------------------------------------------
# 3. INTERFAZ DE USUARIO
# -----------------------------------------------------------------------------

st.title("🇨🇱 Calculadora Térmica Avanzada (OGUC 4.1.10)")
st.caption("Verificación de Envolvente y Generación de Formulario Ventanas DITEC")

# --- SIDEBAR: DATOS GENERALES ---
with st.sidebar:
    st.header("📍 Ubicación del Proyecto")
    regiones = df_zonas['Region'].unique()
    region_sel = st.selectbox("Región", regiones)
    comunas = df_zonas[df_zonas['Region'] == region_sel]['Comuna'].unique()
    comuna_sel = st.selectbox("Comuna", comunas)
    
    datos_comuna = df_zonas[df_zonas['Comuna'] == comuna_sel].iloc[0]
    zona_termica = datos_comuna['Zona_Base']
    
    altitud = st.number_input("Altitud (msnm)", 0, 5000, 500)
    if pd.notna(datos_comuna['Altitud_Limite']) and altitud >= datos_comuna['Altitud_Limite']:
        zona_termica = datos_comuna['Zona_Alta']
        st.warning(f"Zona ajustada por altitud a: {zona_termica}")
    
    st.metric("Zona Térmica", zona_termica)
    
    st.divider()
    st.header("📄 Datos Proyecto")
    nom_proyecto = st.text_input("Nombre Proyecto", "Mi Casa")

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["🧱 Elementos Opacos", "🪟 Formulario Ventanas", "💧 Condensación"])

# =============================================================================
# TAB 1: OPACOS (Base de Datos Integrada)
# =============================================================================
with tab1:
    st.subheader(f"Cálculo Transmitancia Térmica (U) - Zona {zona_termica}")
    
    col_config, col_res = st.columns([2, 1])
    
    with col_config:
        tipo_elem = st.selectbox("Elemento", ["Muro", "Techo", "Piso Ventilado"])
        # Mapeo para filtrar DB
        filtro_db = {'Muro': 'Muro', 'Techo': 'Techo', 'Piso Ventilado': 'Piso'}.get(tipo_elem, 'General')
        
        st.info("💡 Selecciona materiales de la base de datos para autocompletar la conductividad.")
        
        # Inicializar capas en session_state si no existen
        if 'capas_opaco' not in st.session_state:
            st.session_state['capas_opaco'] = [{'mat': '', 'esp': 0.1, 'cond': 1.0}]
            
        num_capas = st.number_input("Cantidad de Capas", 1, 10, len(st.session_state['capas_opaco']))
        
        # Ajustar lista
        if len(st.session_state['capas_opaco']) < num_capas:
            for _ in range(num_capas - len(st.session_state['capas_opaco'])):
                st.session_state['capas_opaco'].append({'mat': '', 'esp': 0.0, 'cond': 0.0})
        elif len(st.session_state['capas_opaco']) > num_capas:
             st.session_state['capas_opaco'] = st.session_state['capas_opaco'][:num_capas]
        
        capas_calc = []
        
        # Generar inputs dinámicos
        for i in range(num_capas):
            st.markdown(f"**Capa {i+1}**")
            c1, c2, c3, c4 = st.columns([3, 3, 2, 2])
            
            # Filtrar DB por Tipo y luego Categoria
            df_filtrado = df_materiales[df_materiales['Filtro_Uso'] == filtro_db]
            cats = ['Personalizado'] + list(df_filtrado['Categoria_General'].unique())
            
            with c1:
                cat_sel = st.selectbox(f"Categoría {i}", cats, key=f"cat_{i}")
            
            with c2:
                if cat_sel == 'Personalizado':
                    mat_nombre = st.text_input(f"Nombre {i}", key=f"nom_{i}")
                    val_cond = 1.0
                else:
                    mats_disp = df_filtrado[df_filtrado['Categoria_General'] == cat_sel]
                    # Crear lista de tuplas (Nombre, Lambda)
                    opciones_mat = dict(zip(mats_disp['Producto_Comercial'], mats_disp['Conductividad_W_mK']))
                    mat_sel = st.selectbox(f"Material {i}", list(opciones_mat.keys()), key=f"mat_sel_{i}")
                    mat_nombre = mat_sel
                    val_cond = float(opciones_mat[mat_sel]) if mat_sel else 1.0

            with c3:
                # Si viene de DB, el valor por defecto es el de la DB
                cond = st.number_input(f"λ (W/mK) {i}", value=val_cond, format="%.3f", key=f"cond_{i}")
            
            with c4:
                esp = st.number_input(f"Espesor (m) {i}", min_value=0.0, value=0.01, format="%.3f", key=f"esp_{i}")
                
            if esp > 0 and cond > 0:
                capas_calc.append({'material': mat_nombre, 'espesor': esp, 'conductividad': cond})

    with col_res:
        st.markdown("### Resultados")
        if capas_calc:
            # Rsi Rse
            rsi = 0.10 if tipo_elem == 'Techo' else 0.13 # Simplificado
            rse = 0.04
            r_capas = sum([c['espesor']/c['conductividad'] for c in capas_calc])
            rt = rsi + r_capas + rse
            u_valor = 1/rt
            
            limite = LIMITES_U[zona_termica].get(tipo_elem.replace(" ", ""), 0)
            
            st.metric("Resistencia (Rt)", f"{rt:.2f}")
            st.metric("Transmitancia (U)", f"{u_valor:.2f}")
            st.metric("Límite Zona (U máx)", f"{limite}")
            
            if u_valor <= limite:
                st.success("✅ CUMPLE")
            else:
                st.error("❌ NO CUMPLE")
                
            st.caption(f"Detalle capas: {len(capas_calc)} capas válidas.")

# =============================================================================
# TAB 2: VENTANAS (Descarga Excel)
# =============================================================================
with tab2:
    st.subheader("Gestión de Ventanas y Fachadas")
    
    if 'lista_ventanas' not in st.session_state:
        st.session_state['lista_ventanas'] = []

    # --- Formulario de Ingreso ---
    with st.expander("📝 Agregar Nueva Ventana / Fachada", expanded=True):
        c_v1, c_v2, c_v3, c_v4 = st.columns(4)
        
        with c_v1:
            v_id = st.text_input("ID Ventana", f"V-{len(st.session_state['lista_ventanas'])+1}")
            v_orient = st.selectbox("Orientación", ["Norte", "Sur", "Oriente", "Poniente"])
        
        with c_v2:
            v_ancho = st.number_input("Ancho (m)", 0.1, 10.0, 1.5)
            v_alto = st.number_input("Alto (m)", 0.1, 10.0, 1.2)
            v_area = v_ancho * v_alto
            st.caption(f"Área Ventana: {v_area:.2f} m²")
            
        with c_v3:
            v_area_muro = st.number_input("Área Total Fachada (Muro+Ventana)", 0.1, 100.0, 10.0)
            v_u_muro = st.number_input("U Muro Opaco", 0.1, 5.0, 0.8)
            
        with c_v4:
            v_u_ventana = st.number_input("U Ventana Total (Uw)", 0.1, 7.0, 2.8, help="Valor combinado Marco + Vidrio")
            
        btn_add = st.button("➕ Agregar Ventana")
        
        if btn_add:
            porc_real = (v_area / v_area_muro) * 100
            porc_max = get_max_window_percentage(zona_termica, v_orient, v_u_ventana)
            
            # Lógica simple de cumplimiento
            cumple_txt = "SI" if porc_real <= porc_max else "NO (Verificar Ponderado)"
            
            nueva_ventana = {
                "ID": v_id,
                "Orientación": v_orient,
                "Ancho (m)": v_ancho,
                "Alto (m)": v_alto,
                "Área Ventana (m2)": v_area,
                "Área Fachada (m2)": v_area_muro,
                "% Ventana": round(porc_real, 1),
                "% Máx Permitido": porc_max,
                "U Ventana": v_u_ventana,
                "U Muro": v_u_muro,
                "Cumple %": cumple_txt
            }
            st.session_state['lista_ventanas'].append(nueva_ventana)
            st.success(f"Ventana {v_id} agregada.")

    # --- Tabla de Resultados ---
    st.divider()
    if st.session_state['lista_ventanas']:
        df_ventanas = pd.DataFrame(st.session_state['lista_ventanas'])
        st.dataframe(df_ventanas, use_container_width=True)
        
        # Cálculo Ponderado Global (Ejemplo simplificado de promedio ponderado global)
        area_total_env = df_ventanas['Área Fachada (m2)'].sum()
        area_total_vidrio = df_ventanas['Área Ventana (m2)'].sum()
        area_total_opaco = area_total_env - area_total_vidrio
        
        # U Promedio Ponderado del proyecto (Simplificación didáctica)
        # Nota: La norma exige cálculo fachada por fachada o global según método.
        u_prom_vidrio = (df_ventanas['U Ventana'] * df_ventanas['Área Ventana (m2)']).sum()
        u_prom_muro = (df_ventanas['U Muro'] * (df_ventanas['Área Fachada (m2)'] - df_ventanas['Área Ventana (m2)'])).sum()
        
        if area_total_env > 0:
            u_global = (u_prom_vidrio + u_prom_muro) / area_total_env
            st.metric("U Global Ponderado (Referencial)", f"{u_global:.2f} W/m²K")
        
        # --- BOTÓN DE DESCARGA ---
        excel_data = generar_excel_ventanas(st.session_state['lista_ventanas'], zona_termica, {'nombre': nom_proyecto})
        
        st.download_button(
            label="💾 Descargar Formulario de Cálculo (.xlsx)",
            data=excel_data,
            file_name=f"Calculo_Ventanas_{nom_proyecto}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        if st.button("🗑️ Borrar Todo"):
            st.session_state['lista_ventanas'] = []
            st.rerun()
    else:
        st.info("No hay ventanas ingresadas.")

# =============================================================================
# TAB 3: CONDENSACIÓN (Sin cambios mayores)
# =============================================================================
with tab3:
    st.header("Verificación Riesgo Condensación")
    # ... (Misma lógica previa o ampliada)
    t_int = 20
    hr_int = 75
    t_ext = st.number_input("T° Exterior Crítica", -10.0, 20.0, 5.0)
    u_eval = st.number_input("U Elemento", 0.1, 5.0, 1.8)
    
    rsi = 0.13
    t_sup = t_int - (u_eval * rsi * (t_int - t_ext))
    
    # Punto de rocio (Magnus)
    import math
    b, c = 17.62, 243.12
    gamma = (b * t_int / (c + t_int)) + math.log(hr_int / 100.0)
    t_rocio = (c * gamma) / (b - gamma)
    
    c1, c2 = st.columns(2)
    c1.metric("T° Superficial Interior", f"{t_sup:.1f} °C")
    c2.metric("T° Rocío", f"{t_rocio:.1f} °C")
    
    if t_sup > t_rocio:
        st.success("✅ Sin riesgo de condensación superficial.")
    else:
        st.error("⚠️ RIESGO DE CONDENSACIÓN.")

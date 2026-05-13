import streamlit as st
import pandas as pd
import re
import io

# 1. Configuración
st.set_page_config(page_title="NOC - Reporte LTE", page_icon="📡", layout="wide")
st.title("📡 Generador de Reportes: Radioenlaces LTE")
st.markdown("Sube tus archivos CSV descargados y el inventario maestro para generar el reporte.")
st.markdown("---")

# 2. Motor de Procesamiento (Adaptado para archivos subidos)
def procesar_archivos_subidos(archivos_radio, archivo_inventario):
    if not archivos_radio:
        return None

    datos_tabla_final = []
    
    # Separar analógicos y de errores
    archivos_analog = [f for f in archivos_radio if 'Analog_Hop' in f.name]
    archivos_error = {f.name: f for f in archivos_radio if 'Radio_Hop' in f.name}
    
    for archivo_analog in archivos_analog:
        nombre_analog = archivo_analog.name
        ip_equipo = nombre_analog.split('_')[0]
        parte_central = nombre_analog.split('Analog_Hop')[0] 
        
        match_dir = re.search(r'(Dir#[\w.]+)', nombre_analog)
        match_ch = re.search(r'(Ch#\d+)', nombre_analog)
        match_slot = re.search(r'(Slot[\w\d]+)', nombre_analog)
        match_hw = re.search(r'\((.*?)\)', nombre_analog)
        
        direccion = match_dir.group(1) if match_dir else 'N/A'
        canal = match_ch.group(1) if match_ch else 'N/A'
        slot = match_slot.group(1) if match_slot else 'N/A'
        hardware = match_hw.group(1) if match_hw else 'Desconocido'
        
        identificador_enlace = f"{slot}_{direccion}_{canal}".replace('N/A_', '')
        
        # Buscar la pareja exacta en los archivos subidos
        nombre_esperado = [n for n in archivos_error.keys() if n.startswith(parte_central)]
        
        if not nombre_esperado: continue
            
        archivo_error = archivos_error[nombre_esperado[0]]

        try:
            # Leer desde la memoria (BytesIO)
            df_analog = pd.read_csv(archivo_analog)
            df_analog['Time'] = pd.to_datetime(df_analog['Time'].str.replace(' UTC', ''), format='mixed', dayfirst=True)
            df_analog_7d = df_analog.sort_values(by='Time', ascending=False).head(7)
            
            df_errores = pd.read_csv(archivo_error)
            df_errores['Time'] = pd.to_datetime(df_errores['Time'].str.replace(' UTC', ''), format='mixed', dayfirst=True)
            df_errores_7d = df_errores.sort_values(by='Time', ascending=False).head(7)
            
            datos_tabla_final.append({
                'IP_Equipo': ip_equipo,
                'Tipo_Hardware': hardware,
                'Enlace_ID': identificador_enlace,
                'Slot': slot, 'Direccion': direccion, 'Canal': canal,
                'Rx_Minimo_7d': df_analog_7d['MinimumLevel'].min(),
                'Rx_Maximo_7d': df_analog_7d['MaximumLevel'].max(),
                'UAS_Total_7d': df_errores_7d['UAS'].sum(),
                'SES_Total_7d': df_errores_7d['SES'].sum(),
                'BBE_y_ES_Total_7d': df_errores_7d['BBE'].sum() + df_errores_7d['ES'].sum()
            })
        except Exception as e:
            st.error(f"Error procesando {ip_equipo}: {e}")

    if not datos_tabla_final: return None
        
    df_final = pd.DataFrame(datos_tabla_final)
    
    # Cruce con inventario si se subió
    if archivo_inventario:
        try:
            df_inventario = pd.read_csv(archivo_inventario, sep=None, engine='python')
            df_final = pd.merge(df_final, df_inventario[['IP_Equipo', 'Enlace_ID', 'Enlace', 'Identificador']], 
                                on=['IP_Equipo', 'Enlace_ID'], how='left')
            df_final['Enlace'] = df_final['Enlace'].fillna('FALTA_EN_INVENTARIO')
            df_final['Identificador'] = df_final['Identificador'].fillna('-')
            
            if 'Enlace' in df_final.columns:
                cols = ['Enlace', 'Identificador', 'IP_Equipo', 'Tipo_Hardware', 'Enlace_ID', 'Rx_Minimo_7d', 'Rx_Maximo_7d', 'UAS_Total_7d', 'SES_Total_7d', 'BBE_y_ES_Total_7d']
                df_final = df_final[cols]
        except Exception as e:
            st.warning(f"No se pudo cruzar el inventario: {e}")
            
    return df_final

# 3. Interfaz de Usuario (Subida de Archivos)
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Sube los archivos CSV de los Radios")
    archivos_radio_subidos = st.file_uploader("Selecciona todos los archivos (Analog y Radio Hop)", accept_multiple_files=True, type=['csv'])

with col2:
    st.subheader("2. Sube el Inventario Maestro (Opcional)")
    archivo_inventario_subido = st.file_uploader("Sube Inventario_LTE.csv", type=['csv'])

if archivos_radio_subidos:
    if st.button("🚀 Generar Reporte", type="primary"):
        with st.spinner("Procesando datos..."):
            df_reporte = procesar_archivos_subidos(archivos_radio_subidos, archivo_inventario_subido)
            
            if df_reporte is not None:
                st.success(f"✅ Se procesaron {len(df_reporte)} enlaces.")
                st.dataframe(df_reporte, use_container_width=True)
                
                # Descarga
                csv = df_reporte.to_csv(index=False, sep=';', decimal=',').encode('utf-8')
                st.download_button(
                    label="📥 Descargar Reporte Consolidado (CSV)",
                    data=csv,
                    file_name='Reporte_LTE_Final.csv',
                    mime='text/csv',
                )
            else:
                st.error("No se pudieron extraer datos. Verifica que subiste las parejas correctas de archivos.")
import streamlit as st
import pandas as pd
import geopandas as gpd
import json
import requests
from io import StringIO
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide", page_title="Donation Isa / Seb")

# --- 1. CHARGEMENT ET NETTOYAGE ROBUSTE ---
@st.cache_data(ttl=3600)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRrcHwy2y4vE2boubFxFCH-3RZpIyr0DvEm0ScJBHsr6UG4EMTvAJz7oqdlRVuIpouLhoxG7l5kCjRF/pub?output=csv"
    response = requests.get(url)
    df = pd.read_csv(StringIO(response.text))
    
    # Nettoyage strict des colonnes
    df.columns = df.columns.str.strip()
    df['id_merge'] = df['id_merge'].astype(str).str.strip()
    
    # Nettoyage des numériques du CSV
    for col in ['contenance', 'Revenu_Cadastral']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('"', '').str.replace(',', '.')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    with open('commune.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Filtrage par IDs pour la performance et le zoom
    ids_to_keep = set(df['id_merge'].unique())
    features_filtered = [f for f in data['features'] if str(f['properties'].get('id')).strip() in ids_to_keep]
    
    gdf = gpd.GeoDataFrame.from_features(features_filtered)
    gdf['id'] = gdf['id'].astype(str).str.strip()
    
    # Fusion
    merged = gdf.merge(df, left_on='id', right_on='id_merge', how='left')
    
    # Remplissage des valeurs manquantes pour éviter tout crash
    merged['contenance'] = merged['contenance'].fillna(0)
    merged['Revenu_Cadastral'] = merged['Revenu_Cadastral'].fillna(0)
    merged['Nature'] = merged['Nature'].fillna('Inconnue')
    merged['IS'] = merged['IS'].fillna('F')
    
    return merged

gdf = load_data()

# --- 2. CARTE INTERACTIVE ---
st.subheader("Localisation des parcelles")
bounds = gdf.total_bounds
m = folium.Map()
m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

for _, row in gdf.iterrows():
    prop = row.get('IS', 'F')
    nom_prop = 'Isabelle' if prop == 'I' else ('Sébastien' if prop == 'S' else 'Non attribué')
    color = 'blue' if prop == 'I' else ('red' if prop == 'S' else 'gray')
    
    # Utilisation de .get() sécurisé
    popup_text = f"<b>Parcelle :</b> {row.get('Parcelle', row.get('id', 'N/A'))}<br>" \
                 f"<b>Contenance :</b> {float(row.get('contenance', 0)):.4f} ha<br>" \
                 f"<b>Valeur :</b> {float(row.get('Revenu_Cadastral', 0)):.2f}<br>" \
                 f"<b>Propriétaire :</b> {nom_prop}"
    
    folium.GeoJson(
        row.geometry,
        style_function=lambda x, col=color: {'fillColor': col, 'color': col, 'weight': 1, 'fillOpacity': 0.6},
        tooltip=folium.Tooltip(popup_text)
    ).add_to(m)

st_folium(m, width=1200, height=400)

# --- 3. TABLEAU DE BORD ---
st.subheader("Tableau de bord des attributions")
df_display = gdf.copy()
df_display['Propriétaire'] = df_display['IS'].map({'I': 'Isabelle', 'S': 'Sébastien'}).fillna('Reste à attribuer')

# Groupement robuste
summary = df_display.groupby(['Propriétaire', 'Nature'], as_index=False).agg({
    'id': 'count', 
    'contenance': 'sum', 
    'Revenu_Cadastral': 'sum'
})

# Calcul des totaux
totals = summary.groupby('Propriétaire')[['id', 'contenance', 'Revenu_Cadastral']].sum().reset_index()
totals['Nature'] = '--- TOTAL ---'
summary = pd.concat([summary, totals], ignore_index=True)
summary = summary.sort_values(['Propriétaire', 'Nature']).rename(columns={'id': 'Nb Parcelles'})

st.dataframe(summary, use_container_width=True, hide_index=True)

import streamlit as st
import pandas as pd
import geopandas as gpd
import json
import requests
from io import StringIO
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide", page_title="Donation Isa / Seb")

# --- 1. CHARGEMENT ET FUSION ---
@st.cache_data(ttl=3600)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRrcHwy2y4vE2boubFxFCH-3RZpIyr0DvEm0ScJBHsr6UG4EMTvAJz7oqdlRVuIpouLhoxG7l5kCjRF/pub?output=csv"
    response = requests.get(url)
    df = pd.read_csv(StringIO(response.text))
    
    # Nettoyage des noms et des IDs
    df.columns = df.columns.str.strip()
    df['id_merge'] = df['id_merge'].astype(str).str.strip()
    
    # Nettoyage forcé des nombres (convertit "11,02" en 11.02)
    for col in ['contenance', 'Revenu_Cadastral']:
        df[col] = df[col].astype(str).str.replace('"', '').str.replace(',', '.')
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    with open('commune.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    gdf = gpd.GeoDataFrame.from_features(data['features'])
    gdf['id'] = gdf['id'].astype(str).str.strip()
    
    # Fusion (on garde tout le GeoJSON pour ne pas perdre la carte, mais on merge)
    gdf = gdf.merge(df, left_on='id', right_on='id_merge', how='left')
    
    # Remplissage par défaut pour éviter les plantages dans le tableau
    gdf['contenance'] = gdf['contenance'].fillna(0)
    gdf['Revenu_Cadastral'] = gdf['Revenu_Cadastral'].fillna(0)
    gdf['IS'] = gdf['IS'].fillna('F')
    gdf['Nature'] = gdf['Nature'].fillna('Inconnue')
    
    return gdf

gdf = load_data()

# --- 2. CARTE ---
st.subheader("Localisation des parcelles")
# On ne zoome que sur les parcelles qui ont une correspondance dans le sheet
gdf_filtre = gdf[gdf['id_merge'].notna()]
if not gdf_filtre.empty:
    bounds = gdf_filtre.total_bounds
    m = folium.Map()
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
else:
    m = folium.Map()

for _, row in gdf.iterrows():
    if pd.isna(row['id_merge']): continue # On n'affiche que les parcelles du sheet
    
    prop = row['IS']
    nom_prop = 'Isabelle' if prop == 'I' else ('Sébastien' if prop == 'S' else 'Non attribué')
    color = 'blue' if prop == 'I' else ('red' if prop == 'S' else 'gray')
    
    popup_text = f"Parcelle: {row['Parcelle']}<br>Contenance: {row['contenance']} ha<br>Valeur: {row['Revenu_Cadastral']}<br>Propriétaire: {nom_prop}"
    
    folium.GeoJson(
        row.geometry,
        style_function=lambda x, col=color: {'fillColor': col, 'color': col, 'weight': 1, 'fillOpacity': 0.6},
        tooltip=popup_text
    ).add_to(m)

st_folium(m, width=1200, height=400)

# --- 3. TABLEAU DE BORD ---
st.subheader("Tableau de bord")
df_display = gdf[gdf['id_merge'].notna()].copy()
df_display['Propriétaire'] = df_display['IS'].map({'I': 'Isabelle', 'S': 'Sébastien'}).fillna('Reste à attribuer')

summary = df_display.groupby(['Propriétaire', 'Nature'], as_index=False).agg({'id': 'count', 'contenance': 'sum', 'Revenu_Cadastral': 'sum'})
st.dataframe(summary, use_container_width=True, hide_index=True)

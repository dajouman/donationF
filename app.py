import streamlit as st
import pandas as pd
import geopandas as gpd
import json
import requests
from io import StringIO
import folium
from streamlit_folium import st_folium

# Configuration de la page
st.set_page_config(layout="wide", page_title="Donation Isa / Seb")

# --- FONCTION DE CHARGEMENT OPTIMISÉE ---
@st.cache_data(ttl=3600)
def load_data():
    # 1. Chargement du CSV
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRrcHwy2y4vE2boubFxFCH-3RZpIyr0DvEm0ScJBHsr6UG4EMTvAJz7oqdlRVuIpouLhoxG7l5kCjRF/pub?output=csv"
    response = requests.get(url)
    response.encoding = 'utf-8'
    df = pd.read_csv(StringIO(response.text))
    df['id_merge'] = df['id_merge'].astype(str)
    
    # 2. Chargement du GeoJSON
    with open('commune.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    gdf_total = gpd.GeoDataFrame.from_features(data['features'])
    gdf_total['id'] = gdf_total['id'].astype(str)
    
    # 3. FILTRAGE INTELLIGENT : On ne garde que les parcelles du CSV
    ids_inventaire = df['id_merge'].unique().tolist()
    gdf = gdf_total[gdf_total['id'].isin(ids_inventaire)].copy()
    
    # 4. Fusion
    return gdf.merge(df, left_on='id', right_on='id_merge', how='left')

# --- INITIALISATION ---
gdf = load_data()

# --- TABLEAU DE BORD ---
st.subheader("Tableau de bord des attributions - Donation Isa / Seb")
df_display = gdf.copy()
df_display['IS'] = df_display['IS'].fillna('F')
df_display['Propriétaire'] = df_display['IS'].map({'I': 'Isabelle', 'S': 'Sébastien', 'F': 'Reste à attribuer'})

# Nettoyage colonnes numériques
for col in ['contenance', 'Revenu_Cadastral']:
    df_display[col] = pd.to_numeric(df_display[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

# Calcul résumé
summary = df_display.groupby(['Propriétaire', 'Nature'], as_index=False).agg({'id_merge': 'count', 'contenance': 'sum', 'Revenu_Cadastral': 'sum'})
totals = summary.groupby('Propriétaire')[['id_merge', 'contenance', 'Revenu_Cadastral']].sum().reset_index()
totals['Nature'] = 'TOTAL'
summary = pd.concat([summary, totals])
summary = summary.sort_values(['Propriétaire', 'Nature'])
summary = summary.rename(columns={'id_merge': 'Nombre de parcelles'})

st.table(summary)

# --- CARTE INTERACTIVE ---
st.subheader("Localisation des parcelles")
m = folium.Map(location=[gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()], zoom_start=14)

for _, row in gdf.iterrows():
    color = 'blue' if row['IS'] == 'I' else ('red' if row['IS'] == 'S' else 'gray')
    folium.GeoJson(
        row.geometry,
        style_function=lambda x, color=color: {'fillColor': color, 'color': color, 'weight': 1, 'fillOpacity': 0.6},
        tooltip=f"ID: {row['id']}<br>Nature: {row['Nature']}"
    ).add_to(m)

st_folium(m, width=1200, height=600)

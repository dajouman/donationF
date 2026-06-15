import streamlit as st
import pandas as pd
import geopandas as gpd
import json
import requests
from io import StringIO
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide", page_title="Donation Isa / Seb")

@st.cache_data(ttl=3600)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRrcHwy2y4vE2boubFxFCH-3RZpIyr0DvEm0ScJBHsr6UG4EMTvAJz7oqdlRVuIpouLhoxG7l5kCjRF/pub?output=csv"
    response = requests.get(url)
    df = pd.read_csv(StringIO(response.text))
    df['id_merge'] = df['id_merge'].astype(str)
    
    with open('commune.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    gdf_total = gpd.GeoDataFrame.from_features(data['features'])
    gdf_total['id'] = gdf_total['id'].astype(str)
    
    ids_inventaire = df['id_merge'].unique().tolist()
    gdf = gdf_total[gdf_total['id'].isin(ids_inventaire)].copy()
    return gdf.merge(df, left_on='id', right_on='id_merge', how='left')

gdf = load_data()

# --- 1. CARTE AVEC ZOOM AUTOMATIQUE ---
st.subheader("Localisation des parcelles")
# Calcul de l'emprise totale pour le zoom automatique
bounds = gdf.total_bounds # [minx, miny, maxx, maxy]
m = folium.Map()
m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

for _, row in gdf.iterrows():
    color = 'blue' if row['IS'] == 'I' else ('red' if row['IS'] == 'S' else 'gray')
    folium.GeoJson(
        row.geometry,
        style_function=lambda x, color=color: {'fillColor': color, 'color': color, 'weight': 1, 'fillOpacity': 0.6},
        tooltip=f"ID: {row['id']} - Nature: {row['Nature']}"
    ).add_to(m)
st_folium(m, width=1200, height=400)

# --- 2. FORMULAIRE ---
# ... (inchangé) ...

# --- 3. TABLEAU DE BORD TRIÉ ---
st.subheader("Tableau de bord des attributions")
df_display = gdf.copy()
df_display['IS'] = df_display['IS'].fillna('F')
df_display['Propriétaire'] = df_display['IS'].map({'I': 'Isabelle', 'S': 'Sébastien', 'F': 'Reste à attribuer'})

for col in ['contenance', 'Revenu_Cadastral']:
    df_display[col] = pd.to_numeric(df_display[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

# Logique de tri : Nature != 'TOTAL' vient avant, puis 'TOTAL'
summary = df_display.groupby(['Propriétaire', 'Nature'], as_index=False).agg({'id': 'count', 'contenance': 'sum', 'Revenu_Cadastral': 'sum'})
totals = summary.groupby('Propriétaire')[['id', 'contenance', 'Revenu_Cadastral']].sum().reset_index()
totals['Nature'] = 'TOTAL'
summary = pd.concat([summary, totals])

# Création d'une clé de tri pour forcer TOTAL en bas
summary['order'] = summary['Nature'].apply(lambda x: 1 if x == 'TOTAL' else 0)
summary = summary.sort_values(['Propriétaire', 'order', 'Nature'])
summary = summary.drop(columns=['order']).rename(columns={'id': 'Nombre de parcelles'})

st.table(summary)

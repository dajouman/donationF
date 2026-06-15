import streamlit as st
import pandas as pd
import geopandas as gpd
import json
import requests
from io import StringIO
import folium
from streamlit_folium import st_folium

# Configuration
st.set_page_config(layout="wide", page_title="Donation Isa / Seb")

# --- CHARGEMENT ---
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

# --- 1. CARTE ---
st.subheader("Localisation des parcelles")
m = folium.Map(location=[gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()], zoom_start=14)
for _, row in gdf.iterrows():
    color = 'blue' if row['IS'] == 'I' else ('red' if row['IS'] == 'S' else 'gray')
    folium.GeoJson(
        row.geometry,
        style_function=lambda x, color=color: {'fillColor': color, 'color': color, 'weight': 1, 'fillOpacity': 0.6},
        tooltip=f"ID: {row['id']} - Nature: {row['Nature']} - Contenance: {row.get('contenance', 'N/A')}"
    ).add_to(m)
st_folium(m, width=1200, height=400)

# --- 2. FORMULAIRE ---
st.subheader("Modifier une affectation")
with st.form("attribution_form"):
    col1, col2 = st.columns(2)
    # Tri de la liste des IDs pour le menu
    sorted_ids = sorted(gdf['id'].unique(), key=lambda x: (len(x), x))
    parcel_id = col1.selectbox("Choisir l'ID de la parcelle", sorted_ids)
    new_owner = col2.selectbox("Nouvelle attribution", ["I", "S", "F"])
    submit = st.form_submit_button("Appliquer la modification")

# --- 3. TABLEAU DE BORD AVEC TOTAUX ---
st.subheader("Tableau de bord des attributions")
df_display = gdf.copy()
df_display['IS'] = df_display['IS'].fillna('F')
df_display['Propriétaire'] = df_display['IS'].map({'I': 'Isabelle', 'S': 'Sébastien', 'F': 'Reste à attribuer'})

for col in ['contenance', 'Revenu_Cadastral']:
    df_display[col] = pd.to_numeric(df_display[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

# Création résumé + Totaux
summary = df_display.groupby(['Propriétaire', 'Nature'], as_index=False).agg({'id': 'count', 'contenance': 'sum', 'Revenu_Cadastral': 'sum'})
totals = summary.groupby('Propriétaire')[['id', 'contenance', 'Revenu_Cadastral']].sum().reset_index()
totals['Nature'] = 'TOTAL'
summary = pd.concat([summary, totals])
summary = summary.sort_values(['Propriétaire', 'Nature'])
summary = summary.rename(columns={'id': 'Nombre de parcelles'})

st.table(summary)

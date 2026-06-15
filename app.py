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

# --- 1. CHARGEMENT ET FILTRAGE DES DONNÉES ---
@st.cache_data(ttl=3600)
def load_data():
    # Chargement CSV
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRrcHwy2y4vE2boubFxFCH-3RZpIyr0DvEm0ScJBHsr6UG4EMTvAJz7oqdlRVuIpouLhoxG7l5kCjRF/pub?output=csv"
    response = requests.get(url)
    df = pd.read_csv(StringIO(response.text))
    df['id_merge'] = df['id_merge'].astype(str)
    
    # Chargement GeoJSON
    with open('commune.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    gdf_total = gpd.GeoDataFrame.from_features(data['features'])
    gdf_total['id'] = gdf_total['id'].astype(str)
    
    # Filtrage : On ne garde que les parcelles du CSV pour la performance
    ids_inventaire = df['id_merge'].unique().tolist()
    gdf = gdf_total[gdf_total['id'].isin(ids_inventaire)].copy()
    
    # Fusion
    return gdf.merge(df, left_on='id', right_on='id_merge', how='left')

gdf = load_data()

# --- 2. CARTE INTERACTIVE ---
st.subheader("Localisation des parcelles")
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

# --- 3. FORMULAIRE D'AFFECTATION ---
st.subheader("Modifier une affectation")
with st.form("attribution_form"):
    col1, col2 = st.columns(2)
    sorted_ids = sorted(gdf['id'].unique(), key=lambda x: (len(x), x))
    parcel_id = col1.selectbox("Choisir l'ID de la parcelle", sorted_ids)
    new_owner = col2.selectbox("Nouvelle attribution", ["I", "S", "F"])
    submit = st.form_submit_button("Appliquer la modification")

# --- 4. TABLEAU DE BORD ---
st.subheader("Tableau de bord des attributions")

# ... [Gardez tout le calcul de 'summary' identique jusqu'à la fin] ...

# AU LIEU DU .style.apply, on utilise un formatage simple
# On affiche le dataframe normalement
st.dataframe(
    summary, 
    use_container_width=True, 
    hide_index=True
)

# Optionnel : Si vous voulez vraiment mettre en avant les totaux sans planter, 
# affichez simplement un petit texte récapitulatif en dessous
st.caption("Note : Les lignes 'TOTAL' résument les données par propriétaire.")

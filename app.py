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

# --- CHARGEMENT DES DONNÉES ---
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
    
    # Filtrage pour la rapidité
    ids_inventaire = df['id_merge'].unique().tolist()
    gdf = gdf_total[gdf_total['id'].isin(ids_inventaire)].copy()
    
    return gdf.merge(df, left_on='id', right_on='id_merge', how='left')

# Exécution chargement
gdf = load_data()

# --- CARTE ---
st.subheader("Localisation des parcelles")
bounds = gdf.total_bounds
m = folium.Map()
m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

for _, row in gdf.iterrows():
    # Gestion sécurisée des couleurs
    c = row.get('IS', 'F')
    color = 'blue' if c == 'I' else ('red' if c == 'S' else 'gray')
    
    folium.GeoJson(
        row.geometry,
        style_function=lambda x, col=color: {'fillColor': col, 'color': col, 'weight': 1, 'fillOpacity': 0.6},
        tooltip=f"ID: {row['id']} - Nature: {row.get('Nature', 'N/A')}"
    ).add_to(m)
st_folium(m, width=1200, height=400)

# --- FORMULAIRE ---
st.subheader("Modifier une affectation")
with st.form("attribution_form"):
    col1, col2 = st.columns(2)
    sorted_ids = sorted(gdf['id'].unique().tolist(), key=lambda x: (len(x), x))
    parcel_id = col1.selectbox("Choisir l'ID de la parcelle", sorted_ids)
    new_owner = col2.selectbox("Nouvelle attribution", ["I", "S", "F"])
    submit = st.form_submit_button("Appliquer la modification")

# --- TABLEAU DE BORD (SANS ERREUR) ---
st.subheader("Tableau de bord des attributions")

df_display = gdf.copy()
df_display['IS'] = df_display['IS'].fillna('F')
df_display['Propriétaire'] = df_display['IS'].map({'I': 'Isabelle', 'S': 'Sébastien', 'F': 'Reste à attribuer'})

# Nettoyage chiffres
for col in ['contenance', 'Revenu_Cadastral']:
    df_display[col] = pd.to_numeric(df_display[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

# Calcul résumé
summary = df_display.groupby(['Propriétaire', 'Nature'], as_index=False).agg({
    'id': 'count', 'contenance': 'sum', 'Revenu_Cadastral': 'sum'
})

# Calcul totaux par propriétaire
totals = summary.groupby('Propriétaire')[['id', 'contenance', 'Revenu_Cadastral']].sum().reset_index()
totals['Nature'] = '--- TOTAL ---'
summary = pd.concat([summary, totals], ignore_index=True)

# Tri pour placer les totaux à la fin de chaque propriétaire
summary['sort'] = summary['Nature'].apply(lambda x: 1 if x == '--- TOTAL ---' else 0)
summary = summary.sort_values(['Propriétaire', 'sort', 'Nature']).drop(columns=['sort'])

# Affichage simple (sans style complexe pour éviter tout crash)
st.dataframe(summary.rename(columns={'id': 'Nb Parcelles'}), use_container_width=True, hide_index=True)

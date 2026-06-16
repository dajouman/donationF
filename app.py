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
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRrcHwy2y4vE2boubFxFCH-3RZpIyr0DvEm0ScJBHsr6UG4EMTvAJz7oqdlRVuIpouLhoxG7l5kCjRF/pub?output=csv"
    response = requests.get(url)
    df = pd.read_csv(StringIO(response.text))
    
    # Nettoyage des identifiants
    df['id_merge'] = df['id_merge'].astype(str).str.strip()
    
    with open('commune.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    gdf_total = gpd.GeoDataFrame.from_features(data['features'])
    gdf_total['id'] = gdf_total['id'].astype(str).str.strip()
    
    # Fusion
    gdf = gdf_total.merge(df, left_on='id', right_on='id_merge', how='left')
    
    # Nettoyage des colonnes numériques
    gdf['contenance'] = pd.to_numeric(gdf['contenance'], errors='coerce').fillna(0)
    gdf['Revenu_Cadastral'] = pd.to_numeric(gdf['Revenu_Cadastral'], errors='coerce').fillna(0)
    
    return gdf

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
    
    # Pop-up enrichi
    popup_text = f"<b>Parcelle :</b> {row.get('parcelle', row['id'])}<br>" \
                 f"<b>Contenance :</b> {row['contenance']:.4f} a<br>" \
                 f"<b>Valeur :</b> {row.get('Revenu_Cadastral', 0):.2f}<br>" \
                 f"<b>Propriétaire :</b> {nom_prop}"
    
    folium.GeoJson(
        row.geometry,
        style_function=lambda x, col=color: {'fillColor': col, 'color': col, 'weight': 1, 'fillOpacity': 0.6},
        tooltip=folium.Tooltip(popup_text)
    ).add_to(m)

st_folium(m, width=1200, height=400)

# --- 3. FORMULAIRE D'AFFECTATION ---
st.subheader("Modifier une affectation")
with st.form("attribution_form"):
    col1, col2 = st.columns(2)
    sorted_ids = sorted(gdf['id'].unique().tolist(), key=lambda x: (len(x), x))
    parcel_id = col1.selectbox("Choisir l'ID de la parcelle", sorted_ids)
    new_owner = col2.selectbox("Nouvelle attribution", ["I", "S", "F"])
    submit = st.form_submit_button("Appliquer la modification")

# --- 4. TABLEAU DE BORD ---
st.subheader("Tableau de bord des attributions")

df_display = gdf.copy()
df_display['IS'] = df_display['IS'].fillna('F')
df_display['Propriétaire'] = df_display['IS'].map({'I': 'Isabelle', 'S': 'Sébastien', 'F': 'Reste à attribuer'})

summary = df_display.groupby(['Propriétaire', 'Nature'], as_index=False).agg({
    'id': 'count', 'contenance': 'sum', 'Revenu_Cadastral': 'sum'
})

totals = summary.groupby('Propriétaire')[['id', 'contenance', 'Revenu_Cadastral']].sum().reset_index()
totals['Nature'] = '--- TOTAL ---'
summary = pd.concat([summary, totals], ignore_index=True)

summary['sort'] = summary['Nature'].apply(lambda x: 1 if x == '--- TOTAL ---' else 0)
summary = summary.sort_values(['Propriétaire', 'sort', 'Nature']).drop(columns=['sort'])

st.dataframe(summary.rename(columns={'id': 'Nb Parcelles'}), use_container_width=True, hide_index=True)

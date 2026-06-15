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

# Préparation des données
df_display = gdf.copy()
df_display['IS'] = df_display['IS'].fillna('F')
df_display['Propriétaire'] = df_display['IS'].map({'I': 'Isabelle', 'S': 'Sébastien', 'F': 'Reste à attribuer'})

for col in ['contenance', 'Revenu_Cadastral']:
    df_display[col] = pd.to_numeric(df_display[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

# Calculs
summary = df_display.groupby(['Propriétaire', 'Nature'], as_index=False).agg({'id': 'count', 'contenance': 'sum', 'Revenu_Cadastral': 'sum'})
totals = summary.groupby('Propriétaire')[['id', 'contenance', 'Revenu_Cadastral']].sum().reset_index()
totals['Nature'] = 'TOTAL'
summary = pd.concat([summary, totals])
summary['order'] = summary['Nature'].apply(lambda x: 1 if x == 'TOTAL' else 0)
summary = summary.sort_values(['Propriétaire', 'order', 'Nature']).drop(columns=['order'])
summary = summary.rename(columns={'id': 'Nombre de parcelles'})

# --- CORRECTION DU STYLE ---
def style_total(row):
    # On vérifie si la valeur de 'Nature' est bien 'TOTAL'
    if row.get('Nature') == 'TOTAL':
        return ['font-weight: bold; background-color: #e1f5fe'] * len(row)
    else:
        return [''] * len(row)

# Utilisation d'un dictionnaire pour appliquer le style seulement si nécessaire
# et conversion explicite pour éviter les erreurs de lecture
st.dataframe(
    summary.style.apply(style_total, axis=1), 
    use_container_width=True, 
    hide_index=True
)

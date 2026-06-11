import streamlit as st
import pandas as pd
import geopandas as gpd
import json
import folium
import streamlit.components.v1 as components

# Configuration pour occuper toute la largeur
st.set_page_config(layout="wide")
st.title("Gestion de la Donation Lachaux")

@st.cache_data(ttl=30)
def load_data():
    # 1. Chargement des données depuis votre Sheet publié
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRrcHwy2y4vE2boubFxFCH-3RZpIyr0DvEm0ScJBHsr6UG4EMTvAJz7oqdlRVuIpouLhoxG7l5kCjRF/pub?output=csv"
    df = pd.read_csv(url)
    df['id_merge'] = df['id_merge'].astype(str)
    
    # 2. Chargement de la géographie
    with open('commune.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    gdf = gpd.GeoDataFrame.from_features(data['features'])
    gdf['id'] = gdf['id'].astype(str)
    
    # 3. Fusion des deux
    return gdf.merge(df, left_on='id', right_on='id_merge', how='left')

# On charge les données
gdf = gdf_full = load_data()

# --- CARTE ---
st.subheader("Visualisation des parcelles")
m = folium.Map(location=[gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()], zoom_start=15)

def get_color(statut):
    if statut == 'I': return '#2ecc71' # Vert
    if statut == 'S': return '#3498db' # Bleu
    if statut == 'F': return '#f1c40f' # Jaune
    return '#dddddd' # Gris

for _, row in gdf.iterrows():
    folium.GeoJson(
        row['geometry'],
        style_function=lambda x, r=row: {
            'fillColor': get_color(r.get('IS')), 
            'color': 'black', 
            'weight': 0.5, 
            'fillOpacity': 0.7
        }
    ).add_to(m)

components.html(m._repr_html_(), width=800, height=500)

# --- TABLEAU DE BORD ---
st.subheader("Tableau de bord des attributions")
gdf['IS'] = gdf['IS'].fillna('F')
libelles = {'I': 'Isabelle', 'S': 'Sébastien', 'F': 'Reste à attribuer'}
gdf['Propriétaire'] = gdf['IS'].map(libelles)

summary = gdf.groupby(['Propriétaire', 'Nature']).agg({
    'contenance': 'sum',
    'Revenu_Cadastral': 'sum'
}).reset_index()

st.table(summary)
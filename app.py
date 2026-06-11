import streamlit as st
import pandas as pd
import geopandas as gpd
import json
import folium
import streamlit.components.v1 as components
import requests
from io import StringIO

# Configuration pour occuper toute la largeur
st.set_page_config(layout="wide")
st.title("Gestion de la Donation Lachaux")

@st.cache_data(ttl=30)
def load_data():
    # 1. Chargement des données depuis votre Sheet publié
    # REMPLACEZ L'URL CI-DESSOUS PAR VOTRE LIEN DE PUBLICATION CSV
    url = "VOTRE_URL_ICI"
    response = requests.get(url)
    # On force l'encodage en utf-8 pour éviter les erreurs de caractères
    response.encoding = 'utf-8'
    df = pd.read_csv(StringIO(response.text))
    df['id_merge'] = df['id_merge'].astype(str)
    
    # 2. Chargement de la géographie
    with open('commune.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    gdf = gpd.GeoDataFrame.from_features(data['features'])
    gdf['id'] = gdf['id'].astype(str)
    
    # 3. Fusion des deux
    return gdf.merge(df, left_on='id', right_on='id_merge', how='left')

# On charge les données
gdf = load_data()

# --- CARTE ---
st.subheader("Visualisation des parcelles")
# Calcul du centre moyen pour centrer la carte
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

# Nettoyage des colonnes numériques
for col in ['contenance', 'Revenu_Cadastral']:
    gdf[col] = pd.to_numeric(gdf[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

# Groupby avec compte des parcelles et sommes
summary = gdf.groupby(['Propriétaire', 'Nature']).agg({
    'id_merge': 'count',
    'contenance': 'sum',
    'Revenu_Cadastral': 'sum'
}).rename(columns={'id_merge': 'Nombre de parcelles'}).reset_index()

st.table(summary)

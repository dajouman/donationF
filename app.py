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
@st.cache_data(ttl=30)
def load_data():
    url = "VOTRE_URL_ICI"
    response = requests.get(url)
    response.encoding = 'utf-8'
    
    # On force la lecture sans "manger" de lignes, 
    # et on ignore les erreurs de formatage pour voir ce qui bloque
    df = pd.read_csv(StringIO(response.text), on_bad_lines='warn', skipinitialspace=True)
    
    # DEBUG : Affiche le nombre de lignes réelles
    st.sidebar.write(f"Lignes détectées dans le CSV : {len(df)}")
    
    df['id_merge'] = df['id_merge'].astype(str)
    
    with open('commune.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    gdf = gpd.GeoDataFrame.from_features(data['features'])
    gdf['id'] = gdf['id'].astype(str)
    
    return gdf.merge(df, left_on='id', right_on='id_merge', how='left')

# On charge les données
gdf = load_data()

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

# --- TABLEAU DE BORD (Trié correctement) ---
st.subheader("Tableau de bord des attributions")
gdf['IS'] = gdf['IS'].fillna('F')
libelles = {'I': 'Isabelle', 'S': 'Sébastien', 'F': 'Reste à attribuer'}
gdf['Propriétaire'] = gdf['IS'].map(libelles)

# Nettoyage
for col in ['contenance', 'Revenu_Cadastral']:
    gdf[col] = pd.to_numeric(gdf[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

# Calcul du détail
summary = gdf.groupby(['Propriétaire', 'Nature'], as_index=False).agg({
    'id_merge': 'count',
    'contenance': 'sum',
    'Revenu_Cadastral': 'sum'
})

# Calcul des totaux
totals = summary.groupby('Propriétaire')[['id_merge', 'contenance', 'Revenu_Cadastral']].sum().reset_index()
totals['Nature'] = 'TOTAL'

# On combine
summary = pd.concat([summary, totals])

# ASTUCE DE TRI : 
# On crée une colonne temporaire pour trier (Nature normale = 0, TOTAL = 1)
summary['sort_order'] = summary['Nature'].apply(lambda x: 1 if x == 'TOTAL' else 0)

# On trie d'abord par Propriétaire, puis par sort_order, puis par Nature
summary = summary.sort_values(['Propriétaire', 'sort_order', 'Nature'])

# On supprime la colonne de tri et on affiche
summary = summary.drop(columns=['sort_order']).rename(columns={'id_merge': 'Nombre de parcelles'})

st.table(summary)

import streamlit as st
import pandas as pd
import geopandas as gpd
import json
import folium
import streamlit.components.v1 as components
import requests
from io import StringIO

st.set_page_config(layout="wide")
st.title("Gestion de la Donation Lachaux")

@st.cache_data(ttl=30)
def load_data():
    # REMPLACEZ CI-DESSOUS PAR VOTRE VRAI LIEN. 
    # EXEMPLE: "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ/pub?output=csv"
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRrcHwy2y4vE2boubFxFCH-3RZpIyr0DvEm0ScJBHsr6UG4EMTvAJz7oqdlRVuIpouLhoxG7l5kCjRF/pub?output=csv" 
    
    response = requests.get(url)
    response.encoding = 'utf-8'
    df = pd.read_csv(StringIO(response.text))
    df['id_merge'] = df['id_merge'].astype(str)
    
    with open('commune.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    gdf = gpd.GeoDataFrame.from_features(data['features'])
    gdf['id'] = gdf['id'].astype(str)
    
    return gdf.merge(df, left_on='id', right_on='id_merge', how='left')

gdf = load_data()

st.subheader("Visualisation des parcelles")
m = folium.Map(location=[gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()], zoom_start=15)

def get_color(statut):
    if statut == 'I': return '#2ecc71'
    if statut == 'S': return '#3498db'
    if statut == 'F': return '#f1c40f'
    return '#dddddd'

for _, row in gdf.iterrows():
    folium.GeoJson(
        row['geometry'],
        style_function=lambda x, r=row: {
            'fillColor': get_color(r.get('IS')), 
            'color': 'black', 'weight': 0.5, 'fillOpacity': 0.7
        }
    ).add_to(m)

components.html(m._repr_html_(), width=800, height=500)

st.subheader("Tableau de bord des attributions")
gdf['IS'] = gdf['IS'].fillna('F')
libelles = {'I': 'Isabelle', 'S': 'Sébastien', 'F': 'Reste à attribuer'}
gdf['Propriétaire'] = gdf['IS'].map(libelles)

for col in ['contenance', 'Revenu_Cadastral']:
    gdf[col] = pd.to_numeric(gdf[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

summary = gdf.groupby(['Propriétaire', 'Nature'], as_index=False).agg({
    'id_merge': 'count',
    'contenance': 'sum',
    'Revenu_Cadastral': 'sum'
})

totals = summary.groupby('Propriétaire')[['id_merge', 'contenance', 'Revenu_Cadastral']].sum().reset_index()
totals['Nature'] = 'TOTAL'
summary = pd.concat([summary, totals])
summary['sort_order'] = summary['Nature'].apply(lambda x: 1 if x == 'TOTAL' else 0)
summary = summary.sort_values(['Propriétaire', 'sort_order', 'Nature']).drop(columns=['sort_order'])
summary = summary.rename(columns={'id_merge': 'Nombre de parcelles'})

st.table(summary)

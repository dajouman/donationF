import streamlit as st
import pandas as pd
import geopandas as gpd
import json
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide", page_title="Donation Isa / Seb")

# --- 1. CHARGEMENT ET FUSION ---
@st.cache_data(ttl=10) # Cache court pour appliquer vos modifications du Sheet instantanément
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRrcHwy2y4vE2boubFxFCH-3RZpIyr0DvEm0ScJBHsr6UG4EMTvAJz7oqdlRVuIpouLhoxG7l5kCjRF/pub?output=csv"
    df = pd.read_csv(url)
    
    # Nettoyage des espaces autour des noms de colonnes du CSV
    df.columns = df.columns.str.strip()
    df['id_merge'] = df['id_merge'].astype(str).str.strip()
    
    # Nettoyage et conversion des chiffres (gestion des virgules comme "14,02")
    for col in ['contenance', 'Revenu_Cadastral']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('"', '', regex=False).str.replace(',', '.', regex=False).str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Chargement du GeoJSON cadastral
    with open('commune.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    gdf = gpd.GeoDataFrame.from_features(data['features'])
    gdf['id'] = gdf['id'].astype(str).str.strip()
    
    # On isole uniquement la géométrie pour éviter tout conflit de nom de colonne
    gdf = gdf[['id', 'geometry']]
    
    # Fusion inner : seules vos parcelles du Sheet sont conservées
    gdf_merged = gdf.merge(df, left_on='id', right_on='id_merge', how='inner')
    
    # Remplissages par défaut
    gdf_merged['IS'] = gdf_merged['IS'].fillna('F')
    gdf_merged['Nature'] = gdf_merged['Nature'].fillna('Inconnue')
    
    return gdf_merged

gdf = load_data()

# --- 2. CARTE INTERACTIVE ---
st.subheader("Localisation des parcelles")
m = folium.Map()

if not gdf.empty:
    bounds = gdf.total_bounds
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
else:
    st.error("Aucune parcelle trouvée lors de la fusion. Vérifiez la correspondance des IDs.")

for _, row in gdf.iterrows():
    prop = row['IS']
    nom_prop = 'Isabelle' if prop == 'I' else ('Sébastien' if prop == 'S' else 'Non attribué')
    color = 'blue' if prop == 'I' else ('red' if prop == 'S' else 'gray')
    
    # Modification ici : affichage de la valeur brute en ares (a)
    popup_text = f"<b>Parcelle :</b> {row['Parcelle']}<br>" \
                 f"<b>Contenance :</b> {row['contenance']} a<br>" \
                 f"<b>Valeur :</b> {row['Revenu_Cadastral']:.2f}<br>" \
                 f"<b>Propriétaire :</b> {nom_prop}"
    
    folium.GeoJson(
        row.geometry,
        style_function=lambda x, col=color: {'fillColor': col, 'color': col, 'weight': 1, 'fillOpacity': 0.6},
        tooltip=folium.Tooltip(popup_text)
    ).add_to(m)

st_folium(m, width=1200, height=400)

# --- 3. TABLEAU DE BORD ---
st.subheader("Tableau de bord des attributions")
df_display = gdf.copy()
df_display['Propriétaire'] = df_display['IS'].map({'I': 'Isabelle', 'S': 'Sébastien'}).fillna('Reste à attribuer')

summary = df_display.groupby(['Propriétaire', 'Nature'], as_index=False).agg({
    'id': 'count', 
    'contenance': 'sum', 
    'Revenu_Cadastral': 'sum'
})

totals = summary.groupby('Propriétaire')[['id', 'contenance', 'Revenu_Cadastral']].sum().reset_index()
totals['Nature'] = '--- TOTAL ---'
summary = pd.concat([summary, totals], ignore_index=True)
summary = summary.sort_values(['Propriétaire', 'Nature']).rename(columns={'id': 'Nb Parcelles'})

st.dataframe(summary, use_container_width=True, hide_index=True)

import streamlit as st
import pandas as pd
import geopandas as gpd
import json
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide", page_title="Donation Isa / Seb")

# --- 1. CHARGEMENT (CACHE RÉDUIT À 10 SECONDES POUR FORCER LA MISE À JOUR) ---
@st.cache_data(ttl=10)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRrcHwy2y4vE2boubFxFCH-3RZpIyr0DvEm0ScJBHsr6UG4EMTvAJz7oqdlRVuIpouLhoxG7l5kCjRF/pub?output=csv"
    df = pd.read_csv(url)
    
    # Nettoyage ultime : on met tout en minuscules et on enlève les espaces
    df.columns = df.columns.str.strip().str.lower()
    
    # On renomme pour que la suite du code fonctionne
    df = df.rename(columns={
        'id_merge': 'id_merge',
        'is': 'IS',
        'nature': 'Nature',
        'parcelle': 'Parcelle',
        'revenu_cadastral': 'Revenu_Cadastral'
    })
    
    # --- LE DÉTECTEUR DE PROBLÈME ---
    if 'contenance' not in df.columns:
        st.error("🚨 ARRÊT : La colonne 'contenance' est absente du fichier reçu !")
        st.write("Voici les colonnes que le lien Google Sheets contient actuellement :", list(df.columns))
        st.info("Si vous venez d'ajouter la colonne dans le Sheet, attendez 5 minutes que le lien publié se mette à jour chez Google, puis rafraîchissez cette page.")
        st.stop() # Arrête le code proprement au lieu de planter
        
    df['id_merge'] = df['id_merge'].astype(str).str.strip()
    
    # Nettoyage des chiffres
    for col in ['contenance', 'Revenu_Cadastral']:
        df[col] = df[col].astype(str).str.replace('"', '', regex=False).str.replace(',', '.', regex=False).str.strip()
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    with open('commune.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    gdf = gpd.GeoDataFrame.from_features(data['features'])
    gdf['id'] = gdf['id'].astype(str).str.strip()
    
    # Fusion parfaite
    gdf_merged = gdf.merge(df, left_on='id', right_on='id_merge', how='inner')
    
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
    st.error("Aucune parcelle trouvée lors de la fusion.")

for _, row in gdf.iterrows():
    prop = row.get('IS', 'F')
    nom_prop = 'Isabelle' if prop == 'I' else ('Sébastien' if prop == 'S' else 'Non attribué')
    color = 'blue' if prop == 'I' else ('red' if prop == 'S' else 'gray')
    
    # Sécurité .get() absolue
    popup_text = f"<b>Parcelle :</b> {row.get('Parcelle', 'N/A')}<br>" \
                 f"<b>Contenance :</b> {row.get('contenance', 0):.4f} ha<br>" \
                 f"<b>Valeur :</b> {row.get('Revenu_Cadastral', 0):.2f}<br>" \
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

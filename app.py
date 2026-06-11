import streamlit as st
import pandas as pd
import geopandas as gpd
import json
import folium
import streamlit.components.v1 as components
import requests
import gspread
from io import StringIO
from google.oauth2.service_account import Credentials

# Configuration
st.set_page_config(layout="wide")
st.title("Gestion de la Donation Lachaux")

# --- FONCTIONS ---
@st.cache_data(ttl=30)
def load_data():
    # REMPLACEZ VOTRE_URL_ICI PAR VOTRE LIEN CSV DE PUBLICATION GOOGLE SHEETS
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

def update_google_sheet(parcelle_id, nouveau_statut):
    # Connexion à l'API Google Sheets via les secrets Streamlit
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict)
    client = gspread.authorize(creds)
    
    # REMPLACEZ "NOM_DE_VOTRE_FICHIER_SHEET" PAR LE NOM EXACT DANS VOTRE DRIVE
    sheet = client.open("NOM_DE_VOTRE_FICHIER_SHEET").sheet1
    
    # Trouver la ligne de la parcelle par son ID
    cell = sheet.find(str(parcelle_id))
    # Met à jour la colonne 4 (colonne D) - Ajustez ce chiffre si besoin
    sheet.update_cell(cell.row, 4, nouveau_statut)

# --- CHARGEMENT ---
gdf = load_data()

# --- CARTE ---
st.subheader("Visualisation des parcelles")
m = folium.Map(location=[gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()], zoom_start=15)

for _, row in gdf.iterrows():
    statut = row.get('IS', 'F')
    color = '#2ecc71' if statut == 'I' else '#3498db' if statut == 'S' else '#f1c40f'
    folium.GeoJson(row['geometry'], style_function=lambda x, c=color: {'fillColor': c, 'color': 'black', 'weight': 0.5, 'fillOpacity': 0.7}).add_to(m)

components.html(m._repr_html_(), width=800, height=500)

# --- INTERFACE D'ATTRIBUTION ---
st.subheader("Attribution d'une parcelle")
col1, col2 = st.columns(2)
with col1:
    selected_id = st.selectbox("Sélectionnez une parcelle :", gdf['id'].unique())
    new_is = st.radio("Attribuer à :", ['I', 'S', 'F'], format_func=lambda x: {'I': 'Isabelle', 'S': 'Sébastien', 'F': 'Reste à attribuer'}[x])
    if st.button("Valider l'attribution"):
        try:
            update_google_sheet(selected_id, new_is)
            st.success("Enregistré dans le Google Sheet !")
            st.rerun() # Recharge l'application
        except Exception as e:
            st.error(f"Erreur de mise à jour : {e}")

# --- TABLEAU DE BORD ---
st.subheader("Tableau de bord des attributions")
gdf['IS'] = gdf['IS'].fillna('F')
gdf['Propriétaire'] = gdf['IS'].map({'I': 'Isabelle', 'S': 'Sébastien', 'F': 'Reste à attribuer'})

for col in ['contenance', 'Revenu_Cadastral']:
    gdf[col] = pd.to_numeric(gdf[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

summary = gdf.groupby(['Propriétaire', 'Nature'], as_index=False).agg({'id_merge': 'count', 'contenance': 'sum', 'Revenu_Cadastral': 'sum'})
totals = summary.groupby('Propriétaire')[['id_merge', 'contenance', 'Revenu_Cadastral']].sum().reset_index()
totals['Nature'] = 'TOTAL'
summary = pd.concat([summary, totals])
summary['sort_order'] = summary['Nature'].apply(lambda x: 1 if x == 'TOTAL' else 0)
summary = summary.sort_values(['Propriétaire', 'sort_order', 'Nature']).drop(columns=['sort_order'])
st.table(summary.rename(columns={'id_merge': 'Nombre de parcelles'}))

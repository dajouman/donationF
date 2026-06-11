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
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict)
    client = gspread.authorize(creds)
    sheet = client.open("Donation_Lachaux").sheet1 # Assurez-vous que c'est le nom exact
    cell = sheet.find(str(parcelle_id))
    sheet.update_cell(cell.row, 4, nouveau_statut)

# --- CHARGEMENT ---
gdf = load_data()

# --- CARTE ---
st.subheader("Visualisation des parcelles")
m = folium.Map(location=[gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()], zoom_start=15)

for _, row in gdf.iterrows():
    statut = row.get('IS')
    
    if pd.isna(statut):
        couleur = '#f0f0f0' # Gris très clair
        nom_proprio = "Hors inventaire"
    elif statut == 'F':
        couleur = '#f1c40f' # Jaune
        nom_proprio = "Reste à attribuer"
    elif statut == 'I':
        couleur = '#2ecc71' # Vert
        nom_proprio = "Isabelle"
    else: # S
        couleur = '#e74c3c' # Rouge
        nom_proprio = "Sébastien"

    info_bulle = f"Parcelle: {row['id']}<br>Propriétaire: {nom_proprio}"
    
    folium.GeoJson(
        row['geometry'],
        style_function=lambda x, c=couleur: {'fillColor': c, 'color': 'black', 'weight': 0.3, 'fillOpacity': 0.7},
        tooltip=folium.Tooltip(info_bulle)
    ).add_to(m)

components.html(m._repr_html_(), width=800, height=500)

# --- INTERFACE D'ATTRIBUTION ---
st.subheader("Attribution d'une parcelle")
ids_tries = sorted(gdf['id'].unique().astype(str), key=lambda x: int(x) if x.isdigit() else x)
selected_id = st.selectbox("Sélectionnez une parcelle :", ids_tries)
new_is = st.radio("Attribuer à :", ['I', 'S', 'F'], format_func=lambda x: {'I': 'Isabelle', 'S': 'Sébastien', 'F': 'Reste à attribuer'}[x])

if st.button("Valider l'attribution"):
    try:
        update_google_sheet(selected_id, new_is)
        st.success("Enregistré dans le Google Sheet !")
        st.rerun()
    except Exception as e:
        st.error(f"Erreur : {e}")

# --- TABLEAU DE BORD ---
st.subheader("Tableau de bord des attributions")
df_display = gdf.copy()
df_display['IS'] = df_display['IS'].fillna('F')
df_display['Propriétaire'] = df_display['IS'].map({'I': 'Isabelle', 'S': 'Sébastien', 'F': 'Reste à attribuer'})

for col in ['contenance', 'Revenu_Cadastral']:
    df_display[col] = pd.to_numeric(df_display[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

summary = df_display.groupby(['Propriétaire', 'Nature'], as_index=False).agg({'id_merge': 'count', 'contenance': 'sum', 'Revenu_Cadastral': 'sum'})
totals = summary.groupby('Propriétaire')[['id_merge', 'contenance', 'Revenu_Cadastral']].sum().reset_index()
totals['Nature'] = 'TOTAL'
summary = pd.concat([summary, totals])
summary['sort_order'] = summary['Nature'].apply(lambda x: 1 if x == 'TOTAL' else 0)
summary = summary.sort_values(['Propriétaire', 'sort_order', 'Nature']).drop(columns=['sort_order'])
st.table(summary.rename(columns={'id_merge': 'Nombre de parcelles'}))

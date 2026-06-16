import streamlit as st
import pandas as pd
import geopandas as gpd
import json
import requests
from io import StringIO
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide", page_title="Donation Isa / Seb")

# --- 1. CHARGEMENT ET FILTRAGE OPTIMISÉ ---
@st.cache_data(ttl=3600)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRrcHwy2y4vE2boubFxFCH-3RZpIyr0DvEm0ScJBHsr6UG4EMTvAJz7oqdlRVuIpouLhoxG7l5kCjRF/pub?output=csv"
    response = requests.get(url)
    df = pd.read_csv(StringIO(response.text))
    df['id_merge'] = df['id_merge'].astype(str).str.strip()
    
    # Nettoyage forcé des numériques dès l'import
    for col in ['contenance', 'Revenu_Cadastral']:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    
    with open('commune.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    gdf_total = gpd.GeoDataFrame.from_features(data['features'])
    gdf_total['id'] = gdf_total['id'].astype(str).str.strip()
    
    # Filtrage strict avant fusion pour la vitesse
    gdf = gdf_total[gdf_total['id'].isin(df['id_merge'].unique())].copy()
    return gdf.merge(df, left_on='id', right_on='id_merge', how='left')

gdf = load_data()

# --- 2. CARTE (ZOOM CIBLÉ) ---
st.subheader("Localisation des parcelles")
bounds = gdf.total_bounds # Calcule le zoom uniquement sur les parcelles du CSV
m = folium.Map()
m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

for _, row in gdf.iterrows():
    prop = row.get('IS', 'F')
    color = 'blue' if prop == 'I' else ('red' if prop == 'S' else 'gray')
    popup_text = f"<b>Parcelle :</b> {row.get('parcelle', row['id'])}<br>" \
                 f"<b>Contenance :</b> {row['contenance']:.4f} a<br>" \
                 f"<b>Valeur :</b> {row.get('Revenu_Cadastral', 0):.2f}<br>" \
                 f"<b>Propriétaire :</b> {'Isabelle' if prop == 'I' else 'Sébastien' if prop == 'S' else 'Non attribué'}"
    
    folium.GeoJson(
        row.geometry,
        style_function=lambda x, col=color: {'fillColor': col, 'color': col, 'weight': 1, 'fillOpacity': 0.6},
        tooltip=folium.Tooltip(popup_text)
    ).add_to(m)

st_folium(m, width=1200, height=400)

# --- 3. FORMULAIRE ---
st.subheader("Modifier une affectation")
with st.form("attribution_form"):
    col1, col2 = st.columns(2)
    parcel_id = col1.selectbox("Choisir l'ID de la parcelle", sorted(gdf['id'].unique().tolist()))
    new_owner = col2.selectbox("Nouvelle attribution", ["I", "S", "F"])
    if st.form_submit_button("Appliquer"):
        st.info("Modification enregistrée (fonction d'écriture à venir).")

# --- 4. TABLEAU DE BORD ---
st.subheader("Tableau de bord")
df_display = gdf.copy()
df_display['Propriétaire'] = df_display['IS'].map({'I': 'Isabelle', 'S': 'Sébastien'}).fillna('Reste à attribuer')

summary = df_display.groupby(['Propriétaire', 'Nature'], as_index=False).agg({'id': 'count', 'contenance': 'sum', 'Revenu_Cadastral': 'sum'})
totals = summary.groupby('Propriétaire')[['id', 'contenance', 'Revenu_Cadastral']].sum().reset_index()
totals['Nature'] = '--- TOTAL ---'
summary = pd.concat([summary, totals], ignore_index=True)
summary = summary.sort_values(['Propriétaire', 'Nature']).rename(columns={'id': 'Nb Parcelles'})

st.dataframe(summary, use_container_width=True, hide_index=True)

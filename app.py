import streamlit as st
import pandas as pd
import geopandas as gpd
import json
import folium
from streamlit_folium import st_folium

# Configuration de la page de l'application
st.set_page_config(layout="wide", page_title="Donation Famille")

# --- 1. CHARGEMENT ET FUSION ---
@st.cache_data(ttl=10) # Cache de 10 secondes pour actualisation rapide
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRrcHwy2y4vE2boubFxFCH-3RZpIyr0DvEm0ScJBHsr6UG4EMTvAJz7oqdlRVuIpouLhoxG7l5kCjRF/pub?output=csv"
    df = pd.read_csv(url)
    
    # Nettoyage des espaces autour des noms de colonnes du CSV
    df.columns = df.columns.str.strip()
    df['id_merge'] = df['id_merge'].astype(str).str.strip()
    
    # SÉCURITÉ : Nettoyage de la colonne IS (enlève les espaces et force les majuscules)
    if 'IS' in df.columns:
        df['IS'] = df['IS'].astype(str).str.strip().str.upper()
    
    # Nettoyage et conversion des chiffres (gestion des virgules françaises et cases vides)
    for col in ['contenance', 'Revenu_Cadastral']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('"', '', regex=False).str.replace(',', '.', regex=False).str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Chargement du GeoJSON cadastral
    with open('commune.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    gdf = gpd.GeoDataFrame.from_features(data['features'])
    gdf['id'] = gdf['id'].astype(str).str.strip()
    
    # Sécurisation : on ne garde que la géométrie du JSON pour éviter tout doublon de colonne
    gdf = gdf[['id', 'geometry']]
    
    # Fusion inner : seules les parcelles listées dans votre Sheet sont conservées et affichées
    gdf_merged = gdf.merge(df, left_on='id', right_on='id_merge', how='inner')
    
    # Remplissages par défaut
    gdf_merged['Nature'] = gdf_merged['Nature'].fillna('Info uniquement')
    gdf_merged['Parcelle'] = gdf_merged['Parcelle'].fillna(gdf_merged['id'])
    
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
    
    # Configuration des profils (Nom de famille, Couleur de la parcelle)
    config_prop = {
        'I': ('Isabelle', 'blue'),
        'S': ('Sébastien', 'red'),
        'Y': ('Sylvain', '#9370db'),  # Mauve
        'G': ('Gilles', '#ff7f0e')    # Orange foncé
    }
    
    nom_prop, color = config_prop.get(prop, ('Non attribué', 'gray'))
    
    # Ajustement dynamique du Pop-up / Tooltip selon le propriétaire
    if prop in ['Y', 'G']:
        # Version pour Sylvain et Gilles (Nom de Parcelle et Propriétaire)
        popup_text = f"<b>Parcelle :</b> {row['Parcelle']}<br><b>Propriétaire :</b> {nom_prop}"
    else:
        # Version complète pour Isabelle et Sébastien
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

# --- 3. TABLEAU DE BORD GLOBAL (Cousins uniquement) ---
st.subheader("Tableau de bord des attributions")

# FILTRE : On ne garde STRICTEMENT qu'Isabelle et Sébastien pour le tableau de bord
df_display = gdf[gdf['IS'].isin(['I', 'S'])].copy()

if not df_display.empty:
    # Mapping des noms pour l'affichage textuel du tableau
    df_display['Propriétaire'] = df_display['IS'].map({
        'I': 'Isabelle', 
        'S': 'Sébastien'
    }).fillna('Reste à attribuer')

    # Groupement et agrégation des données
    summary = df_display.groupby(['Propriétaire', 'Nature'], as_index=False).agg({
        'id': 'count', 
        'contenance': 'sum', 
        'Revenu_Cadastral': 'sum'
    })

    # Calcul des lignes de sous-totaux par personne
    totals = summary.groupby('Propriétaire')[['id', 'contenance', 'Revenu_Cadastral']].sum().reset_index()
    totals['Nature'] = '--- TOTAL ---'
    summary = pd.concat([summary, totals], ignore_index=True)
    summary = summary.sort_values(['Propriétaire', 'Nature']).rename(columns={'id': 'Nb Parcelles'})

    st.dataframe(summary, use_container_width=True, hide_index=True)
else:
    st.info("Aucune parcelle attribuée à Isabelle ou Sébastien pour le moment.")

# --- 4. BALANCE DE LA DONATION (Filtre strict Cousins) ---
st.subheader("Balance et Équilibrage des Cousins (Isabelle / Sébastien)")

rc_isabelle = gdf[gdf['IS'] == 'I']['Revenu_Cadastral'].sum()
rc_sebastien = gdf[gdf['IS'] == 'S']['Revenu_Cadastral'].sum()
rc_total = rc_isabelle + rc_sebastien
cible = rc_total / 2
valeur_soulte = abs(rc_isabelle - rc_sebastien) / 2

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="Total Revenu Isabelle", value=f"{rc_isabelle:.2f} €")
with col2:
    st.metric(label="Total Revenu Sébastien", value=f"{rc_sebastien:.2f} €")
with col3:
    st.metric(label="Cible d'équilibre (50/50)", value=f"{cible:.2f} €")

if rc_isabelle > rc_sebastien:
    st.warning(
        f"📊 **Écart constaté :** Isabelle a un lot supérieur de {rc_isabelle - rc_sebastien:.2f} € par rapport à Sébastien.\n\n"
        f"⚖️ **Pour équilibrer :** Isabelle doit une soulte théorique de **{valeur_soulte:.2f} €** à Sébastien."
    )
elif rc_sebastien > rc_isabelle:
    st.warning(
        f"📊 **Écart constaté :** Sébastien a un lot supérieur de {rc_sebastien - rc_isabelle:.2f} € par rapport à Isabelle.\n\n"
        f"⚖️ **Pour équilibrer :** Sébastien doit une soulte théorique de **{valeur_soulte:.2f} €** à Isabelle."
    )
else:
    st.success("🎉 **Équilibre parfait entre les cousins !**")

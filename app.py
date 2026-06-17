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
    # On ajoute de manière préventive 'Valeur_Civile', 'Valeur', 'Estimation' si vous les créez dans le Sheet
    colonnes_numeriques = ['contenance', 'Revenu_Cadastral', 'Valeur_Civile', 'Valeur', 'Estimation']
    for col in colonnes_numeriques:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('"', '', regex=False).str.replace(',', '.', regex=False).str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Détection dynamique de la colonne financière à utiliser (Priorité à la Valeur Civile du notaire)
    val_col_found = 'Revenu_Cadastral' # Repli par défaut
    for potentielle_col in ['Valeur_Civile', 'Valeur', 'Estimation']:
        if potentielle_col in df.columns:
            val_col_found = potentielle_col
            break
    
    # On stocke temporairement le nom de la colonne choisie dans une variable fixe pour le reste du script
    df['VAL_CALCUL'] = df[val_col_found]
    df['VAL_COL_NAME'] = val_col_found # Pour affichage dynamique de la source de donnée
    
    # Chargement du GeoJSON cadastral
    with open('commune.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    gdf = gpd.GeoDataFrame.from_features(data['features'])
    gdf['id'] = gdf['id'].astype(str).str.strip()
    
    gdf = gdf[['id', 'geometry']]
    gdf_merged = gdf.merge(df, left_on='id', right_on='id_merge', how='inner')
    
    # Remplissages par défaut
    gdf_merged['Nature'] = gdf_merged['Nature'].fillna('Info uniquement')
    gdf_merged['Parcelle'] = gdf_merged['Parcelle'].fillna(gdf_merged['id'])
    
    return gdf_merged

gdf = load_data()

# Extraction du nom de la colonne financière utilisée pour les labels
nom_col_source = gdf['VAL_COL_NAME'].iloc[0] if not gdf.empty else "Valeur"

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
    
    config_prop = {
        'I': ('Isabelle', 'blue'),
        'S': ('Sébastien', 'red'),
        'Y': ('Sylvain', '#9370db'),  # Mauve
        'G': ('Gilles', '#ff7f0e')    # Orange foncé
    }
    
    nom_prop, color = config_prop.get(prop, ('Non attribué', 'gray'))
    
    if prop in ['Y', 'G']:
        popup_text = f"<b>Parcelle :</b> {row['Parcelle']}<br><b>Propriétaire :</b> {nom_prop}"
    else:
        popup_text = f"<b>Parcelle :</b> {row['Parcelle']}<br>" \
                     f"<b>Contenance :</b> {row['contenance']} a<br>" \
                     f"<b>{nom_col_source} :</b> {row['VAL_CALCUL']:.2f}<br>" \
                     f"<b>Propriétaire :</b> {nom_prop}"
    
    folium.GeoJson(
        row.geometry,
        style_function=lambda x, col=color: {'fillColor': col, 'color': col, 'weight': 1, 'fillOpacity': 0.6},
        tooltip=folium.Tooltip(popup_text)
    ).add_to(m)

st_folium(m, width=1200, height=400)

# --- 3. TABLEAU DE BORD GLOBAL (Cousins uniquement) ---
st.subheader("Tableau de bord des attributions")

df_display = gdf[gdf['IS'].isin(['I', 'S'])].copy()

if not df_display.empty:
    df_display['Propriétaire'] = df_display['IS'].map({'I': 'Isabelle', 'S': 'Sébastien'})

    summary = df_display.groupby(['Propriétaire', 'Nature'], as_index=False).agg({
        'id': 'count', 
        'contenance': 'sum', 
        'VAL_CALCUL': 'sum'
    })

    totals = summary.groupby('Propriétaire')[['id', 'contenance', 'VAL_CALCUL']].sum().reset_index()
    totals['Nature'] = '--- TOTAL ---'
    summary = pd.concat([summary, totals], ignore_index=True)
    summary = summary.sort_values(['Propriétaire', 'Nature']).rename(
        columns={'id': 'Nb Parcelles', 'VAL_CALCUL': f'Total {nom_col_source}'}
    )

    st.dataframe(summary, use_container_width=True, hide_index=True)
else:
    st.info("Aucune parcelle attribuée à Isabelle ou Sébastien pour le moment.")

# --- 4. MODELE ACTE NOTARIAL D'ÉQUILIBRAGE (Cousins uniquement) ---
st.subheader("⚖️ Acte d'Équilibrage et Règlement des Droits (Modèle Notarié)")

# Calculs stricts basés sur la méthode notariale de la Masse Civile
val_isabelle = gdf[gdf['IS'] == 'I']['VAL_CALCUL'].sum()
val_sebastien = gdf[gdf['IS'] == 'S']['VAL_CALCUL'].sum()

masse_partageable = val_isabelle + val_sebastien
droits_theoriques = masse_partageable / 2
ecart = abs(val_isabelle - val_sebastien)
soulte_theorique = ecart / 2

# Affichage sous forme de fiches juridiques (Masse -> Droits -> Lots)
col1, col2 = st.columns(2)
with col1:
    st.metric(label="Masse Civile globale à partager (Cousins)", value=f"{masse_partageable:.2f} €")
with col2:
    st.metric(label="Droits de chaque donataire copartagé (1/2)", value=f"{droits_theoriques:.2f} €")

st.markdown("---")
st.markdown("### 📋 Constat des Attributions Effectives")

col_isa, col_seb = st.columns(2)
with col_isa:
    st.markdown(f"**Lot attribué à Isabelle :**")
    st.markdown(f"• Valeur totale civile du lot : `{val_isabelle:.2f} €`")
    if val_isabelle == droits_theoriques:
        st.success("✅ **Ce lot remplit son attributaire du montant de ses droits.**")
    elif val_isabelle > droits_theoriques:
        st.info(f"🔺 Le lot dépasse ses droits théoriques de `+{val_isabelle - droits_theoriques:.2f} €`")
    else:
        st.warning(f"🔻 Le lot est inférieur ses droits théoriques de `-{droits_theoriques - val_isabelle:.2f} €`")

with col_seb:
    st.markdown(f"**Lot attribué à Sébastien :**")
    st.markdown(f"• Valeur totale civile du lot : `{val_sebastien:.2f} €`")
    if val_sebastien == droits_theoriques:
        st.success("✅ **Ce lot remplit son attributaire du montant de ses droits.**")
    elif val_sebastien > droits_theoriques:
        st.info(f"🔺 Le lot dépasse ses droits théoriques de `+{val_sebastien - droits_theoriques:.2f} €`")
    else:
        st.warning(f"🔻 Le lot est inférieur ses droits théoriques de `-{droits_theoriques - val_sebastien:.2f} €`")

st.markdown("---")
st.markdown("### ⚖️ Règlement des Lots et Soultes")

if val_isabelle > val_sebastien:
    st.error(
        f"**Rapport de Soulte :** Pour rétablir l'égalité stricte des lots exigée par la loi dans le cadre de ce partage anticipé, "
        f"**Isabelle** devra verser une soulte compensatoire d'un montant de **{soulte_theorique:.2f} €** à **Sébastien**."
    )
elif val_sebastien > val_isabelle:
    st.error(
        f"**Rapport de Soulte :** Pour rétablir l'égalité stricte des lots exigée par la loi dans le cadre de ce partage anticipé, "
        f"**Sébastien** devra verser une soulte compensatoire d'un montant de **{soulte_theorique:.2f} €** à **Isabelle**."
    )
else:
    st.success(
        "🎉 **Équilibre parfait constaté !** Les lots sont rigoureusement égaux. "
        "Chaque lot remplit son attributaire du montant de ses droits, le présent acte a lieu **sans soulte**."
    )

# Note informative pour l'utilisateur dans l'interface
st.caption(
    f"Note technique : Les calculs se basent actuellement sur la colonne `{nom_col_source}`. "
    "Si vous créez une colonne 'Valeur_Civile' dans votre Google Sheet avec les estimations réelles du terrain, "
    "l'application basculera automatiquement dessus pour un calcul juridique parfait."
)

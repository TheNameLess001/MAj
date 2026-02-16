import streamlit as st
import pandas as pd
import io
import zipfile

# --- CONFIGURATION ---
st.set_page_config(page_title="Générateur Catalogue Store", page_icon="⚡", layout="wide")

# --- FONCTION CACHE ---
@st.cache_data
def load_data(file):
    return pd.read_excel(file, sheet_name=None)

# --- UI HEADER ---
st.title("⚡ Processeur Data Carrefour x Yassir (Anti-Doublons)")
st.markdown("""
<div style='background-color: #e6f3ff; padding: 10px; border-radius: 5px; border-left: 5px solid #2b8cbe;'>
<strong>Nouveauté :</strong> Si deux produits ont le même nom dans un magasin, un espace invisible est ajouté à la fin du deuxième pour les différencier sans changer l'affichage.
</div>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Fichier Excel (.xlsx)", type=['xlsx'])

if uploaded_file:
    with st.spinner('🚀 Chargement et analyse du fichier...'):
        dfs = load_data(uploaded_file)
        
        sheet_names = list(dfs.keys())
        if len(sheet_names) < 4:
            st.error("Erreur : Le fichier doit contenir 4 onglets.")
            st.stop()

        df_out = dfs[sheet_names[0]]
        df_cat = dfs[sheet_names[1]]
        df_maj = dfs[sheet_names[2]]
        df_img = dfs[sheet_names[3]]

        # --- 1. PRÉPARATION ---
        # Conversion en string pour éviter les erreurs de merge
        for df in [df_maj, df_cat, df_img]:
            # On cherche les colonnes ID potentielles
            for col in ['product_id', 'store_id', 'external_id']:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip()

        # Nettoyage Images (garder la 1ère)
        if 'PICTURE_ORDER' in df_img.columns:
            df_img = df_img.sort_values('PICTURE_ORDER')
        df_img = df_img.drop_duplicates(subset=['external_id'], keep='first')

        # --- 2. FUSION GLOBALE (Rapide) ---
        merged = pd.merge(df_maj, df_cat, left_on='product_id', right_on='external_id', how='left')
        merged = pd.merge(merged, df_img[['external_id', 'image']], left_on='product_id', right_on='external_id', how='left', suffixes=('', '_img'))

        total_rows = len(merged)

        # --- 3. NETTOYAGE STRICT ---
        # Supprimer doublons stricts (même ID dans le même store)
        merged = merged.drop_duplicates(subset=['store_id', 'product_id'])
        rows_after_dedup = len(merged)
        
        # Supprimer produits incomplets (Pas de nom ou Pas d'image)
        condition_valid = (
            merged['name_english'].notna() & (merged['name_english'] != "") & 
            merged['image'].notna() & (merged['image'] != "")
        )
        final_data = merged[condition_valid].copy()
        
        # --- 4. GESTION DES DOUBLONS DE NOMS (La "faute minime") ---
        # On compte combien de fois un nom apparaît par store
        # Ex: "Pomme" (0), "Pomme" (1), "Pomme" (2)
        final_data['name_dedup_count'] = final_data.groupby(['store_id', 'name_english']).cumcount()
        
        # Fonction pour ajouter des espaces : 0 espace, 1 espace, 2 espaces...
        def add_space_suffix(row):
            count = row['name_dedup_count']
            if count > 0:
                # Ajoute 'count' nombre d'espaces à la fin
                return row['name_english'] + (' ' * count)
            return row['name_english']

        final_data['name_english'] = final_data.apply(add_space_suffix, axis=1)
        
        rows_final = len(final_data)

        # --- STATS ---
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Lignes Totales", total_rows)
        c2.metric("Doublons ID supprimés", total_rows - rows_after_dedup)
        c3.metric("Rejetés (Info manquante)", rows_after_dedup - rows_final)
        c4.metric("Produits Finaux", rows_final)
        st.divider()

        # --- EXPORT ---
        if rows_final > 0:
            final_data['external_id'] = final_data['product_id']
            if 'description' not in final_data.columns:
                final_data['description'] = ""
            
            final_data['description'] = final_data['description'].fillna("")
            final_data['quantity'] = final_data['quantity'].fillna(0).astype(int)
            final_data['price'] = final_data['price'].fillna(0)
            
            cols_export = ['name_english', 'price', 'quantity', 'description', 'category', 'sub_category', 'image', 'external_id']
            
            zip_buffer = io.BytesIO()
            stores = final_data['store_id'].unique()
            
            progress_bar = st.progress(0)
            
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, store in enumerate(stores):
                    df_store = final_data[final_data['store_id'] == store]
                    # On s'assure de n'avoir que les colonnes voulues
                    df_csv = df_store[cols_export]
                    
                    csv_bytes = df_csv.to_csv(index=False).encode('utf-8')
                    zf.writestr(f"Output_Store_{store}.csv", csv_bytes)
                    
                    progress_bar.progress((i + 1) / len(stores))
            
            st.success("✅ Traitement terminé !")
            
            zip_buffer.seek(0)
            st.download_button(
                "📥 TÉLÉCHARGER TOUT (ZIP)",
                data=zip_buffer,
                file_name="resultats_stores_unique.zip",
                mime="application/zip",
                use_container_width=True
            )
            
            with st.expander("Voir exemple de correction doublons"):
                # Montre les noms qui ont des espaces à la fin (donc les doublons corrigés)
                doublons_corriges = final_data[final_data['name_dedup_count'] > 0][['store_id', 'external_id', 'name_english']]
                if not doublons_corriges.empty:
                    st.write("Ces produits ont reçu un espace invisible à la fin de leur nom :")
                    st.dataframe(doublons_corriges.head())
                else:
                    st.write("Aucun doublon de nom trouvé.")

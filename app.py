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
st.title("⚡ Processeur Data Carrefour x Yassir")
st.markdown("""
<div style='background-color: #e6f3ff; padding: 10px; border-radius: 5px; border-left: 5px solid #2b8cbe;'>
<strong>Traitement intelligent :</strong> Fusionne les onglets, supprime les doublons (même ID dans même store) 
et retire les produits incomplets (sans image ou sans nom).
</div>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Fichier Excel (.xlsx)", type=['xlsx'])

if uploaded_file:
    with st.spinner('🚀 Chargement et analyse du fichier...'):
        dfs = load_data(uploaded_file)
        
        # Vérification basique
        sheet_names = list(dfs.keys())
        if len(sheet_names) < 4:
            st.error("Erreur : Le fichier doit contenir 4 onglets (Output, Catalogue, MAJ, Image).")
            st.stop()

        # Assignation des DF
        df_out = dfs[sheet_names[0]]
        df_cat = dfs[sheet_names[1]]
        df_maj = dfs[sheet_names[2]]
        df_img = dfs[sheet_names[3]]

        # --- PRÉPARATION DES DONNÉES (Vectorisée) ---
        
        # 1. Nettoyage IDs (String + Strip)
        df_maj['product_id'] = df_maj['product_id'].astype(str).str.strip()
        df_maj['store_id'] = df_maj['store_id'].astype(str).str.strip()
        
        df_cat['external_id'] = df_cat['external_id'].astype(str).str.strip()
        df_img['external_id'] = df_img['external_id'].astype(str).str.strip()

        # 2. Prépa Images (Garder unique)
        if 'PICTURE_ORDER' in df_img.columns:
            df_img = df_img.sort_values('PICTURE_ORDER')
        df_img = df_img.drop_duplicates(subset=['external_id'], keep='first')

        # 3. MERGE GLOBAL (MAJ + Catalogue + Image)
        merged = pd.merge(df_maj, df_cat, left_on='product_id', right_on='external_id', how='left')
        merged = pd.merge(merged, df_img[['external_id', 'image']], left_on='product_id', right_on='external_id', how='left', suffixes=('', '_img'))

        # Stats avant nettoyage
        total_rows = len(merged)

        # 4. SUPPRESSION DOUBLONS (Store + Product ID)
        merged = merged.drop_duplicates(subset=['store_id', 'product_id'])
        rows_after_dedup = len(merged)
        
        # 5. SUPPRESSION INCOMPLETS (Pas de nom OU Pas d'image)
        # On vérifie si name_english est vide/NaN ou image est vide/NaN
        condition_valid = (
            merged['name_english'].notna() & 
            (merged['name_english'] != "") & 
            merged['image'].notna() & 
            (merged['image'] != "")
        )
        final_data = merged[condition_valid].copy()
        rows_final = len(final_data)

        # --- DASHBOARD STATS ---
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Lignes Totales", total_rows)
        c2.metric("Doublons supprimés", total_rows - rows_after_dedup)
        c3.metric("Rejetés (Info manquante)", rows_after_dedup - rows_final)
        c4.metric("Produits Validés", rows_final)
        st.divider()

        # --- GÉNÉRATION ZIP ---
        if rows_final > 0:
            # Préparation colonnes finales
            final_data['external_id'] = final_data['product_id']
            if 'description' not in final_data.columns:
                final_data['description'] = ""
            final_data['description'] = final_data['description'].fillna("")
            final_data['quantity'] = final_data['quantity'].fillna(0).astype(int)
            final_data['price'] = final_data['price'].fillna(0)
            
            # Colonnes requises
            cols_export = ['name_english', 'price', 'quantity', 'description', 'category', 'sub_category', 'image', 'external_id']
            
            # Buffer ZIP
            zip_buffer = io.BytesIO()
            
            # Liste des stores
            stores = final_data['store_id'].unique()
            
            progress_text = "Génération des fichiers CSV en cours..."
            my_bar = st.progress(0, text=progress_text)
            
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, store in enumerate(stores):
                    # Filtrer
                    df_store = final_data[final_data['store_id'] == store]
                    
                    # Sélectionner et ordonner colonnes
                    df_csv = df_store[cols_export]
                    
                    # Écrire dans le ZIP
                    csv_bytes = df_csv.to_csv(index=False).encode('utf-8')
                    zf.writestr(f"Output_Store_{store}.csv", csv_bytes)
                    
                    # Update progress
                    my_bar.progress((i + 1) / len(stores), text=f"Store {store} traité")
            
            my_bar.empty()
            st.success("✅ Traitement terminé avec succès !")
            
            # BOUTON DOWNLOAD
            zip_buffer.seek(0)
            st.download_button(
                label="📥 TÉLÉCHARGER LES FICHIERS (ZIP)",
                data=zip_buffer,
                file_name="resultats_stores_clean.zip",
                mime="application/zip",
                use_container_width=True
            )
            
            # APERÇU
            with st.expander("Voir un aperçu des données valides"):
                st.dataframe(final_data[cols_export].head(20))
                
        else:
            st.warning("⚠️ Attention : Tous les produits ont été filtrés (manque d'image ou de nom). Vérifiez vos IDs.")

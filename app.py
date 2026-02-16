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
st.title("⚡ Processeur Data Carrefour x Yassir (Anti-Doublons Accentués)")
st.markdown("""
<div style='background-color: #fff3cd; padding: 10px; border-radius: 5px; border-left: 5px solid #ffc107; color: #856404;'>
<strong>Nouveauté :</strong> Les doublons de noms sont maintenant différenciés par un <strong>accent discret</strong> sur une voyelle (ex: <em>Orange</em> devient <em>Orangè</em>).
<br>Cela rend le nom unique pour la base de données sans ajouter d'espaces qui seraient supprimés.
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
        for df in [df_maj, df_cat, df_img]:
            for col in ['product_id', 'store_id', 'external_id']:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip()

        # Nettoyage Images
        if 'PICTURE_ORDER' in df_img.columns:
            df_img = df_img.sort_values('PICTURE_ORDER')
        df_img = df_img.drop_duplicates(subset=['external_id'], keep='first')

        # --- 2. FUSION GLOBALE ---
        merged = pd.merge(df_maj, df_cat, left_on='product_id', right_on='external_id', how='left')
        merged = pd.merge(merged, df_img[['external_id', 'image']], left_on='product_id', right_on='external_id', how='left', suffixes=('', '_img'))

        total_rows = len(merged)

        # --- 3. NETTOYAGE STRICT ---
        merged = merged.drop_duplicates(subset=['store_id', 'product_id'])
        rows_after_dedup = len(merged)
        
        condition_valid = (
            merged['name_english'].notna() & (merged['name_english'] != "") & 
            merged['image'].notna() & (merged['image'] != "")
        )
        final_data = merged[condition_valid].copy()
        
        # --- 4. GESTION DES DOUBLONS PAR ACCENTS ---
        final_data['name_dedup_count'] = final_data.groupby(['store_id', 'name_english']).cumcount()
        
        def apply_accent_typo(row):
            name = row['name_english']
            count = row['name_dedup_count']
            
            if count == 0:
                return name
            
            # Table de correspondance pour ajouter/changer des accents
            # On privilégie les accents plats ou aigus qui sont discrets
            charmap = {
                'a': 'à', 'A': 'À', 'à': 'a',
                'e': 'é', 'E': 'É', 'é': 'e', 'è': 'e',
                'i': 'ï', 'I': 'Ï',
                'o': 'ô', 'O': 'Ô',
                'u': 'ù', 'U': 'Ù',
                'y': 'ÿ'
            }
            
            chars = list(name)
            # Trouver les positions des voyelles modifiables
            indices = [i for i, c in enumerate(chars) if c in charmap]
            
            if not indices:
                # Fallback s'il n'y a pas de voyelles (rare): ajout d'un point
                return name + "."
            
            # Stratégie : Modifier la voyelle en partant de la fin selon le numéro du doublon
            # Doublon 1 -> Dernière voyelle
            # Doublon 2 -> Avant-dernière voyelle
            # Le modulo permet de boucler si on a plus de doublons que de voyelles
            idx_to_change = indices[-(count % len(indices)) - 1]
            
            original_char = chars[idx_to_change]
            chars[idx_to_change] = charmap[original_char]
            
            # Sécurité supplémentaire si on a fait un tour complet (très rare)
            suffix = ""
            if count > len(indices):
                suffix = "."
                
            return "".join(chars) + suffix

        final_data['name_english'] = final_data.apply(apply_accent_typo, axis=1)
        
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
                    df_csv = df_store[cols_export]
                    
                    csv_bytes = df_csv.to_csv(index=False).encode('utf-8')
                    zf.writestr(f"Output_Store_{store}.csv", csv_bytes)
                    
                    progress_bar.progress((i + 1) / len(stores))
            
            st.success("✅ Traitement terminé !")
            
            zip_buffer.seek(0)
            st.download_button(
                "📥 TÉLÉCHARGER TOUT (ZIP)",
                data=zip_buffer,
                file_name="resultats_stores_accents.zip",
                mime="application/zip",
                use_container_width=True
            )
            
            # Aperçu des changements
            with st.expander("🔎 Voir les noms modifiés (Doublons gérés)"):
                modified = final_data[final_data['name_dedup_count'] > 0][['store_id', 'external_id', 'name_english']]
                if not modified.empty:
                    st.write("Voici comment les doublons ont été modifiés :")
                    st.dataframe(modified.head(10))
                else:
                    st.info("Aucun doublon de nom n'a été trouvé.")

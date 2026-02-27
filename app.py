import streamlit as st
import pandas as pd

st.set_page_config(page_title="Assortiment vs MenuList Matcher", layout="wide")

st.title("📦 Assortiment vs MenuList Matcher")
st.markdown("Fichiers de sortie formatés exactement comme le modèle **MenuList**. Les images sont récupérées depuis la 2ème feuille de l'Assortiment.")

# --- BARRE LATÉRALE : UPLOADS ---
st.sidebar.header("1. Upload des Fichiers")
assortiment_file = st.sidebar.file_uploader("1️⃣ Fichier Assortiment (Excel avec 2 feuilles : Catalogue et Images)", type=['xlsx'])
menulist_file = st.sidebar.file_uploader("2️⃣ Fichier MenuList (CSV modèle)", type=['csv'])
pricing_file = st.sidebar.file_uploader("3️⃣ Fichier Prix & Quantités (Ex: invalid_rows.csv)", type=['csv'])

# Variables globales
df_assort = None
df_images = None
store_col = None
store_filter = None

def clean_id(serie):
    """Nettoie les IDs pour assurer une correspondance parfaite."""
    return serie.astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

# --- ÉTAPE 1 : LECTURE DE L'ASSORTIMENT & IMAGES ---
if assortiment_file:
    try:
        # Lecture de la 1ère feuille (Catalogue)
        df_assort = pd.read_excel(assortiment_file, sheet_name=0)
        
        # Lecture de la 2ème feuille (Images)
        try:
            df_images = pd.read_excel(assortiment_file, sheet_name=1)
            st.sidebar.success("✅ 2ème feuille (Images) lue avec succès.")
            
            # Renommer la colonne d'ID de la feuille image s'il s'agit de 'internal code'
            id_col_img = next((col for col in df_images.columns if 'internal' in col.lower() or 'external_id' in col.lower()), None)
            if id_col_img and id_col_img != 'external_id':
                df_images = df_images.rename(columns={id_col_img: 'external_id'})
                
            # Trouver la colonne d'image
            img_col = next((col for col in df_images.columns if 'image' in col.lower() or 'photo' in col.lower() or 'url' in col.lower()), None)
            if img_col and img_col != 'image':
                df_images = df_images.rename(columns={img_col: 'image'})

            # Nettoyer et fusionner
            if 'external_id' in df_assort.columns and 'external_id' in df_images.columns:
                df_assort['external_id'] = clean_id(df_assort['external_id'])
                df_images['external_id'] = clean_id(df_images['external_id'])
                df_images = df_images.drop_duplicates(subset=['external_id'])
                
                # Ne garder que l'ID et l'image pour la fusion
                if 'image' in df_images.columns:
                    df_assort = pd.merge(df_assort, df_images[['external_id', 'image']], on='external_id', how='left')
        except Exception as e:
            st.sidebar.warning(f"Impossible de lire la 2ème feuille (Images) : {e}")

        # Cherche la colonne store
        store_col = next((col for col in df_assort.columns if 'store' in col.lower() or 'magasin' in col.lower()), None)
        
        st.sidebar.header("2. Choix du Magasin")
        if store_col:
            unique_stores = df_assort[store_col].dropna().astype(str).str.replace(r'\.0$', '', regex=True).unique().tolist()
            unique_stores.sort()
            store_filter = st.sidebar.selectbox("Sélectionnez le Store ID :", unique_stores, index=unique_stores.index('170') if '170' in unique_stores else 0)
        else:
            store_filter = st.sidebar.text_input("Entrez le Store ID manuellement (ex: 170)", value="170")
            
    except Exception as e:
        st.sidebar.error(f"Erreur lors de la lecture de l'assortiment : {e}")

# --- ÉTAPE 2 : TRAITEMENT ---
if df_assort is not None and menulist_file:
    if st.sidebar.button("Lancer la correspondance 🚀"):
        with st.spinner('Traitement des données en cours...'):
            try:
                # Lecture MenuList pour récupérer la structure et les food_id
                df_menu = pd.read_csv(menulist_file, sep=';', dtype=str)
                menu_columns = df_menu.columns.tolist() # Sauvegarde des entêtes exactes
                
                if 'external_id' in df_assort.columns and 'external_id' in df_menu.columns:
                    df_assort['external_id'] = clean_id(df_assort['external_id'])
                    df_menu['external_id'] = clean_id(df_menu['external_id'])
                    
                    # Filtrage Store
                    if store_col:
                        df_assort_filtered = df_assort[df_assort[store_col].astype(str).str.replace(r'\.0$', '', regex=True) == str(store_filter)].copy()
                    else:
                        df_assort_filtered = df_assort.copy()
                    
                    # Jointure avec MenuList pour récupérer le food_id
                    menu_subset = df_menu[['external_id', 'food_id']].drop_duplicates(subset=['external_id'])
                    merged = pd.merge(df_assort_filtered, menu_subset, on='external_id', how='left')
                    
                    # Séparation existants / non-existants
                    existing_products = merged[merged['food_id'].notna()].copy()
                    non_existing_products = merged[merged['food_id'].isna()].copy()
                    
                    # --- Enrichissement Prix & Quantités (pour non-existants) ---
                    if pricing_file is not None:
                        df_pricing = pd.read_csv(pricing_file)
                        if 'product_id' in df_pricing.columns:
                            df_pricing['product_id'] = clean_id(df_pricing['product_id'])
                            
                            if 'store_id' in df_pricing.columns and store_filter:
                                df_pricing = df_pricing[df_pricing['store_id'].astype(str).str.replace(r'\.0$', '', regex=True) == str(store_filter)]
                            
                            # On renomme 'stock' en 'quantity' pour correspondre au format MenuList
                            rename_dict = {}
                            if 'stock' in df_pricing.columns: rename_dict['stock'] = 'quantity'
                            if rename_dict: df_pricing = df_pricing.rename(columns=rename_dict)
                            
                            cols_to_keep = ['product_id']
                            if 'price' in df_pricing.columns: cols_to_keep.append('price')
                            if 'quantity' in df_pricing.columns: cols_to_keep.append('quantity')
                            
                            pricing_subset = df_pricing[cols_to_keep].drop_duplicates(subset=['product_id'])
                            
                            non_existing_products = pd.merge(non_existing_products, pricing_subset, left_on='external_id', right_on='product_id', how='left')

                    # --- FORMATAGE FINAL SELON LE MODÈLE MENULIST ---
                    def format_like_menulist(df, target_columns):
                        """Crée un dataframe vide avec les bonnes colonnes et le remplit avec nos données"""
                        df_out = pd.DataFrame(columns=target_columns)
                        for col in target_columns:
                            if col in df.columns:
                                df_out[col] = df[col]
                        # Remplir les valeurs NaN par des chaînes vides pour faire plus propre
                        return df_out.fillna('')

                    output1_final = format_like_menulist(existing_products, menu_columns)
                    output2_final = format_like_menulist(non_existing_products, menu_columns)

                    # --- AFFICHAGE ---
                    st.success(f"✅ Traitement terminé pour le Store ID : {store_filter}")
                    
                    tab1, tab2 = st.tabs(["✅ Output 1 (Existants)", "❌ Output 2 (Non-Existants)"])
                    
                    with tab1:
                        st.subheader(f"Produits existants ({len(output1_final)} articles)")
                        st.dataframe(output1_final, use_container_width=True)
                        st.download_button(
                            label="📥 Télécharger Output 1 (CSV)",
                            data=output1_final.to_csv(index=False, sep=';').encode('utf-8-sig'),
                            file_name=f"Output1_Existing_Products.csv",
                            mime="text/csv"
                        )
                    
                    with tab2:
                        st.subheader(f"Produits manquants ({len(output2_final)} articles)")
                        st.dataframe(output2_final, use_container_width=True)
                        st.download_button(
                            label="📥 Télécharger Output 2 (CSV)",
                            data=output2_final.to_csv(index=False, sep=';').encode('utf-8-sig'),
                            file_name=f"Output2_NonExisting_Store_{store_filter}.csv",
                            mime="text/csv"
                        )
                else:
                    st.error("🚨 Erreur : La colonne `external_id` est introuvable.")
                    
            except Exception as e:
                st.error(f"Une erreur s'est produite : {e}")
elif not assortiment_file or not menulist_file:
    st.info("👈 Veuillez uploader vos fichiers pour commencer.")

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Assortiment vs MenuList Matcher", layout="wide")

st.title("📦 Assortiment vs MenuList Matcher (avec Images & Prix)")
st.markdown("Identifiez les produits existants et manquants. Les photos (issues de la feuille Images) et les prix/quantités seront intégrés dans les exports.")

# --- BARRE LATÉRALE : UPLOADS ---
st.sidebar.header("1. Upload des Fichiers")
assortiment_file = st.sidebar.file_uploader("1️⃣ Fichier Assortiment (Catalogue - CSV ou Excel)", type=['csv', 'xlsx'])
images_file = st.sidebar.file_uploader("🖼️ Fichier Images (Optionnel si Excel global)", type=['csv', 'xlsx'], help="Uploadez le CSV contenant les images, ou laissez vide si elles sont dans une feuille 'Images' de l'Excel ci-dessus.")
menulist_file = st.sidebar.file_uploader("2️⃣ Fichier MenuList (CSV)", type=['csv'])
pricing_file = st.sidebar.file_uploader("3️⃣ Fichier Prix & Quantités (Ex: invalid_rows.csv)", type=['csv'])

# Variables globales
df_assort = None
df_images = None
store_col = None
store_filter = None

# Fonction utilitaire pour nettoyer l'ID
def clean_id(serie):
    return serie.astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

# Fonction pour trouver la colonne image
def find_image_column(df):
    for col in df.columns:
        if 'image' in col.lower() or 'photo' in col.lower() or 'url' in col.lower():
            return col
    return None

# --- ÉTAPE 1 : LECTURE DE L'ASSORTIMENT & IMAGES ---
if assortiment_file:
    try:
        # Lecture du catalogue
        if assortiment_file.name.endswith('.csv'):
            df_assort = pd.read_csv(assortiment_file)
        else:
            # Excel : on lit la première feuille par défaut
            df_assort = pd.read_excel(assortiment_file, sheet_name=0)
            
            # Si aucun fichier image séparé n'est uploadé, on tente de lire l'onglet "Images" dans l'Excel
            if not images_file:
                xls = pd.ExcelFile(assortiment_file)
                # Cherche une feuille qui s'appelle 'Images' (insensible à la casse)
                sheet_img = next((sheet for sheet in xls.sheet_names if 'image' in sheet.lower()), None)
                if sheet_img:
                    df_images = pd.read_excel(assortiment_file, sheet_name=sheet_img)
                    st.sidebar.success(f"Onglet images détecté : '{sheet_img}'")

        # Lecture du fichier images s'il est uploadé séparément (CSV)
        if images_file:
            if images_file.name.endswith('.csv'):
                df_images = pd.read_csv(images_file)
            else:
                df_images = pd.read_excel(images_file)
            st.sidebar.success("Fichier Images chargé avec succès.")

        # Fusion Catalogue + Images sur external_id
        if df_images is not None and 'external_id' in df_assort.columns and 'external_id' in df_images.columns:
            df_assort['external_id'] = clean_id(df_assort['external_id'])
            df_images['external_id'] = clean_id(df_images['external_id'])
            # On supprime les doublons potentiels dans les images pour éviter de dédoubler les lignes
            df_images = df_images.drop_duplicates(subset=['external_id'])
            
            # Jointure (ajoute la colonne image au catalogue, en gardant son en-tête intacte)
            df_assort = pd.merge(df_assort, df_images, on='external_id', how='left')

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

# --- ÉTAPE 2 : TRAITEMENT MENULIST & PRICING ---
if df_assort is not None and menulist_file:
    if st.sidebar.button("Lancer la correspondance 🚀"):
        with st.spinner('Traitement des données en cours...'):
            try:
                # Lecture MenuList
                df_menu = pd.read_csv(menulist_file, sep=';', dtype=str)
                
                if 'external_id' in df_assort.columns and 'external_id' in df_menu.columns:
                    # Nettoyage
                    df_assort['external_id'] = clean_id(df_assort['external_id'])
                    df_menu['external_id'] = clean_id(df_menu['external_id'])
                    
                    # Filtrage Store (si colonne présente)
                    if store_col:
                        df_assort_filtered = df_assort[df_assort[store_col].astype(str).str.replace(r'\.0$', '', regex=True) == str(store_filter)]
                    else:
                        df_assort_filtered = df_assort
                    
                    # Jointure avec la MenuList (pour récupérer le food_id)
                    menu_subset = df_menu[['external_id', 'food_id']].drop_duplicates(subset=['external_id'])
                    merged = pd.merge(df_assort_filtered, menu_subset, on='external_id', how='left')
                    
                    # Séparation existants / non-existants
                    existing_products = merged[merged['food_id'].notna()].copy()
                    non_existing_products = merged[merged['food_id'].isna()].copy()
                    
                    # --- Étape 3 : Enrichissement Prix & Quantités (Fichier invalid_rows) ---
                    if pricing_file is not None:
                        df_pricing = pd.read_csv(pricing_file)
                        if 'product_id' in df_pricing.columns:
                            df_pricing['product_id'] = clean_id(df_pricing['product_id'])
                            
                            # Filtre magasin
                            if 'store_id' in df_pricing.columns and store_filter:
                                df_pricing = df_pricing[df_pricing['store_id'].astype(str).str.replace(r'\.0$', '', regex=True) == str(store_filter)]
                            
                            cols_to_keep = ['product_id']
                            if 'price' in df_pricing.columns: cols_to_keep.append('price')
                            if 'stock' in df_pricing.columns: cols_to_keep.append('stock')
                            
                            pricing_subset = df_pricing[cols_to_keep].drop_duplicates(subset=['product_id'])
                            
                            # On ajoute prix et stock aux produits NON-existants
                            non_existing_products = pd.merge(non_existing_products, pricing_subset, left_on='external_id', right_on='product_id', how='left')
                            if 'product_id' in non_existing_products.columns:
                                non_existing_products = non_existing_products.drop(columns=['product_id'])
                    
                    # --- Configuration de l'affichage Web (optionnel, pour faire joli) ---
                    img_col_name = find_image_column(existing_products)
                    config_existing = {img_col_name: st.column_config.ImageColumn("Aperçu (Image)")} if img_col_name else {}
                    config_non_existing = {img_col_name: st.column_config.ImageColumn("Aperçu (Image)")} if img_col_name else {}

                    # --- AFFICHAGE ET EXPORT ---
                    st.success(f"✅ Traitement terminé pour le Store ID : {store_filter}")
                    
                    tab1, tab2 = st.tabs(["✅ Produits Existants", "❌ Produits Non-Existants (Magasin 170)"])
                    
                    with tab1:
                        st.subheader(f"Produits trouvés ({len(existing_products)} articles)")
                        st.dataframe(existing_products, use_container_width=True, column_config=config_existing)
                        st.download_button(
                            label="📥 Télécharger Produits Existants (CSV)",
                            data=existing_products.to_csv(index=False).encode('utf-8-sig'),
                            file_name=f"Output1_Existing_Products.csv",
                            mime="text/csv"
                        )
                    
                    with tab2:
                        st.subheader(f"Produits manquants ({len(non_existing_products)} articles)")
                        st.dataframe(non_existing_products, use_container_width=True, column_config=config_non_existing)
                        st.download_button(
                            label=f"📥 Télécharger Produits Non-Existants (CSV)",
                            data=non_existing_products.to_csv(index=False).encode('utf-8-sig'),
                            file_name=f"Output2_NonExisting_Store_{store_filter}.csv",
                            mime="text/csv"
                        )
                else:
                    st.error("🚨 Erreur : Les fichiers Catalogue, Images et MenuList doivent tous contenir la colonne `external_id`.")
                    
            except Exception as e:
                st.error(f"Une erreur s'est produite : {e}")
elif not assortiment_file or not menulist_file:
    st.info("👈 Veuillez uploader vos fichiers pour commencer.")

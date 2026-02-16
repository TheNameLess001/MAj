import streamlit as st
import pandas as pd
import io
import zipfile

# Configuration de la page
st.set_page_config(page_title="Générateur de Fichiers Store", layout="wide")

st.title("🛒 Générateur de Fichiers CSV par Store")
st.markdown("""
Cette application transforme votre fichier Excel multi-onglets en fichiers CSV individuels pour chaque magasin.
**Structure attendue du fichier Excel :**
1. **Output** (Modèle de colonnes)
2. **Catalogue** (Détails produits : category, name_english...)
3. **MAJ** (Prix, quantité, store_id...)
4. **Image** (Liens images)
""")

# Fonction pour charger les données
def load_data(uploaded_file):
    try:
        # On lit les feuilles spécifiques. 
        # Note: On utilise des noms standards, assurez-vous que vos onglets s'appellent ainsi ou sont dans cet ordre (0, 1, 2, 3)
        xls = pd.ExcelFile(uploaded_file)
        
        # On essaie de récupérer par nom, sinon par index
        sheet_names = xls.sheet_names
        
        # Logique de récupération flexible (Nom ou Index)
        df_output_template = pd.read_excel(uploaded_file, sheet_name=sheet_names[0]) # 1er onglet
        df_catalogue = pd.read_excel(uploaded_file, sheet_name=sheet_names[1])       # 2eme onglet
        df_maj = pd.read_excel(uploaded_file, sheet_name=sheet_names[2])             # 3eme onglet
        df_image = pd.read_excel(uploaded_file, sheet_name=sheet_names[3])           # 4eme onglet
        
        return df_output_template, df_catalogue, df_maj, df_image
    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier : {e}")
        return None, None, None, None

# Upload du fichier
uploaded_file = st.file_uploader("Choisissez votre fichier Excel (.xlsx)", type=['xlsx'])

if uploaded_file is not None:
    st.success("Fichier chargé ! Traitement en cours...")
    
    # Chargement des DataFrames
    df_template, df_cat, df_maj, df_img = load_data(uploaded_file)
    
    if df_maj is not None:
        # Nettoyage et préparation des données
        
        # 1. Préparer le catalogue (s'assurer que external_id est une string pour la fusion)
        df_cat['external_id'] = df_cat['external_id'].astype(str)
        
        # 2. Préparer les images
        # Si un produit a plusieurs images, on prend la première (PICTURE_ORDER = 1 ou drop_duplicates)
        if 'PICTURE_ORDER' in df_img.columns:
            df_img = df_img.sort_values('PICTURE_ORDER')
        df_img['external_id'] = df_img['external_id'].astype(str)
        df_img = df_img.drop_duplicates(subset=['external_id'], keep='first')
        
        # 3. Préparer MAJ
        df_maj['product_id'] = df_maj['product_id'].astype(str)
        
        # Récupérer la liste des colonnes attendues depuis l'onglet Output
        # Si l'onglet output est vide, on définit les colonnes manuellement selon votre demande
        expected_columns = ['name_english', 'price', 'quantity', 'description', 'category', 'sub_category', 'image', 'external_id']
        
        # Liste des stores uniques
        unique_stores = df_maj['store_id'].unique()
        
        st.write(f"Nombre de magasins détectés : **{len(unique_stores)}**")
        
        # Buffer pour le fichier ZIP
        zip_buffer = io.BytesIO()
        
        processed_count = 0
        
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            progress_bar = st.progress(0)
            
            for i, store_id in enumerate(unique_stores):
                # Filtrer MAJ pour ce store
                store_data = df_maj[df_maj['store_id'] == store_id].copy()
                
                # --- FUSIONS (MERGE) ---
                
                # 1. Ajouter les infos Catalogue (Match: product_id <-> external_id)
                merged_df = pd.merge(
                    store_data, 
                    df_cat, 
                    left_on='product_id', 
                    right_on='external_id', 
                    how='left'
                )
                
                # 2. Ajouter les Images (Match: product_id <-> external_id)
                # Note: external_id existe maintenant en double cause du merge précédent, on utilise product_id de la base
                merged_df = pd.merge(
                    merged_df,
                    df_img[['external_id', 'image']],
                    left_on='product_id',
                    right_on='external_id',
                    how='left',
                    suffixes=('', '_img')
                )
                
                # --- CONSTRUCTION DU FICHIER FINAL ---
                final_df = pd.DataFrame()
                
                # Mapping des colonnes
                final_df['external_id'] = merged_df['product_id']
                final_df['name_english'] = merged_df['name_english']
                final_df['price'] = merged_df['price']
                final_df['quantity'] = merged_df['quantity']
                final_df['category'] = merged_df['category']
                final_df['sub_category'] = merged_df['sub_category']
                final_df['image'] = merged_df['image']
                
                # Pour la description, si elle n'existe pas, on met vide ou name_english
                if 'description' in merged_df.columns:
                    final_df['description'] = merged_df['description']
                else:
                    final_df['description'] = "" 

                # S'assurer que l'ordre des colonnes est exact
                final_df = final_df[expected_columns]
                
                # Gestion des valeurs nulles
                final_df['quantity'] = final_df['quantity'].fillna(0).astype(int)
                final_df['price'] = final_df['price'].fillna(0)
                
                # Convertir en CSV
                csv_data = final_df.to_csv(index=False).encode('utf-8')
                
                # Ajouter au ZIP
                zf.writestr(f"Output_Store_{store_id}.csv", csv_data)
                
                processed_count += 1
                progress_bar.progress((i + 1) / len(unique_stores))

        st.success(f"Traitement terminé ! {processed_count} fichiers générés.")
        
        # Bouton de téléchargement
        zip_buffer.seek(0)
        st.download_button(
            label="📥 Télécharger tous les fichiers (ZIP)",
            data=zip_buffer,
            file_name="stores_output.zip",
            mime="application/zip"
        )
        
        # Aperçu d'un fichier (le dernier traité)
        st.subheader("Aperçu des données (Dernier magasin traité)")
        st.dataframe(final_df.head())

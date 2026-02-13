# Import library
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder

# Load data
dataset_path = 'DATAGABUNGAN.xlsx'
df = pd.read_excel(dataset_path)

# Info awal
df.info()

# Pastikan kolom target ('Jumlah') dipindah ke paling kanan
jumlah_column = df.pop('Jumlah')
df['Jumlah'] = jumlah_column

# Tampilkan 5 data pertama
print(df.head())

# Statistik deskriptif
print(df.describe())

# Cek missing value
print(df.isnull().sum())

# Label Encoding untuk kolom kategorikal
categorical_columns = ['Kota', 'Lokasi', 'Jenis pembangunan', 'Jenis Pekerjaan', 'Uraian Pekerjaan', 'Satuan']

label_encoders = {}
for col in categorical_columns:
    le = LabelEncoder()
    df[col] = le.fit_transform(df[col].astype(str))
    label_encoders[col] = le

# Cek data setelah encode
print(df.head())

# Simpan Label Encoders
import joblib
joblib.dump(label_encoders, 'label_encoders.joblib')
 